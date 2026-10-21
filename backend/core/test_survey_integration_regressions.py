"""Saved-record regressions for integrated survey boundaries and safe retries.

Inference fault injection tests below exercise queue repair only; they do not
claim a native model benchmark. The separate browser pilot exercises Ollama.
"""
import hashlib
import html
import json
import re
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import survey_processing as service, test_survey_processing as fixtures
from .models import Checklist
from .survey_processing_models import SurveyProcessingEvent, SurveyProcessingJob


@override_settings(SECRET_KEY='isolated-integrated-survey-regressions', ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SurveyIntegrationRegressionTests(TestCase):
    setUp = fixtures.SurveyProcessingTests.setUp
    person = fixtures.SurveyProcessingTests.person
    request = fixtures.SurveyProcessingTests.request
    add_photo = fixtures.SurveyProcessingTests.add_photo
    analysed = fixtures.SurveyProcessingTests.analysed
    processing = fixtures.SurveyProcessingTests.processing
    ready = fixtures.SurveyProcessingTests.ready
    keyed_ready = fixtures.SurveyProcessingTests.keyed_ready

    def independent_submission(self, *, qualified=False, coordinates=None):
        from .models import WorkflowTemplateQualification
        from .roadmap_service import definition_digest
        self.checklist.governance_mode = Checklist.GovernanceMode.INDEPENDENT
        self.checklist.coordinate_reference = coordinates or {}
        self.checklist.save(update_fields=['governance_mode', 'coordinate_reference'])
        if qualified:
            WorkflowTemplateQualification.objects.create(project=self.project, template=self.template,
                workflow_type=self.checklist.workflow_type, definition_digest=definition_digest(self.schema),
                criteria_reference='Explicit synthetic qualification criteria', inspection_method='Synthetic label review',
                reviewed_by=self.lead, reason='Isolated qualification gate fixture')
        self.client.force_login(self.engineer)
        return self.client.post(reverse('survey_processing_action', args=[self.checklist.pk]),
            {'action': 'submit', 'uploads_finished': 'true'})

    def test_ai_submit_reuses_existing_exact_template_qualification_gate_before_queue(self):
        response = self.independent_submission(coordinates={'source': 'Synthetic measured record', 'crs': 'EPSG:4326'})
        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn('technical applicability', response.json()['error'])
        self.assertEqual(self.checklist.processing_revisions.count(), 0)
        self.assertEqual(SurveyProcessingJob.objects.count(), 0)

    def test_ai_submit_reuses_existing_recorded_coordinate_gate_before_queue(self):
        response = self.independent_submission(qualified=True)
        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn('coordinate source and datum/CRS', response.json()['error'])
        self.assertEqual(self.checklist.processing_revisions.count(), 0)
        self.assertEqual(SurveyProcessingJob.objects.count(), 0)

    def test_ai_submit_queues_when_existing_governed_input_gates_are_satisfied(self):
        response = self.independent_submission(qualified=True,
            coordinates={'source': 'Explicit synthetic recorded coordinates', 'crs': 'EPSG:4326'})
        self.assertEqual(response.status_code, 201, response.content)
        revision = self.checklist.processing_revisions.get()
        self.assertEqual(revision.processing_job.status, 'queued')
        self.assertEqual(revision.snapshot['coordinates'], self.checklist.coordinate_reference)
        self.assertEqual(self.checklist.photo_evidence.count(), 2)

    def photo_page(self):
        self.client.force_login(self.engineer)
        response = self.client.get(reverse('photo_workspace', args=[self.checklist.pk]))
        self.assertEqual(response.status_code, 200, response.content)
        content = html.unescape(response.content.decode())
        button = re.search(r'<button[^>]*id="upload-button"[^>]*>(.*?)</button>', content, re.S)
        self.assertIsNotNone(button)
        return response, re.sub(r'<[^>]+>', '', button.group(1)).strip(), content

    def test_opted_in_photo_upload_copy_requires_explicit_ai_submission(self):
        response, button, content = self.photo_page()
        self.assertTrue(response.context['checklist_processing_enabled'])
        self.assertEqual(button, 'Upload photos')
        self.assertIn('AI Checklist & Drawings', content)
        self.assertIn('Analysis starts after you submit this survey', content)
        self.assertNotIn('Upload & analyze this group', button)

    def test_opted_in_survey_cannot_create_a_disconnected_legacy_photo_job(self):
        from .models import PhotoJob
        self.client.force_login(self.engineer)
        retained = PhotoJob.objects.create(checklist=self.checklist, requested_by=self.engineer,
            schema=self.checklist.schema_snapshot, model='synthetic-retained-historical-job')
        retained.photos.add(self.photo)
        before = {photo.pk: Path(photo.original.path).read_bytes() for photo in [self.photo, self.photo2]}
        response = self.client.post(reverse('photo_enqueue', args=[self.checklist.pk]),
            json.dumps({'photo_ids': [self.photo.pk, self.photo2.pk]}), content_type='application/json')
        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn('AI Checklist & Drawings', response.json()['error'])
        self.assertEqual(self.checklist.photo_jobs.count(), 1)
        retained.refresh_from_db()
        self.assertEqual(retained.status, 'queued')
        self.assertEqual(list(retained.photos.values_list('pk', flat=True)), [self.photo.pk])
        self.assertEqual(self.checklist.processing_revisions.count(), 0)
        for photo in [self.photo, self.photo2]:
            self.assertEqual(Path(photo.original.path).read_bytes(), before[photo.pk])

    def test_excluded_survey_keeps_existing_upload_and_analyse_copy(self):
        from .models import ChecklistTemplate
        excluded = ChecklistTemplate.objects.create(name='Synthetic excluded photo workflow', definition=self.schema,
            published=True, checklist_required=False)
        self.checklist.checklist_template = excluded
        self.checklist.save(update_fields=['checklist_template'])
        response, button, _ = self.photo_page()
        self.assertFalse(response.context['checklist_processing_enabled'])
        self.assertEqual(button, 'Upload & analyze this group')

    def test_both_inspection_modules_keep_existing_photo_workflow_copy(self):
        from .models import Project, Profile
        for workflow in [Checklist.WorkflowType.TELECOM_INSPECTION, Checklist.WorkflowType.CONSTRUCTION_INSPECTION]:
            with self.subTest(workflow=workflow):
                if workflow == Checklist.WorkflowType.CONSTRUCTION_INSPECTION:
                    project = Project.objects.create(name='Synthetic construction photo workflow', company=self.company,
                        industry=Project.Industry.CONSTRUCTION, checklist_template=self.template)
                    self.engineer = self.person('construction_copy', Profile.Roles.ENGINEER, project)
                    self.checklist = Checklist.objects.create(project=project, user=self.engineer,
                        site_id='SYNTHETIC-CONSTRUCTION-PHOTOS', workflow_type=workflow)
                else:
                    self.checklist.workflow_type = workflow
                    self.checklist.save(update_fields=['workflow_type'])
                response, button, _ = self.photo_page()
                self.assertFalse(response.context['checklist_processing_enabled'])
                self.assertEqual(button, 'Upload & analyze this group')

    def test_right_only_branding_stays_in_right_output_slot(self):
        self.checklist.branding_snapshot = {'clients': [
            {'name': 'Left without logo', 'logo': ''},
            {'name': 'Right assigned client', 'logo': self.photo.original.name}],
            'company_logo': self.photo2.original.name}
        self.checklist.save(update_fields=['branding_snapshot'])
        revision, _ = service.submit(self.request(), self.checklist.pk, True)
        branding = service.drawing_branding(revision)
        self.assertNotIn('client_logo', branding)
        self.assertEqual(branding['partner_logo'], self.photo.original.path)
        self.assertEqual(branding['company_logo'], self.photo2.original.path)

    def test_accepted_numeric_units_survive_real_pdf_dxf_and_shared_geometry(self):
        import ezdxf
        import pymupdf
        revision, _ = service.submit(self.request(), self.checklist.pk, True)
        stack, _, _ = self.processing()
        service.process_next()
        stack.close()  # Actual exporters below, no mocked geometry or renderer.
        service.review(self.request(), self.checklist.pk, revision.pk, 'correct', ids=['tower_height'],
                       corrections={'tower_height': '1.2'}, reason='Synthetic recorded 1.2 m reviewed explicitly')
        payload = service.reviewed_payload(revision)
        item = next(i for i in payload['checklist_items'] if i['id'] == 'tower_height')
        self.assertEqual(item['unit'], 'm')
        asset = service.render_drawing_set(revision, payload)
        answers = [row['answer'] for sheet in asset.geometry['sheets'] for row in sheet.get('findings', [])]
        self.assertTrue(any('1.2 m' in answer for answer in answers), answers)
        with pymupdf.open(asset.manifest['pdf']) as pdf:
            self.assertIn('1.2 m', ''.join(page.get_text() for page in pdf))
        dxf_text = []
        for sheet in asset.manifest['sheets']:
            drawing = ezdxf.readfile(sheet['dxf'])
            self.assertFalse(drawing.audit().has_errors)
            dxf_text.extend(entity.dxf.text for entity in drawing.modelspace().query('TEXT'))
        self.assertTrue(any('1.2 m' in text for text in dxf_text))

    def test_additional_acceptance_is_idempotent_in_saved_events_and_replay(self):
        revision = self.ready()
        proposals = service.reviewed_payload(revision)['suggested_items']
        self.assertTrue(proposals)
        for _ in range(2):
            service.review(self.request(), self.checklist.pk, revision.pk, 'accept_additional',
                           ids=[0, 0], reason='Reviewed this supplemental label request')
        self.assertEqual(revision.processing_events.filter(action='accept_additional').count(), 1)
        self.assertEqual(service.reviewed_payload(revision)['accepted_additional_items'], [proposals[0]])
        # A legacy duplicate event must not duplicate the replayed accepted result.
        SurveyProcessingEvent.objects.create(revision=revision, actor=self.engineer, action='accept_additional',
                                             payload={'items': [proposals[0]]})
        self.assertEqual(service.reviewed_payload(revision)['accepted_additional_items'], [proposals[0]])

    def test_invalid_additional_indices_leave_no_partial_acceptance(self):
        revision = self.ready()
        for ids in [[0, 999], ['0'], {}, [True]]:
            with self.subTest(ids=ids), self.assertRaises(ValidationError):
                service.review(self.request(), self.checklist.pk, revision.pk, 'accept_additional',
                               ids=ids, reason='Invalid selection must fail atomically')
        self.assertFalse(revision.processing_events.filter(action='accept_additional').exists())

    def test_repeated_field_acceptance_has_one_saved_decision(self):
        revision = self.ready()
        for _ in range(2):
            service.review(self.request(), self.checklist.pk, revision.pk, 'accept', ids=['manufacturer'])
        self.assertEqual(revision.processing_events.filter(action='accept').count(), 1)

    def test_foreign_or_missing_revision_is_404_for_review_and_retry(self):
        revision = self.ready()
        other = Checklist.objects.create(project=self.project, user=self.engineer,
            quality_reviewer=self.quality, site_id='SYNTHETIC-FOREIGN-REVISION',
            answer_data={'custom': {'contact': 'Different immutable submission'}})
        self.client.force_login(self.engineer)
        action = reverse('survey_processing_action', args=[other.pk])
        for data in [
            {'action': 'retry', 'revision_id': revision.pk},
            {'action': 'review', 'revision_id': revision.pk, 'decision': 'accept', 'finding_ids': '["manufacturer"]'},
        ]:
            with self.subTest(action=data['action']):
                self.assertEqual(self.client.post(action, data).status_code, 404)

    def test_malformed_correction_object_is_a_handled_saved_record_error(self):
        revision = self.ready()
        self.client.force_login(self.engineer)
        action = reverse('survey_processing_action', args=[self.checklist.pk])
        result = self.client.post(action, {'action': 'review', 'revision_id': revision.pk,
            'decision': 'correct', 'finding_ids': '["manufacturer"]', 'corrections': '[]', 'reason': 'Bad shape'})
        self.assertEqual(result.status_code, 409)
        self.assertIn('correction object', result.json()['error'])
        self.assertFalse(revision.processing_events.filter(action='correct').exists())

    def test_extracted_record_correction_cannot_edit_approved_section(self):
        revision = self.keyed_ready()
        self.checklist.section_approvals = {'measurements': {'name': 'Existing human approval'}}
        self.checklist.save(update_fields=['section_approvals'])
        with self.assertRaisesMessage(ValidationError, 'approved and locked'):
            service.review(self.request(), self.checklist.pk, revision.pk, 'record',
                ids=[f'photo:{self.photo.pk}:finding:2'],
                corrections={f'photo:{self.photo.pk}:finding:2': {'value': '35', 'unit': 'm'}},
                reason='This approved section must stay locked')
        self.assertFalse(revision.processing_events.filter(action='record').exists())

    def test_record_correction_preserves_source_unit_and_converts_field_value(self):
        self.schema['sections'][1]['fields'][0]['unit'] = 'm'
        self.checklist.schema_snapshot = deepcopy(self.schema)
        self.checklist.save(update_fields=['schema_snapshot'])
        # Same controlling published revision, changed only in this synthetic setup.
        from .models import ChecklistTemplate
        ChecklistTemplate.objects.filter(pk=self.template.pk).update(definition=self.schema)
        revision = self.keyed_ready()
        key = f'photo:{self.photo.pk}:finding:2'
        service.review(self.request(), self.checklist.pk, revision.pk, 'record', ids=[key],
            corrections={key: {'value': '35000', 'unit': 'mm'}}, reason='Verified recorded millimetres')
        payload = service.reviewed_payload(revision)
        finding = next(f for f in payload['findings'] if f['finding_key'] == key)
        item = next(i for i in payload['checklist_items'] if i['id'] == 'tower_height')
        self.assertEqual((finding['value'], finding['unit']), ('35000', 'mm'))
        self.assertEqual((item['value'], item['unit']), ('35', 'm'))
        self.assertFalse(item['accepted'])
        with self.assertRaises(ValidationError):
            service.review(self.request(), self.checklist.pk, revision.pk, 'record', ids=[key],
                corrections={key: {'value': '35000', 'unit': 'V'}}, reason='Dimensionally invalid correction')
        # Pre-existing bad-unit corrections are kept as audit evidence and remain
        # recoverable; replay must not make the entire saved workspace fail.
        SurveyProcessingEvent.objects.create(revision=revision, actor=self.engineer, action='record',
            reason='Legacy invalid unit event', payload={'findings': {key: {'value': '30', 'unit': 'V'}}})
        legacy = service.reviewed_payload(revision)
        held = next(i for i in legacy['checklist_items'] if i['id'] == 'tower_height')
        self.assertIsNone(held['value'])
        self.assertTrue(held['conflict'])
        service.review(self.request(), self.checklist.pk, revision.pk, 'record', ids=[key],
            corrections={key: {'value': '35', 'unit': 'm'}}, reason='Corrected legacy unit transcription')
        recovered = next(i for i in service.reviewed_payload(revision)['checklist_items'] if i['id'] == 'tower_height')
        self.assertEqual(recovered['value'], '35')
        self.assertFalse(recovered['conflict'])

    def test_explicit_structured_human_record_corrections_remain_supported(self):
        revision = self.keyed_ready()
        key = f'photo:{self.photo.pk}:finding:1'
        value = {'label': 'Synthetic verified label', 'recorded_parts': ['A', 'B']}
        service.review(self.request(), self.checklist.pk, revision.pk, 'record', ids=[key],
            corrections={key: {'value': value, 'unit': ''}}, reason='Human records structured label details')
        payload = service.reviewed_payload(revision)
        finding = next(f for f in payload['findings'] if f['finding_key'] == key)
        self.assertEqual(finding['value'], value)
        self.assertEqual(finding['verification_status'], 'confirmed')
        self.checklist.refresh_from_db()
        self.assertNotIn('manufacturer', self.checklist.answer_data['custom'])

    def test_busy_inference_yields_to_worker_poll_and_terminal_lease_is_cleared(self):
        from .local_ai import InferenceBusy
        revision, _ = service.submit(self.request(), self.checklist.pk, True)
        self.processing()
        with patch('core.photo_service.verify_vision', side_effect=InferenceBusy('Synthetic contention')):
            self.assertFalse(service.process_next())
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status, 'queued')
        self.assertIsNone(revision.processing_job.lease_until)
        self.assertTrue(service.process_next())
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status, 'ready_for_review')
        self.assertIsNone(revision.processing_job.lease_until)
        self.assertEqual(revision.processing_job.lease_owner, '')

    def test_interrupted_active_job_without_a_lease_can_resume(self):
        revision, _ = service.submit(self.request(), self.checklist.pk, True)
        SurveyProcessingJob.objects.filter(revision=revision).update(status='preparing_checklist', lease_until=None)
        claimed = service.claim()
        self.assertEqual(claimed.revision_id, revision.pk)
        self.assertTrue(claimed.lease_owner)
        self.assertIsNotNone(claimed.lease_until)

    def test_two_hundred_saved_photo_uploads_are_bounded_and_originals_preserved(self):
        self.client.force_login(self.engineer)
        url = reverse('photo_upload', args=[self.checklist.pk])
        # The fixture already has two photos. Add 198 distinct real PNG files.
        expected = {}
        for start in range(0, 198, 20):
            files = []
            for index in range(start, min(start + 20, 198)):
                buffer = BytesIO()
                Image.new('RGB', (48, 32), (index, 23, 150)).save(buffer, 'PNG')
                raw = buffer.getvalue()
                filename = f'synthetic-bounded-{index:03d}.png'
                expected[filename] = hashlib.sha256(raw).hexdigest()
                files.append(SimpleUploadedFile(filename, raw, content_type='image/png'))
            response = self.client.post(url, {'group': 'Civil', 'files': files})
            self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.checklist.photo_evidence.count(), 200)
        for photo in self.checklist.photo_evidence.filter(filename__startswith='synthetic-bounded-'):
            self.assertEqual(hashlib.sha256(Path(photo.original.path).read_bytes()).hexdigest(), expected[photo.filename])
            self.assertTrue(photo.preview)
            self.assertFalse(photo.metadata.get('gps'))
        revision, created = service.submit(self.request(), self.checklist.pk, True)
        self.assertTrue(created)
        self.assertEqual(len(revision.snapshot['photos']), 200)
        self.assertEqual(revision.processing_job.total, 200)
        # Duplicate bytes reuse one saved source; a corrupt batch saves no input.
        example = self.checklist.photo_evidence.filter(filename__startswith='synthetic-bounded-').first()
        response = self.client.post(url, {'group': 'Civil', 'files': [SimpleUploadedFile('renamed-duplicate.png', Path(example.original.path).read_bytes())]})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['photos'][0]['duplicate'])
        bad = self.client.post(url, {'group': 'Civil', 'files': [SimpleUploadedFile('corrupt.png', b'not an image')]})
        self.assertEqual(bad.status_code, 400)
        too_many = self.client.post(url, {'group': 'Civil', 'files': [SimpleUploadedFile(f'{i}.png', b'not an image') for i in range(21)]})
        self.assertEqual(too_many.status_code, 400)
        self.assertEqual(self.checklist.photo_evidence.count(), 200)


