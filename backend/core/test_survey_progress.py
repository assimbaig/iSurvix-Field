"""Progress never loads retained evidence packages; selected details stay reviewable."""
from copy import deepcopy
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from . import survey_processing as pipeline
from . import test_survey_processing as fixtures
from .models import Checklist
from .survey_processing_models import (SurveyProcessingRevision, SurveyProcessingJob,
    SurveyProcessingResult, SurveySourceAnalysis, SurveyProcessingEvent, SurveyDrawingSet)


@override_settings(SECRET_KEY='isolated-progress-test', ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SurveyProgressTests(TestCase):
    setUp = fixtures.SurveyProcessingTests.setUp
    person = fixtures.SurveyProcessingTests.person
    add_photo = fixtures.SurveyProcessingTests.add_photo
    request = fixtures.SurveyProcessingTests.request

    def seed(self, count=1):
        revisions = []
        for number in range(1, count + 1):
            snapshot = pipeline.freeze_data(self.checklist)
            if number < count:
                snapshot['answers'] = {'synthetic_old_revision': number}
            revision = SurveyProcessingRevision.objects.create(checklist=self.checklist, number=number,
                digest=pipeline.digest(snapshot), snapshot=snapshot, submitted_by=self.engineer)
            SurveyProcessingJob.objects.create(revision=revision, status='ready_for_review', model='synthetic-only', completed=2, total=2)
            source = {'source_id': f'photo:{self.photo.pk}', 'reference': 'original'}
            findings = [{**source, 'finding_key': f'photo:{self.photo.pk}:finding:{i}', 'field_hint': 'manufacturer',
                'value': str(i), 'unit': '', 'confidence': 'medium', 'verification_status': 'needs_review'} for i in range(105)]
            payload = {'checklist_items': [{'id': 'manufacturer', 'label': 'Manufacturer', 'value': None,
                'sources': [source], 'accepted': False, 'status': 'Needs review'}], 'findings': findings,
                'conflicts': [], 'missing': [], 'drawing_records': [], 'suggested_items': []}
            SurveyProcessingResult.objects.create(revision=revision, payload=payload, digest=pipeline.digest(payload))
            saved_source = {**source, 'preview_file': 'synthetic-preview.jpg', 'findings': findings}
            SurveySourceAnalysis.objects.create(revision=revision, source_id=source['source_id'], payload=saved_source,
                digest=pipeline.digest(saved_source))
            SurveyProcessingEvent.objects.bulk_create([SurveyProcessingEvent(revision=revision, actor=self.engineer,
                action='synthetic_note', reason=f'Synthetic note {i}', payload={}) for i in range(52)])
            for edition in (1, 2):
                SurveyDrawingSet.objects.create(revision=revision, edition=edition, review_digest=pipeline.review_digest(payload),
                    geometry={'synthetic_only': True}, manifest={'sheets': [{'title': 'Synthetic sheet', 'number': 'SYN-01'}]})
            revisions.append(revision)
        self.client.force_login(self.engineer)
        return revisions

    def endpoint(self, name='state'):
        return reverse('survey_processing_' + name, args=[self.checklist.pk])

    def test_progress_is_bounded_and_never_reads_snapshots_sources_results_or_geometry(self):
        self.seed(26)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.endpoint('progress'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['revisions']), 25)
        self.assertEqual(data['active']['revision'], 26)
        self.assertLess(len(response.content), 15000)
        sql = '\n'.join(q['sql'] for q in queries)
        for forbidden in ['"snapshot"', 'core_surveysourceanalysis', 'core_surveyprocessingresult', '"geometry"']:
            self.assertNotIn(forbidden, sql)
        self.assertLess(len(queries), 25)

    def test_progress_counts_change_without_invalidating_details_until_stage_changes(self):
        revision, = self.seed()
        first = self.client.get(self.endpoint('progress')).json()
        SurveyProcessingJob.objects.filter(revision=revision).update(completed=1)
        tick = self.client.get(self.endpoint('progress')).json()
        self.assertEqual(tick['detail_token'], first['detail_token'])
        self.assertEqual(tick['active']['completed'], 1)
        SurveyProcessingJob.objects.filter(revision=revision).update(status='failed', error='Synthetic interrupted job')
        changed = self.client.get(self.endpoint('progress')).json()
        self.assertNotEqual(changed['detail_token'], first['detail_token'])
        self.assertEqual(changed['active']['error'], 'Synthetic interrupted job')

    def test_exact_selected_revision_and_all_retained_history_remain_available(self):
        revisions = self.seed(26)
        selected = revisions[0]
        response = self.client.get(self.endpoint(), {'compact': 1, 'revision_id': selected.pk})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['selected_revision_id'], selected.pk)
        details = [r for r in data['revisions'] if r.get('detailed')]
        self.assertEqual([r['id'] for r in details], [selected.pk])
        self.assertFalse(details[0]['current'])
        self.assertEqual(data['pagination']['history']['total'], 26)
        second = self.client.get(self.endpoint(), {'compact': 1, 'history_page': 2}).json()
        self.assertEqual(second['revisions'][0]['id'], selected.pk)

    def test_findings_events_and_drawing_editions_are_paginated_without_loss_or_duplicates(self):
        revision, = self.seed()
        first = self.client.get(self.endpoint(), {'compact': 1}).json()['revisions'][0]
        self.assertEqual(len(first['findings']), 50)
        self.assertEqual(first['pagination']['findings']['total'], 105)
        keys = [f['finding_key'] for f in first['findings']]
        for page in (2, 3):
            partial = self.client.get(self.endpoint(), {'compact': 1, 'revision_id': revision.pk,
                'section': 'findings', 'page': page}).json()['revisions'][0]
            self.assertNotIn('checklist_items', partial)
            keys += [f['finding_key'] for f in partial['findings']]
        self.assertEqual(len(set(keys)), 105)
        self.assertEqual(len(keys), 105)
        events = self.client.get(self.endpoint(), {'compact': 1, 'section': 'events', 'page': 2}).json()['revisions'][0]
        self.assertEqual(len(events['events']), 2)
        self.assertEqual(first['pagination']['drawings']['total'], 2)
        other = self.client.get(self.endpoint(), {'compact': 1, 'section': 'drawings', 'page': 2}).json()['revisions'][0]
        self.assertNotEqual(first['drawings'][0]['id'], other['drawings'][0]['id'])
        self.assertIn('thumbnail_url', first['checklist_items'][0]['sources'][0])

    def test_invalid_and_foreign_revision_and_unauthorised_progress_are_rejected(self):
        self.seed()
        self.assertEqual(self.client.get(self.endpoint(), {'compact': 1, 'revision_id': 999999}).status_code, 404)
        self.assertEqual(self.client.get(self.endpoint(), {'compact': 1, 'section': 'anything'}).status_code, 409)
        self.client.logout()
        self.assertEqual(self.client.get(self.endpoint('progress')).status_code, 302)
        other = Checklist.objects.create(project=self.project, user=self.lead, site_id='SYN-FOREIGN-PROGRESS')
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.get(reverse('survey_processing_progress', args=[other.pk])).status_code, 404)

    def test_clients_do_not_receive_draft_progress_or_internal_findings(self):
        self.seed()
        self.client.force_login(self.customer)
        # The normal survey permission gate denies the whole unreleased record.
        # Progress must not become a side channel around that stricter gate.
        self.assertEqual(self.client.get(self.endpoint('progress')).status_code, 404)
        self.assertEqual(self.client.get(self.endpoint(), {'compact': 1}).status_code, 404)

    def test_compact_history_does_not_change_result_bytes_or_review_events(self):
        revision, = self.seed()
        before = deepcopy(revision.processing_result.payload)
        events = list(revision.processing_events.values_list('pk', 'payload'))
        for page in (1, 2, 3):
            self.client.get(self.endpoint(), {'compact': 1, 'section': 'findings', 'page': page})
        revision.processing_result.refresh_from_db()
        self.assertEqual(revision.processing_result.payload, before)
        self.assertEqual(list(revision.processing_events.values_list('pk', 'payload')), events)
