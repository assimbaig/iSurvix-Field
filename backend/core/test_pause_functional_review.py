"""Independent functional checks of late-phase pauses and outbound retries.

The inference edge is controlled; saved checkpoints, request/response semantics
and drawing editions use real isolated Django records.
"""
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import survey_processing as pipeline
from . import test_survey_pause as fixture
from . import test_remote_survey_worker as remote
from .survey_processing_models import SurveyDrawingSet, SurveyProcessingJob


@override_settings(SECRET_KEY='isolated-independent-pause-review',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentLocalPauseReviewTests(TestCase):
    setUp=fixture.SurveyPauseTests.setUp
    person=fixture.SurveyPauseTests.person
    request=fixture.SurveyPauseTests.request
    add_photo=fixture.SurveyPauseTests.add_photo
    analysed=fixture.SurveyPauseTests.analysed
    processing=fixture.SurveyPauseTests.processing
    submitted=fixture.SurveyPauseTests.submitted
    control=fixture.SurveyPauseTests.control

    def test_pause_during_drawing_transaction_commits_output_then_resumes_without_duplicate_editions(self):
        self.submitted()
        stack,native,renderer=self.processing()
        def render(*args,**kwargs):
            self.control('pause_ai')
            self.assertEqual(SurveyProcessingJob.objects.get(revision=self.revision).status,'pausing')
            return {'pdf':'synthetic-package.pdf','dxf':'synthetic-package.dxf','previews':[]}
        renderer.side_effect=render
        self.assertTrue(pipeline.process_next())
        job=SurveyProcessingJob.objects.get(revision=self.revision)
        self.assertEqual(job.status,'paused',job.error)
        output=self.revision.drawing_sets.get();source_ids=list(self.revision.source_analyses.values_list('pk',flat=True))
        self.assertEqual(len(source_ids),2)
        self.assertTrue(hasattr(self.revision,'processing_result'))
        stack.close();self.control('resume_ai')
        _,native2,renderer2=self.processing()
        self.assertTrue(pipeline.process_next())
        job.refresh_from_db();self.assertEqual(job.status,'ready_for_review',job.error)
        native2.assert_not_called();renderer2.assert_not_called()
        self.assertEqual(self.revision.drawing_sets.get().pk,output.pk)
        self.assertEqual(list(self.revision.source_analyses.values_list('pk',flat=True)),source_ids)

    def test_late_progress_cannot_erase_pause_or_its_monotonic_saved_count(self):
        self.submitted();job=pipeline.claim()
        pipeline.progress(job,completed=1,total=2)
        self.control('pause_ai')
        pipeline.progress(job,'preparing_checklist',completed=2,total=2)
        job.refresh_from_db();self.assertEqual((job.status,job.completed),('pausing',2))
        from .survey_pause import boundary,ProcessingPaused
        with self.assertRaises(ProcessingPaused):boundary(job)
        job.refresh_from_db();self.assertEqual((job.status,job.completed),('paused',2))

    def test_changed_inputs_do_not_offer_a_resume_button_that_can_only_fail(self):
        self.submitted();self.control('pause_ai')
        self.checklist.answer_data={'custom':{'contact':'Changed after this submitted snapshot'}}
        self.checklist.save(update_fields=['answer_data'])
        self.client.force_login(self.quality)
        data=self.client.get(reverse('survey_processing_progress',args=[self.checklist.pk])).json()
        self.assertFalse(data['active']['can_resume'])
        with self.assertRaises(ValidationError):self.control('resume_ai')

    def test_retried_resume_after_worker_claim_preserves_the_active_lease(self):
        self.submitted();self.control('pause_ai');self.control('resume_ai')
        claimed=pipeline.claim();owner=claimed.lease_owner;attempts=claimed.attempts
        # The first HTTP response can be lost after the worker already claims
        # the resumed job. Retrying that resume must be a harmless no-op.
        self.control('resume_ai')
        claimed.refresh_from_db()
        self.assertEqual(claimed.status,'analysing_evidence')
        self.assertEqual((claimed.lease_owner,claimed.attempts),(owner,attempts))
        self.assertEqual(self.revision.processing_events.filter(action='resumed').count(),1)


@override_settings(**remote.SETTINGS)
class IndependentRemotePauseReviewTests(remote.Fixtures,TestCase):
    control=fixture.SurveyPauseTests.control

    def pause(self):
        self.control('pause_ai')

    def test_duplicate_delivery_while_pausing_is_idempotent_and_old_lease_cannot_mutate_resumed_job(self):
        claimed=self.claim();task=remote.bridge.next_task(self.credential,claimed['job_id'],claimed['lease'])
        self.pause()
        first=self.complete(claimed,task);duplicate=self.complete(claimed,task)
        self.assertTrue(first['accepted']);self.assertFalse(first['duplicate']);self.assertTrue(duplicate['duplicate'])
        self.assertEqual(self.revision.source_analyses.count(),1)
        result=remote.bridge.next_task(self.credential,claimed['job_id'],claimed['lease'])
        self.assertEqual(result['status'],'paused')
        self.control('resume_ai')
        resumed=self.claim();self.assertNotEqual(resumed['lease'],claimed['lease'])
        with self.assertRaises(PermissionDenied):self.complete(claimed,task)
        job=SurveyProcessingJob.objects.get(revision=self.revision)
        self.assertEqual(job.completed,1)
        current=remote.bridge.next_task(self.credential,resumed['job_id'],resumed['lease'])
        self.assertNotEqual(current['task_id'],task['task_id'])

    def test_expired_remote_pause_can_be_explicitly_resumed_without_a_new_snapshot(self):
        claimed=self.claim();self.pause()
        SurveyProcessingJob.objects.filter(pk=claimed['job_id']).update(lease_until=timezone.now()-timedelta(seconds=1))
        self.control('resume_ai')
        job=SurveyProcessingJob.objects.get(revision=self.revision)
        self.assertEqual(job.status,'queued')
        self.assertEqual(self.revision.checklist.processing_revisions.count(),1)
        self.assertEqual(self.revision.source_analyses.count(),0)
        self.assertTrue(self.claim())
