"""The active QA page must not reload all findings for each count tick."""
import json
from copy import deepcopy
from types import SimpleNamespace

from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from . import test_qa_matching_backend as fixtures
from .survey_processing_models import SurveySourceAnalysis, SurveyProcessingJob, SurveyProcessingEvent
from . import survey_processing as pipeline


class PhaseProjectionTests(SimpleTestCase):
    def phases(self,status,completed=3,total=3,saved=0,result=False):
        from .qa_review_progress import phase_projection
        return phase_projection(status,completed,total,saved,result)

    def test_equal_analysis_counter_is_not_a_completed_stage_boundary(self):
        phases=self.phases('analysing_evidence')
        self.assertEqual(phases['analysis']['state'],'running')
        self.assertEqual(phases['findings']['state'],'running')
        self.assertEqual(phases['matching']['state'],'waiting')
        self.assertIsNone(phases['findings']['completed'])
        self.assertIsNone(phases['findings']['total'])

    def test_preparing_checklist_is_completed_analysis_and_running_tagging_with_unknown_total(self):
        phases=self.phases('preparing_checklist',saved=5)
        self.assertEqual(phases['analysis']['state'],'complete')
        self.assertEqual(phases['findings']['state'],'complete')
        self.assertEqual(phases['matching']['state'],'running')
        self.assertEqual(phases['matching']['completed'],5)
        self.assertIsNone(phases['matching']['total'])

    def test_pause_failure_and_resume_preserve_durable_completed_analysis(self):
        for status,matching in [('paused','paused'),('pausing','pausing'),('failed','failed'),('queued','queued')]:
            with self.subTest(status=status):
                phases=self.phases(status,saved=2)
                self.assertEqual(phases['analysis']['state'],'complete')
                self.assertEqual(phases['matching']['state'],matching)
                self.assertEqual(phases['matching']['completed'],2)
        phases=self.phases('paused',completed=1,total=3)
        self.assertEqual(phases['analysis']['state'],'paused')
        self.assertEqual(phases['matching']['state'],'waiting')

    def test_saved_result_completes_matching_even_if_drawing_work_pauses_or_fails(self):
        for status in ['paused','failed','preparing_drawings','ready_for_review']:
            with self.subTest(status=status):
                phases=self.phases(status,result=True)
                self.assertEqual([phases[key]['state'] for key in ['analysis','findings','matching']],['complete']*3)


@override_settings(SECRET_KEY='qa-light-progress-test', ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QAReviewProgressTests(TestCase):
    setUp = fixtures.QAMatchingBackendTests.setUp
    person = fixtures.QAMatchingBackendTests.person
    add_photo = fixtures.QAMatchingBackendTests.add_photo
    raw = fixtures.QAMatchingBackendTests.raw
    post = fixtures.QAMatchingBackendTests.post
    state = fixtures.QAMatchingBackendTests.state
    upload = fixtures.QAMatchingBackendTests.upload
    submit = fixtures.QAMatchingBackendTests.submit
    assert_submitted = fixtures.QAMatchingBackendTests.assert_submitted

    def progress(self, actor=None, **params):
        from .qa_review_progress import progress
        return progress(SimpleNamespace(user=actor or self.quality, GET=params), self.checklist.pk)

    def test_phases_separate_completed_analysis_from_running_tagging_without_loading_payloads(self):
        from django.urls import reverse
        SurveyProcessingJob.objects.filter(revision=self.revision).update(status='preparing_checklist',completed=3,total=3)
        saved={'synthetic':'not read by progress'}
        SurveySourceAnalysis.objects.create(revision=self.revision,source_id='mapping:synthetic-phase-batch',
            payload=saved,digest=pipeline.digest(saved))
        with CaptureQueriesContext(connection) as queries:
            result=self.progress()
        phases=result['ai']['phases']
        self.assertEqual(phases['analysis']['state'],'complete')
        self.assertEqual((phases['analysis']['completed'],phases['analysis']['total']),(3,3))
        self.assertEqual(phases['findings']['state'],'complete')
        self.assertEqual(phases['findings']['shared_with'],'analysis')
        self.assertIsNone(phases['findings']['completed'])
        self.assertEqual(phases['matching']['state'],'running')
        self.assertEqual(phases['matching']['completed'],1)
        self.assertIsNone(phases['matching']['total'])
        sql='\n'.join(row['sql'] for row in queries)
        self.assertNotIn('"payload"',sql)
        self.assertNotIn('"snapshot"',sql)
        self.client.force_login(self.quality)
        full=self.client.get(reverse('photo_capture_review_state',args=[self.checklist.pk]))
        self.assertEqual(full.status_code,200,full.content)
        self.assertEqual(full.json()['ai']['phases'],phases)

    def test_count_ticks_do_not_load_frozen_snapshots_or_all_source_payloads(self):
        payload = {'findings': [], 'large': 'x' * 100000}
        SurveySourceAnalysis.objects.create(revision=self.revision, source_id='photo:'+str(self.ids[0]),
            payload=payload, digest=pipeline.digest(payload))
        with CaptureQueriesContext(connection) as queries:
            first = self.progress()
        self.assertLess(len(json.dumps(first)), 12000)
        sql = '\n'.join(row['sql'] for row in queries)
        self.assertNotIn('"snapshot"', sql)
        self.assertNotIn('"payload"', sql)
        SurveyProcessingJob.objects.filter(revision=self.revision).update(completed=1)
        second = self.progress()
        self.assertEqual(first['progress_token'], second['progress_token'])
        self.assertEqual(second['ai']['completed'], 1)
        self.assertNotIn('photos', second)

    def test_review_event_and_stage_changes_invalidate_details_without_changing_evidence(self):
        before = deepcopy(self.revision.snapshot)
        initial = self.progress()
        SurveyProcessingEvent.objects.create(revision=self.revision, actor=self.quality,
            action='qa_answer', payload={'items': {}})
        changed = self.progress()
        self.assertNotEqual(initial['progress_token'], changed['progress_token'])
        SurveyProcessingJob.objects.filter(revision=self.revision).update(status='preparing_checklist')
        stage = self.progress()
        self.assertNotEqual(changed['progress_token'], stage['progress_token'])
        self.revision.refresh_from_db(); self.assertEqual(self.revision.snapshot, before)

    def test_selected_photo_analysis_is_scoped_and_integrity_checked(self):
        payload = {'source_id':'photo:'+str(self.ids[0]), 'findings':[{'value':'SyntheticCo'}]}
        source = SurveySourceAnalysis.objects.create(revision=self.revision, source_id=payload['source_id'],
            payload=payload, digest=pipeline.digest(payload))
        result = self.progress(photo_id=str(self.ids[0]))
        self.assertEqual(result['photo']['observations'], payload['findings'])
        from django.core.exceptions import ValidationError
        from django.http import Http404
        with self.assertRaises((Http404, ValidationError)): self.progress(photo_id='99999999')
        SurveySourceAnalysis.objects.create(revision=self.revision, source_id='photo:'+str(self.ids[1]),
            payload=payload, digest='bad')
        with self.assertRaises(ValidationError): self.progress(photo_id=str(self.ids[1]))

    def test_engineer_team_lead_and_client_cannot_receive_qa_analysis_ticks(self):
        from django.core.exceptions import PermissionDenied
        from django.http import Http404
        for actor in [self.engineer, self.lead, self.customer]:
            with self.subTest(role=actor.profile.role), self.assertRaises((PermissionDenied, Http404)):
                self.progress(actor)
