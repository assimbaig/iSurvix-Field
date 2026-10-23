"""Independent saved-record API checks against the integrated survey contract.

These tests do not substitute for the separately executed native vision/browser
pilot. Their explicitly labelled extracted records are deterministic test inputs;
authorization, persistence, integrity and exports use real Django services/files.
"""
import hashlib
import json
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import survey_processing as pipeline, test_survey_processing as fixtures
from .models import Checklist, ChecklistTemplate
from .survey_processing_models import (SurveyDocument, SurveyProcessingEvent,
    SurveyProcessingJob, SurveyProcessingResult, SurveySourceAnalysis)


@override_settings(SECRET_KEY='independent-synthetic-integrated-qa', ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentIntegratedQATests(TestCase):
    setUp = fixtures.SurveyProcessingTests.setUp
    person = fixtures.SurveyProcessingTests.person
    add_photo = fixtures.SurveyProcessingTests.add_photo
    request = fixtures.SurveyProcessingTests.request

    def endpoint(self, name='survey_processing_action'):
        return reverse(name, args=[self.checklist.pk])

    def saved_result(self, right_only_branding=False):
        """Create explicit synthetic extracted records, not an inference claim."""
        self.schema['sections'][1]['fields'][0]['unit'] = 'm'
        measured_template = ChecklistTemplate.objects.create(name='Independent synthetic measured template',
            definition=deepcopy(self.schema), published=True, checklist_required=True)
        self.checklist = Checklist.objects.create(project=self.project, user=self.engineer,
            quality_reviewer=self.quality, site_id='SYNTHETIC-INDEPENDENT-MEASURED',
            checklist_template=measured_template, answer_data={'custom': {'contact': 'Synthetic measured contact'}})
        self.photo, self.photo2 = self.add_photo('orange'), self.add_photo('purple')
        if right_only_branding:
            self.checklist.branding_snapshot = {'company_logo': self.photo2.original.name, 'clients': [
                {'name': 'Synthetic left without logo', 'logo': ''},
                {'name': 'Synthetic right client', 'logo': self.photo.original.name}]}
            self.checklist.save(update_fields=['branding_snapshot'])
        self.client.force_login(self.engineer)
        # Build retained pre-category history through its original service.
        revision,created=pipeline.submit(self.request(),self.checklist.pk,True)
        self.assertTrue(created)
        finding = {'finding_key': 'independent-synthetic-record-1', 'field_hint': 'tower_height',
            'category': 'measurement', 'component': 'tower', 'value': '30', 'unit': 'm',
            'basis': 'recorded', 'evidence_quote': 'Synthetic fixture measured record: 30 m',
            'confidence': 'medium', 'verification_status': 'needs_review', 'measured': False,
            'source_id': f'photo:{self.photo.pk}', 'reference': 'original'}
        for photo in (self.photo, self.photo2):
            payload = {'source_id': f'photo:{photo.pk}', 'reference': 'original', 'findings': []}
            SurveySourceAnalysis.objects.create(revision=revision, source_id=payload['source_id'],
                payload=payload, digest=pipeline.digest(payload))
        payload = pipeline.prepare_checklist(revision.snapshot, {'findings': [finding],
            'missing': [], 'conflicts': [], 'suggested_items': ['Synthetic supplemental recorded label']})
        SurveyProcessingResult.objects.create(revision=revision, payload=payload, digest=pipeline.digest(payload))
        SurveyProcessingJob.objects.filter(revision=revision).update(status='ready_for_review')
        return revision

    def test_invalid_numeric_record_correction_cannot_poison_saved_package(self):
        revision = self.saved_result()
        before_events = revision.processing_events.count()
        with self.assertRaises(ValidationError):
            pipeline.review(self.request(),self.checklist.pk,revision.pk,'record',
                ids=['independent-synthetic-record-1'],corrections={'independent-synthetic-record-1':{'value':'30','unit':'V'}},
                reason='An incompatible unit must be rejected before append-only persistence.')
        self.assertEqual(revision.processing_events.count(), before_events)
        self.client.force_login(self.quality)
        state = self.client.get(self.endpoint('survey_processing_state'))
        self.assertEqual(state.status_code, 200, state.content)
        self.assertEqual(next(x for x in state.json()['active']['checklist_items'] if x['id'] == 'tower_height')['value'], '30')

    def test_duplicate_document_retry_at_capacity_is_idempotent(self):
        self.client.force_login(self.engineer)
        first = None
        for number in range(50):
            output = BytesIO()
            Image.new('RGB', (32, 24), (number, 40, 90)).save(output, 'PNG')
            raw = output.getvalue()
            document = SurveyDocument(checklist=self.checklist, uploaded_by=self.engineer,
                filename=f'synthetic-support-{number:02d}.png', content_type='image/png', size=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())
            document.original.save(document.filename, ContentFile(raw))
            first = first or document
        original_bytes = Path(first.original.path).read_bytes()
        response = self.client.post(self.endpoint(), {'action': 'upload_document',
            'files': [SimpleUploadedFile('renamed-retry.png', original_bytes, content_type='image/png')]})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.checklist.survey_documents.count(), 50)
        self.assertEqual(Path(first.original.path).read_bytes(), original_bytes)
        self.assertFalse(self.checklist.survey_upload_sessions.filter(finished_at__isnull=True).exists())

    def test_corrupt_document_batch_does_not_commit_valid_first_file(self):
        self.client.force_login(self.engineer)
        original = Path(self.photo.original.path).read_bytes()
        response = self.client.post(self.endpoint(), {'action': 'upload_document', 'files': [
            SimpleUploadedFile('valid-first.png', original, content_type='image/png'),
            SimpleUploadedFile('corrupt-second.pdf', b'corrupt PDF', content_type='application/pdf')]})
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(self.checklist.survey_documents.count(), 0)
        self.assertFalse(self.checklist.survey_upload_sessions.filter(finished_at__isnull=True).exists())

    def test_wrong_roles_cannot_mutate_or_complete_engineer_package(self):
        revision = self.saved_result()
        before = deepcopy(self.checklist.answer_data)
        event_count = SurveyProcessingEvent.objects.count()
        for actor in (self.admin, self.lead, self.quality, self.customer):
            self.client.force_login(actor)
            for values in [
                {'action': 'start_upload'}, {'action': 'submit', 'uploads_finished': 'true'},
                {'action': 'review', 'decision': 'accept', 'finding_ids': '["tower_height"]'},
                {'action': 'review', 'decision': 'engineer_complete'},
            ]:
                with self.subTest(role=actor.profile.role, action=values):
                    response = self.client.post(self.endpoint(), {**values, 'revision_id': revision.pk})
                    self.assertIn(response.status_code, (403, 404), response.content)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.answer_data, before)
        self.assertEqual(SurveyProcessingEvent.objects.count(), event_count)

    def test_section_lock_blocks_retained_service_accept_and_result_correction(self):
        revision = self.saved_result()
        self.checklist.section_approvals = {'measurements': {'name': 'Synthetic approved section'}}
        self.checklist.save(update_fields=['section_approvals'])
        for decision, ids, changes in [('accept', ['tower_height'], {}),
            ('correct', ['tower_height'], {'tower_height': '35'}),
            ('record', ['independent-synthetic-record-1'], {'independent-synthetic-record-1': {'value': '35', 'unit': 'm'}})]:
            with self.subTest(decision=decision):
                response = self.client.post(self.endpoint(), {'action': 'review', 'decision': decision,
                    'revision_id': revision.pk, 'finding_ids': json.dumps(ids), 'corrections': json.dumps(changes),
                    'reason': 'Attempt to bypass an existing human-approved section lock.'})
                self.assertEqual(response.status_code, 403, response.content)
                with self.assertRaises(ValidationError):
                    pipeline.review(self.request(),self.checklist.pk,revision.pk,decision,ids=ids,
                        corrections=changes,reason='Attempt to bypass an existing human-approved section lock.')
        self.assertEqual(revision.processing_events.count(), 1)  # original submission only

    def test_review_acceptance_does_not_silently_apply_answers(self):
        revision = self.saved_result()
        original = deepcopy(self.checklist.answer_data)
        for _ in range(2):
            pipeline.review(self.request(),self.checklist.pk,revision.pk,'accept',ids=['tower_height'])
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.answer_data, original)
        self.assertEqual(revision.processing_events.filter(action='accept').count(), 1)
        self.assertEqual(self.checklist.photo_evidence.filter(placements__status='confirmed').count(), 0)
        self.client.force_login(self.quality)
        self.assertTrue(next(x for x in self.client.get(self.endpoint('survey_processing_state')).json()['active']['checklist_items'] if x['id'] == 'tower_height')['accepted'])

    def test_right_only_snapshot_logo_reaches_correct_actual_pdf_and_dxf_slot(self):
        import ezdxf
        import pymupdf
        revision = self.saved_result(right_only_branding=True)
        asset = pipeline.render_drawing_set(revision, pipeline.reviewed_payload(revision))
        self.assertTrue(Path(asset.manifest['pdf']).is_file())
        with pymupdf.open(asset.manifest['pdf']) as pdf:
            self.assertEqual(len(pdf), len(asset.geometry['sheets']))
            for index, sheet in enumerate(asset.geometry['sheets']):
                logos = [x for x in sheet['entities'] if x['kind'] == 'image']
                self.assertEqual([x['sources'][0]['role'] for x in logos], ['company', 'partner'])
                partner = next(x for x in logos if x['sources'][0]['role'] == 'partner')
                self.assertEqual((partner['x'], partner['y']), (373, 43))
                self.assertEqual(len(pdf[index].get_images()), 2)
                drawing = ezdxf.readfile(asset.manifest['sheets'][index]['dxf'])
                self.assertFalse(drawing.audit().has_errors)
                inserted = list(drawing.modelspace().query('IMAGE'))
                self.assertEqual([(x.dxf.insert.x, x.dxf.insert.y) for x in inserted], [(337, 53), (373, 43)])
