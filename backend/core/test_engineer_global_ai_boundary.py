"""The current Engineer HTTP policy also covers retained, unmarked records."""
from pathlib import Path
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from . import test_survey_processing as fixtures
from .models import PhotoJob
from .survey_processing_models import SurveyProcessingJob


@override_settings(SECRET_KEY='isolated-global-engineer-ai-policy', ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EngineerGlobalAIBoundaryTests(TestCase):
    setUp = fixtures.SurveyProcessingTests.setUp
    person = fixtures.SurveyProcessingTests.person
    add_photo = fixtures.SurveyProcessingTests.add_photo
    request = fixtures.SurveyProcessingTests.request
    analysed = fixtures.SurveyProcessingTests.analysed
    processing = fixtures.SurveyProcessingTests.processing
    ready = fixtures.SurveyProcessingTests.ready

    def test_legacy_engineer_ai_mutations_are_denied_without_touching_retained_data(self):
        self.client.force_login(self.engineer)
        retained=PhotoJob.objects.create(checklist=self.checklist,requested_by=self.engineer,
            schema=self.schema,model='synthetic-retained-model',status='failed',error='Retained failure')
        retained.photos.add(self.photo)
        original=Path(self.photo.original.path).read_bytes()
        self.assertNotIn('category_intake_version',self.checklist.intake_metadata or {})
        routes=[('photo_enqueue',[self.checklist.pk]),('photo_retry',[self.checklist.pk,retained.pk]),
            ('photo_accept',[self.checklist.pk,999]),('photo_mapping',[self.checklist.pk]),
            ('checklist_ai_request',[self.checklist.pk]),
            ('evidence_learning_decide',[self.checklist.pk,999]),('evidence_learning_publish',[self.checklist.pk]),
            ('custom_checklist_upload',[self.checklist.pk,'manufacturer']),
            ('custom_checklist_photo_delete',[self.checklist.pk,'manufacturer',0])]
        with patch('core.checklist_ai_review.inference_lease') as inference:
            for route,args in routes:
                with self.subTest(route=route):
                    response=self.client.post(reverse(route,args=args),{},content_type='application/json')
                    self.assertEqual(response.status_code,403,response.content)
            for action in ['submit','retry','review','release']:
                response=self.client.post(reverse('survey_processing_action',args=[self.checklist.pk]),
                    {'action':action,'decision':'geometry','revision_id':999,'uploads_finished':'true'})
                self.assertEqual(response.status_code,403,response.content)
            inference.assert_not_called()
        retained.refresh_from_db();self.checklist.refresh_from_db()
        self.assertEqual((retained.status,retained.error),('failed','Retained failure'))
        self.assertEqual(self.checklist.processing_revisions.count(),0)
        self.assertEqual(SurveyProcessingJob.objects.count(),0)
        self.assertEqual(self.checklist.photo_jobs.count(),1)
        self.assertEqual(Path(self.photo.original.path).read_bytes(),original)

    def test_retained_ai_workspaces_redirect_to_actual_engineer_capture(self):
        self.client.force_login(self.engineer)
        capture=reverse('photo_workspace',args=[self.checklist.pk])
        for route in ['survey_processing_workspace','checklist_ai_review','evidence_learning','custom_checklist']:
            with self.subTest(route=route):
                self.assertRedirects(self.client.get(reverse(route,args=[self.checklist.pk])),capture,
                    fetch_redirect_response=False)
        response=self.client.get(capture)
        self.assertContains(response,'id="engineer-capture"')
        self.assertContains(response,'Submit to QA')
        self.assertNotContains(response,'AI Checklist &amp; Drawings')
        self.assertNotContains(response,'Accept selected')

    def test_retained_photo_state_contains_capture_not_ai_acceptance_controls(self):
        self.client.force_login(self.engineer)
        response=self.client.get(reverse('photo_state',args=[self.checklist.pk]))
        self.assertEqual(response.status_code,200,response.content)
        self.assertIn('photos',response.json())
        for key in ['drafts','mappings','field_catalog','evidence_analysis']:
            self.assertNotIn(key,response.json())

    def test_legacy_ai_read_endpoints_deny_engineer_but_preserve_original_and_preview(self):
        from .photo_service import prepare_image
        original=Path(self.photo.original.path).read_bytes()
        _,preview,_,_,_=prepare_image(SimpleUploadedFile(self.photo.filename,original,content_type='image/png'))
        self.photo.preview.save('synthetic-preview.jpg',ContentFile(preview))
        revision=self.ready()
        snapshot=revision.snapshot.copy()
        self.assertNotIn('category_intake_version',snapshot)
        self.assertTrue(revision.processing_result.payload['findings'])
        self.client.force_login(self.engineer)
        for name in ['survey_processing_state','survey_processing_progress','checklist_ai_state',
                     'photo_report','photo_fast_state','evidence_learning_state']:
            with self.subTest(route=name):
                response=self.client.get(reverse(name,args=[self.checklist.pk]))
                self.assertEqual(response.status_code,403,response.content)
                self.assertNotIn(b'SyntheticCo',response.content)
        for variant in ['original','preview']:
            response=self.client.get(reverse('photo_evidence',args=[self.checklist.pk,self.photo.pk,variant]))
            self.assertEqual(response.status_code,200)
            expected=self.photo.original if variant=='original' else self.photo.preview
            self.assertEqual(b''.join(response.streaming_content),Path(expected.path).read_bytes())
            response.close()
        state=self.client.get(reverse('photo_capture_state',args=[self.checklist.pk]))
        self.assertEqual(state.status_code,200)
        self.assertNotIn('findings',state.json())
        self.client.force_login(self.quality)
        permitted=self.client.get(reverse('survey_processing_state',args=[self.checklist.pk]))
        self.assertEqual(permitted.status_code,200,permitted.content)
        self.assertIn(b'SyntheticCo',permitted.content)
        revision.refresh_from_db()
        self.assertEqual(revision.snapshot,snapshot)
