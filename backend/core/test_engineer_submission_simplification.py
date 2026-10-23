"""Submission-only AI intake preserves real sources and existing review boundaries."""
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import survey_processing as pipeline, test_survey_processing as fixtures
from .models import Checklist, ChecklistTemplate, PhotoJob
from .survey_processing_models import SurveyProcessingJob


@override_settings(SECRET_KEY='isolated-engineer-intake', ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EngineerSubmissionSimplificationTests(TestCase):
    setUp = fixtures.SurveyProcessingTests.setUp
    person = fixtures.SurveyProcessingTests.person
    request = fixtures.SurveyProcessingTests.request
    add_photo = fixtures.SurveyProcessingTests.add_photo
    analysed = fixtures.SurveyProcessingTests.analysed
    processing = fixtures.SurveyProcessingTests.processing
    ready = fixtures.SurveyProcessingTests.ready
    accept_complete = fixtures.SurveyProcessingTests.accept_complete

    def legacy_job(self, status='failed'):
        job = PhotoJob.objects.create(checklist=self.checklist, requested_by=self.engineer,
            model='synthetic-retained-job', schema=self.checklist.schema_snapshot,
            status=status, error='Retained failure',
            processed_photo_ids=[self.photo.pk, self.photo2.pk] if status == 'completed' else [])
        job.photos.set([self.photo, self.photo2])
        return job

    def exclude_processing(self):
        self.checklist.checklist_template = ChecklistTemplate.objects.create(
            name='Excluded intake fixture', definition=self.schema, published=True,
            checklist_required=False)
        self.checklist.save(update_fields=['checklist_template'])

    def test_category_upload_preserves_original_bytes_and_never_starts_ai(self):
        self.client.force_login(self.engineer)
        session = pipeline.upload_session(self.request(), self.checklist.pk)
        image = BytesIO()
        Image.new('RGB', (75, 48), 'red').save(image, format='PNG')
        original = image.getvalue()
        with patch('core.photo_service.verify_vision') as vision:
            response = self.client.post(reverse('photo_upload', args=[self.checklist.pk]), {
                'group': 'Civil',
                'processing_upload_token': str(session.token),
                'files': [SimpleUploadedFile('synthetic-ungrouped.png', original, content_type='image/png')],
            })
        self.assertEqual(response.status_code, 201, response.content)
        photo = self.checklist.photo_evidence.get(pk=response.json()['photos'][0]['id'])
        self.assertEqual(photo.group, 'Civil')
        self.assertEqual(Path(photo.original.path).read_bytes(), original)
        self.assertEqual(self.checklist.processing_revisions.count(), 0)
        self.assertEqual(self.checklist.photo_jobs.count(), 0)
        self.assertEqual(SurveyProcessingJob.objects.count(), 0)
        vision.assert_not_called()
        pipeline.upload_session(self.request(), self.checklist.pk, session.token)
        digest=self.client.get(reverse('photo_capture_state',args=[self.checklist.pk])).json()['digest']
        response = self.client.post(reverse('photo_capture_submit', args=[self.checklist.pk]),
            json.dumps({'uploads_finished': True,'expected_digest':digest}),content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.checklist.processing_revisions.get().processing_job.status, 'queued')
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, Checklist.Status.SUBMITTED)

    def test_opted_in_legacy_retry_cannot_start_ai_before_submission(self):
        retained = self.legacy_job()
        self.client.force_login(self.engineer)
        response = self.client.post(reverse('photo_retry', args=[self.checklist.pk, retained.pk]))
        self.assertEqual(response.status_code, 403, response.content)
        retained.refresh_from_db()
        self.assertEqual(retained.status, 'failed')
        self.assertEqual(retained.error, 'Retained failure')
        self.assertEqual(self.checklist.processing_revisions.count(), 0)

    def test_excluded_survey_keeps_authorized_reviewer_retry_contract(self):
        self.exclude_processing()
        retained = self.legacy_job()
        self.client.force_login(self.lead)
        response = self.client.post(reverse('photo_retry', args=[self.checklist.pk, retained.pk]))
        self.assertEqual(response.status_code, 200, response.content)
        retained.refresh_from_db()
        self.assertEqual(retained.status, 'queued')
        self.assertEqual(self.checklist.processing_revisions.count(), 0)

    def test_canonical_retry_reuses_the_failed_job_after_explicit_submission(self):
        revision, _ = pipeline.submit(self.request(), self.checklist.pk, True)
        job = revision.processing_job
        job.status = 'failed'
        job.error = 'Synthetic stopped worker'
        job.save(update_fields=['status', 'error'])
        # Retained service-level retry semantics survive the new HTTP policy.
        pipeline.retry(self.request(),self.checklist.pk,revision.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, 'queued')
        self.assertEqual(self.checklist.processing_revisions.count(), 1)
        self.assertEqual(SurveyProcessingJob.objects.count(), 1)

    def test_historical_photo_cache_does_not_enable_pre_submit_critical_ai(self):
        self.legacy_job('completed')
        self.client.force_login(self.lead)
        with patch('core.checklist_ai_review.inference_lease') as lease:
            response = self.client.post(reverse('checklist_ai_request', args=[self.checklist.pk]),
                '{}', content_type='application/json')
        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn('Submit this survey', response.json()['error'])
        lease.assert_not_called()
        self.assertEqual(self.checklist.ai_reviews.count(), 0)

    def test_queued_canonical_submission_cannot_be_bypassed_by_a_historical_cache(self):
        self.legacy_job('completed')
        pipeline.submit(self.request(), self.checklist.pk, True)
        self.client.force_login(self.lead)
        with patch('core.checklist_ai_review.inference_lease') as lease:
            response = self.client.post(reverse('checklist_ai_request', args=[self.checklist.pk]),
                '{}', content_type='application/json')
        self.assertEqual(response.status_code, 409, response.content)
        lease.assert_not_called()

    def test_additional_ai_review_can_start_after_current_canonical_analysis(self):
        self.ready()
        self.client.force_login(self.lead)
        from .local_ai import InferenceBusy
        with patch('core.checklist_ai_review.inference_lease', side_effect=InferenceBusy('Synthetic occupied lease')) as lease:
            response = self.client.post(reverse('checklist_ai_request', args=[self.checklist.pk]),
                '{}', content_type='application/json')
        self.assertEqual(response.status_code, 409, response.content)
        lease.assert_called_once()
        self.assertEqual(self.checklist.ai_reviews.count(), 0)

    def test_changed_inputs_require_resubmission_before_additional_ai(self):
        self.ready()
        self.legacy_job('completed')
        self.checklist.refresh_from_db()
        self.checklist.answer_data['custom']['contact'] = 'A changed field input'
        self.checklist.save(update_fields=['answer_data'])
        self.client.force_login(self.lead)
        with patch('core.checklist_ai_review.inference_lease') as lease:
            response = self.client.post(reverse('checklist_ai_request', args=[self.checklist.pk]),
                '{}', content_type='application/json')
        self.assertEqual(response.status_code, 409, response.content)
        lease.assert_not_called()

    def test_reviewed_submission_can_return_to_the_same_photo_workbench(self):
        revision = self.ready()
        self.accept_complete(revision)
        self.client.force_login(self.engineer)
        workbench = reverse('photo_workspace', args=[self.checklist.pk])
        response = self.client.post(reverse('custom_checklist_submit', args=[self.checklist.pk]),
            {'return_to': workbench})
        self.assertRedirects(response, workbench, fetch_redirect_response=False)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, Checklist.Status.SUBMITTED)
        self.assertEqual(self.checklist.quality_approval, {})

    def test_submission_never_redirects_to_an_external_return_url(self):
        self.exclude_processing()
        self.client.force_login(self.engineer)
        response = self.client.post(reverse('custom_checklist_submit', args=[self.checklist.pk]),
            {'return_to': 'https://example.invalid/collect'})
        self.assertRedirects(response, reverse('custom_checklist', args=[self.checklist.pk]),
            fetch_redirect_response=False)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, Checklist.Status.SUBMITTED)

    def test_unreviewed_submission_keeps_original_validation_and_redirect(self):
        self.client.force_login(self.engineer)
        response = self.client.post(reverse('custom_checklist_submit', args=[self.checklist.pk]),
            {'return_to': reverse('photo_workspace', args=[self.checklist.pk])})
        self.assertRedirects(response, reverse('custom_checklist', args=[self.checklist.pk]),
            fetch_redirect_response=False)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, Checklist.Status.DRAFT)
        self.assertEqual(self.checklist.processing_revisions.count(), 0)