class NumericEvidenceRegressionTests(TestCase):
    def test_explicit_stable_field_binding_does_not_spill_into_identical_labels(self):
        snapshot = {'site_id': 'SYNTHETIC-BINDING', 'answers': {'custom': {}}, 'schema': {'sections': [
            {'id': 'cabinet', 'title': 'Cabinet', 'fields': [
                {'id': 'cabinet_height', 'label': 'Cabinet height', 'type': 'number', 'unit': 'm'},
                {'id': 'alternate_height', 'label': 'Cabinet height', 'type': 'number', 'unit': 'm'}]}]}}
        result = service.prepare_checklist(snapshot, {'findings': [
            {'field_hint': 'cabinet_height', 'component': 'cabinet', 'category': 'measurement',
             'value': 2, 'unit': 'm', 'basis': 'recorded', 'evidence_quote': 'Synthetic recorded 2 m',
             'confidence': 'high', 'source_id': 'photo:1', 'reference': 'original'}]})
        first, other = result['checklist_items']
        self.assertEqual(first['value'], '2')
        self.assertEqual(first['sources'], [{'source_id': 'photo:1', 'reference': 'original'}])
        self.assertIsNone(other['value'])
        self.assertEqual(other['status'], 'Missing')
        self.assertEqual(other['sources'], [])

    def package(self, observations, reported=None, unit='m'):
        snapshot = {'site_id': 'SYNTHETIC-MEASURED', 'schema': {'sections': [{'id': 'measured', 'title': 'Measured',
            'fields': [{'id': 'height', 'label': 'Recorded tower height', 'type': 'number', 'unit': unit}]}]},
            'answers': {'custom': {} if reported is None else {'height': reported}}}
        reconciliation = {'findings': [dict(field_hint='height', category='measurement', component='tower',
            basis='recorded', evidence_quote='Synthetic recorded measurement', confidence='medium',
            source_id=f'photo:{index}', reference='original', **entry) for index, entry in enumerate(observations, 1)],
            'conflicts': [], 'missing': [], 'suggested_items': []}
        before = deepcopy(reconciliation)
        payload = service.prepare_checklist(snapshot, reconciliation)
        self.assertEqual(reconciliation, before)
        return payload, payload['checklist_items'][0]

    def test_dimensionally_compatible_units_convert_to_selected_field_unit(self):
        payload, item = self.package([{'value': 30000, 'unit': 'mm'}, {'value': 30, 'unit': 'm'}], reported='30')
        self.assertEqual(item['value'], '30')
        self.assertEqual(item['unit'], 'm')
        self.assertFalse(item['conflict'])
        self.assertEqual(payload['missing'], [])

    def test_unsupported_or_missing_units_are_withheld_instead_of_mislabelled(self):
        for unit in ['', 'V', 'furlong']:
            with self.subTest(unit=unit):
                payload, item = self.package([{'value': 30, 'unit': unit}])
                self.assertIsNone(item['value'])
                self.assertEqual(item['status'], 'Missing')
                self.assertTrue(payload['missing'])
                self.assertEqual(payload['findings'][0]['value'], 30)

    def test_different_converted_values_are_not_silently_selected(self):
        payload, item = self.package([{'value': 30000, 'unit': 'mm'}, {'value': 35, 'unit': 'm'}])
        self.assertTrue(item['conflict'])
        self.assertIsNone(item['value'])
        self.assertTrue(payload['conflicts'])

    def test_unit_conversion_preserves_recorded_decimal_precision(self):
        value = '123456789012345678901234567890.123456'
        _, item = self.package([{'value': value, 'unit': 'mm'}])
        self.assertEqual(item['value'], '123456789012345678901234567.890123456')

    def test_compact_huge_exponents_are_withheld_before_expanding_a_number(self):
        for unit in ['m', 'mm']:
            with self.subTest(unit=unit):
                payload, item = self.package([{'value': '1e99999999', 'unit': unit}])
                self.assertIsNone(item['value'])
                self.assertTrue(payload['missing'])
