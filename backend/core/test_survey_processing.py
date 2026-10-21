"""Disposable integration tests for opt-in survey AI packages and human release."""
import hashlib
import json
import tempfile
from contextlib import ExitStack, nullcontext
from copy import deepcopy
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.http import Http404
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import Checklist, ChecklistTemplate, Company, PhotoEvidence, Profile, Project
from .survey_processing_models import (SurveyDrawingSet, SurveyProcessingEvent, SurveyProcessingJob,
    SurveyProcessingResult, SurveyProcessingRevision, SurveySourceAnalysis)
from . import survey_processing as service


@override_settings(SECRET_KEY='isolated-survey-processing-tests', ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SurveyProcessingTests(TestCase):
    def setUp(self):
        runtime = Path(__file__).resolve().parents[2] / '.local' / 'tmp'
        runtime.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='survey-ai-test-', dir=runtime)
        self.addCleanup(temporary.cleanup)
        storage = override_settings(MEDIA_ROOT=temporary.name)
        storage.enable()
        self.addCleanup(storage.disable)
        self.company = Company.objects.create(name='Synthetic survey company')
        self.schema = {'title': 'Synthetic survey checklist', 'sections': [
            {'id': 'general', 'title': 'General', 'fields': [
                {'id': 'site_id', 'label': 'Site ID', 'type': 'text', 'system': 'site_id', 'required': True},
                {'id': 'contact', 'label': 'Survey contact', 'type': 'text', 'survey_input': True, 'required': True},
                {'id': 'manufacturer', 'label': 'Cabinet manufacturer', 'type': 'text'}]},
            {'id': 'measurements', 'title': 'Measurements', 'fields': [
                {'id': 'tower_height', 'label': 'Recorded tower height', 'type': 'number'}]},
            {'id': 'condition', 'title': 'Condition', 'fields': [
                {'id': 'cabinet_condition', 'label': 'Cabinet inspection result', 'type': 'inspection'}]},
        ]}
        self.template = ChecklistTemplate.objects.create(name='Synthetic survey', definition=self.schema,
                                                          published=True, checklist_required=True)
        self.project = Project.objects.create(name='Synthetic survey project', company=self.company,
                                               checklist_template=self.template)
        self.engineer = self.person('engineer', Profile.Roles.ENGINEER)
        self.quality = self.person('quality', Profile.Roles.QUALITY_ENGINEER)
        self.lead = self.person('lead', Profile.Roles.TEAM_LEAD)
        self.customer = self.person('client', Profile.Roles.CLIENT)
        self.admin = self.person('admin', Profile.Roles.ADMIN)
        self.project.administrator = self.admin
        self.project.save(update_fields=['administrator'])
        self.checklist = Checklist.objects.create(project=self.project, user=self.engineer,
            quality_reviewer=self.quality, site_id='SYNTHETIC-AI-001', answer_data={'custom': {'contact': 'Synthetic contact'}})
        self.photo = self.add_photo('blue')
        self.photo2 = self.add_photo('green')

    def person(self, name, role, project=None):
        user = User.objects.create_user('survey_ai_' + name)
        user.profile.role = role
        user.profile.company = (project or self.project).company
        user.profile.project = project or self.project
        user.profile.save()
        return user

    def request(self, actor=None):
        return SimpleNamespace(user=actor or self.engineer)

    def add_photo(self, color):
        buffer = BytesIO()
        Image.new('RGB', (60, 40), color).save(buffer, 'PNG')
        raw = buffer.getvalue()
        photo = PhotoEvidence.objects.create(checklist=self.checklist, uploaded_by=self.engineer,
                    filename=f'synthetic-{color}.png', sha256=hashlib.sha256(raw).hexdigest())
        photo.original.save(photo.filename, ContentFile(raw))
        return photo

    def analysed(self, source, model, **kwargs):
        return {'source_id': source['source_id'], 'source_type': source['source_type'],
            'sha256': source['sha256'], 'reference': source['reference'], 'model': model,
            'verification_status': 'needs_review', 'missing': [], 'conflicts': [],
            'suggested_items': ['Record an additional mounting label'], 'findings': [
                {'field_hint': 'manufacturer', 'category': 'equipment', 'component': 'cabinet',
                 'value': 'SyntheticCo', 'unit': '', 'basis': 'recorded', 'evidence_quote': 'SyntheticCo',
                 'confidence': 'high', 'verification_status': 'needs_review', 'measured': False,
                 'source_id': source['source_id'], 'reference': source['reference']},
                {'field_hint': 'tower_height', 'category': 'measurement', 'component': 'tower',
                 'value': '30', 'unit': 'm', 'basis': 'recorded', 'evidence_quote': '30 m',
                 'confidence': 'medium', 'verification_status': 'needs_review', 'measured': False,
                 'source_id': source['source_id'], 'reference': source['reference']},
            ]}

    def processing(self, analyse=None, render_failure=None):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch('core.photo_service.verify_vision', return_value={'capabilities': ['vision'], 'digest': 'synthetic-model'}))
        stack.enter_context(patch('core.photo_queue.photo_inference_lease', side_effect=lambda: nullcontext(lambda: None)))
        stack.enter_context(patch('core.photo_queue.inference_lease', side_effect=lambda *args, **kwargs: nullcontext(lambda: None)))
        vision = stack.enter_context(patch('core.survey_evidence.analyse_source', side_effect=analyse or self.analysed))
        stack.enter_context(patch('core.survey_drawings.build_geometry', return_value={'sheets': [], 'site_id': 'SYNTHETIC-AI-001'}))
        renderer = stack.enter_context(patch('core.survey_drawings.render_outputs',
            return_value={'pdf': 'synthetic-package.pdf', 'dxf': 'synthetic-package.dxf', 'previews': []}, side_effect=render_failure))
        return stack, vision, renderer

    def ready(self):
        revision, created = service.submit(self.request(), self.checklist.pk, True)
        self.assertTrue(created)
        self.processing()
        self.assertTrue(service.process_next())
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status, 'ready_for_review', revision.processing_job.error)
        return revision

    def accept_complete(self, revision):
        service.review(self.request(), self.checklist.pk, revision.pk, 'accept',
                       ids=['site_id', 'contact', 'manufacturer', 'tower_height'])
        service.review(self.request(), self.checklist.pk, revision.pk, 'reject',
                       ids=['cabinet_condition'], reason='No supported condition evidence; explicitly unresolved.')
        service.review(self.request(), self.checklist.pk, revision.pk, 'engineer_complete')

    def pristine(self):
        self.checklist.refresh_from_db()
        return deepcopy((self.checklist.answer_data, self.checklist.schema_snapshot,
            self.checklist.section_approvals, self.checklist.quality_approval,
            self.checklist.client_approval, self.checklist.review_history, self.checklist.status))

    def test_only_explicit_checklist_required_survey_is_in_scope(self):
        self.assertTrue(service.enabled(self.checklist))
        for workflow in [Checklist.WorkflowType.TELECOM_INSPECTION, Checklist.WorkflowType.CONSTRUCTION_INSPECTION]:
            self.checklist.workflow_type = workflow
            self.assertFalse(service.enabled(self.checklist))
        self.checklist.workflow_type = Checklist.WorkflowType.TELECOM_SURVEY
        excluded = ChecklistTemplate.objects.create(name='Excluded survey', definition=self.schema,
                                                     published=True, checklist_required=False)
        self.checklist.checklist_template = excluded
        self.assertFalse(service.enabled(self.checklist))
        self.checklist.save(update_fields=['workflow_type', 'checklist_template'])
        with self.assertRaises(Http404):
            service.submit(self.request(), self.checklist.pk, True)
        self.assertEqual(SurveyProcessingRevision.objects.count(), 0)

    def test_access_rechecks_owner_active_account_company_and_project(self):
        for actor in [AnonymousUser(), self.quality, self.lead, self.customer, self.admin]:
            with self.subTest(actor=str(actor)):
                with self.assertRaises((Http404, PermissionDenied)):
                    service.submit(self.request(actor), self.checklist.pk, True)
        outsider_company = Company.objects.create(name='Other synthetic company')
        outsider_project = Project.objects.create(name='Other synthetic project', company=outsider_company,
                                                  checklist_template=self.template)
        outsider = self.person('outsider', Profile.Roles.ENGINEER, outsider_project)
        with self.assertRaises(Http404):
            service.access(self.request(outsider), self.checklist.pk)
        self.engineer.is_active = False
        self.engineer.save(update_fields=['is_active'])
        with self.assertRaises(Http404):
            service.submit(self.request(), self.checklist.pk, True)
        self.assertEqual(SurveyProcessingRevision.objects.count(), 0)

    def test_upload_completion_and_required_inputs_gate_submission(self):
        with self.assertRaises(ValidationError):
            service.submit(self.request(), self.checklist.pk, False)
        session = service.upload_session(self.request(), self.checklist.pk)
        with self.assertRaises(ValidationError):
            service.submit(self.request(), self.checklist.pk, True)
        service.upload_session(self.request(), self.checklist.pk, session.token)
        self.checklist.answer_data = {'custom': {}}
        self.checklist.save(update_fields=['answer_data'])
        with self.assertRaises(ValidationError):
            service.submit(self.request(), self.checklist.pk, True)
        self.assertEqual(SurveyProcessingJob.objects.count(), 0)

    def test_repeated_submit_is_idempotent_and_submission_is_immutable(self):
        revision, created = service.submit(self.request(), self.checklist.pk, True)
        duplicate, duplicate_created = service.submit(self.request(), self.checklist.pk, True)
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(duplicate.pk, revision.pk)
        self.assertEqual(SurveyProcessingJob.objects.count(), 1)
        self.assertEqual(revision.snapshot['photos'][0]['sha256'], self.photo.sha256)
        revision.snapshot['site_id'] = 'tampered'
        with self.assertRaises(ValidationError):
            revision.save()
        with self.assertRaises(ValidationError):
            SurveyProcessingRevision.objects.filter(pk=revision.pk).update(digest='changed')
        with self.assertRaises(ValidationError):
            SurveyProcessingRevision.objects.filter(pk=revision.pk).delete()

    def test_changed_inputs_create_next_revision_and_preserve_previous(self):
        first, _ = service.submit(self.request(), self.checklist.pk, True)
        self.checklist.answer_data['custom']['contact'] = 'Changed synthetic contact'
        self.checklist.save(update_fields=['answer_data'])
        with self.assertRaises(ValidationError):
            service.submit(self.request(), self.checklist.pk, True)
        SurveyProcessingJob.objects.filter(revision=first).update(status='failed')
        with self.assertRaises(ValidationError):
            service.retry(self.request(), self.checklist.pk, first.pk)
        second, created = service.submit(self.request(), self.checklist.pk, True)
        self.assertTrue(created)
        self.assertEqual((first.number, second.number), (1, 2))
        first.refresh_from_db()
        self.assertEqual(first.snapshot['answers']['custom']['contact'], 'Synthetic contact')
        self.assertEqual(SurveyProcessingRevision.objects.count(), 2)

    def test_worker_generates_drafts_without_answers_approvals_or_original_changes(self):
        before = self.pristine()
        original_bytes = Path(self.photo.original.path).read_bytes()
        revision = self.ready()
        self.assertEqual(self.pristine(), before)
        self.assertEqual(Path(self.photo.original.path).read_bytes(), original_bytes)
        self.assertEqual(revision.source_analyses.count(), 2)
        payload = service.reviewed_payload(revision)
        by_id = {item['id']: item for item in payload['checklist_items']}
        self.assertEqual(set(by_id), {'site_id', 'contact', 'manufacturer', 'tower_height', 'cabinet_condition'})
        self.assertEqual(by_id['manufacturer']['proposed_answer'], 'SyntheticCo')
        self.assertEqual(by_id['manufacturer']['status'], 'Needs review')
        self.assertEqual(by_id['cabinet_condition']['status'], 'Missing')
        self.assertFalse(any(item['accepted'] for item in by_id.values()))
        self.assertEqual(len(by_id['manufacturer']['sources']), 2)
        self.assertEqual(revision.drawing_sets.count(), 1)
        self.assertFalse(revision.drawing_sets.first().released)
        self.assertFalse(service.process_next())

    def test_failed_source_retry_reuses_checkpoint_without_duplicate_outputs(self):
        calls = []
        def fail_second(source, model, **kwargs):
            calls.append(source['source_id'])
            if len(calls) == 2:
                raise ValueError('Synthetic interrupted model')
            return self.analysed(source, model)
        revision, _ = service.submit(self.request(), self.checklist.pk, True)
        stack, native, renderer = self.processing(analyse=fail_second)
        service.process_next()
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status, 'failed')
        self.assertEqual(revision.source_analyses.count(), 1)
        stack.close()
        service.retry(self.request(), self.checklist.pk, revision.pk)
        stack, native, renderer = self.processing()
        service.process_next()
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status, 'ready_for_review', revision.processing_job.error)
        self.assertEqual(native.call_count, 1)
        self.assertEqual(revision.source_analyses.count(), 2)
        self.assertEqual(revision.drawing_sets.count(), 1)
        duplicate, created = service.submit(self.request(), self.checklist.pk, True)
        self.assertFalse(created)
        self.assertEqual(duplicate.pk, revision.pk)

    def test_expired_worker_recovery_claim_is_exclusive(self):
        revision, _ = service.submit(self.request(), self.checklist.pk, True)
        first = service.claim()
        self.assertIsNotNone(first)
        self.assertIsNone(service.claim())
        SurveyProcessingJob.objects.filter(pk=first.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
        recovered = service.claim()
        self.assertEqual(recovered.pk, first.pk)
        self.assertNotEqual(recovered.lease_owner, first.lease_owner)
        with self.assertRaises(ValidationError):
            service.progress(first, completed=1)
        self.assertIsNone(service.claim())

    def test_busy_ollama_requeues_without_losing_snapshot(self):
        from .local_ai import InferenceBusy
        revision, _ = service.submit(self.request(), self.checklist.pk, True)
        stack, native, renderer = self.processing()
        with patch('core.photo_service.verify_vision', side_effect=InferenceBusy('Synthetic busy')):
            service.process_next()
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status, 'queued')
        self.assertEqual(revision.processing_job.lease_owner, '')
        self.assertEqual(revision.source_analyses.count(), 0)
        self.assertEqual(SurveyProcessingRevision.objects.count(), 1)

    def test_original_tamper_fails_even_when_observation_is_cached(self):
        revision = self.ready()
        # A crashed post-analysis job must still revalidate every original on resume.
        job = revision.processing_job
        job.status, job.lease_owner, job.lease_until = 'queued', '', None
        job.save()
        Path(self.photo.original.path).write_bytes(b'synthetic tampering')
        service.process_next()
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(revision.source_analyses.count(), 2)

    def test_group_acceptance_and_correction_reasons_are_audited_not_applied_to_source(self):
        before = self.pristine()
        revision = self.ready()
        service.review(self.request(), self.checklist.pk, revision.pk, 'accept', ids=['site_id', 'contact', 'manufacturer'])
        with self.assertRaises(ValidationError):
            service.review(self.request(), self.checklist.pk, revision.pk, 'correct', ids=['tower_height'], corrections={'tower_height': '32'})
        service.review(self.request(), self.checklist.pk, revision.pk, 'correct', ids=['tower_height'],
                       corrections={'tower_height': '32'}, reason='Transcribed confirmed recorded height.')
        payload = service.reviewed_payload(revision)
        by_id = {item['id']: item for item in payload['checklist_items']}
        self.assertEqual(by_id['tower_height']['value'], '32')
        self.assertTrue(by_id['manufacturer']['accepted'])
        self.assertEqual(by_id['manufacturer']['status'], 'Confirmed from evidence')
        self.assertEqual(self.pristine(), before)
        self.assertTrue(revision.processing_events.filter(action='correct', actor=self.engineer).exists())

    def test_invalid_numeric_and_inspection_corrections_are_rejected(self):
        revision = self.ready()
        for ident, value in [('tower_height', 'not a finite number'), ('tower_height', 'NaN'),
                             ('cabinet_condition', 'Checked'), ('cabinet_condition', {'result': 'AUTO APPROVED'})]:
            with self.subTest(ident=ident, value=value):
                with self.assertRaises(ValidationError):
                    service.review(self.request(), self.checklist.pk, revision.pk, 'correct',
                                   ids=[ident], corrections={ident: value}, reason='Synthetic validation check')

    def test_approved_sections_cannot_be_changed_via_ai_review(self):
        revision = self.ready()
        self.checklist.section_approvals = {'measurements': {'name': 'Synthetic reviewer'}}
        self.checklist.save(update_fields=['section_approvals'])
        with self.assertRaises(ValidationError):
            service.review(self.request(), self.checklist.pk, revision.pk, 'correct',
                           ids=['tower_height'], corrections={'tower_height': '31'}, reason='Must remain locked')

    def test_new_inputs_invalidate_review_without_erasing_previous_package(self):
        revision = self.ready()
        self.checklist.answer_data['custom']['contact'] = 'New source input'
        self.checklist.save(update_fields=['answer_data'])
        with self.assertRaises(ValidationError):
            service.review(self.request(), self.checklist.pk, revision.pk, 'accept', ids=['manufacturer'])
        self.assertEqual(SurveyProcessingResult.objects.count(), 1)
        self.assertEqual(revision.source_analyses.count(), 2)

    def test_additional_checklist_items_remain_proposals_and_template_is_unchanged(self):
        revision = self.ready()
        original = deepcopy(self.template.definition)
        with self.assertRaises(ValidationError):
            service.review(self.request(), self.checklist.pk, revision.pk, 'accept_additional', ids=[0])
        service.review(self.request(), self.checklist.pk, revision.pk, 'accept_additional',
                       ids=[0], reason='Explicitly accepted package-only additional item')
        payload = service.reviewed_payload(revision)
        self.assertTrue(payload['accepted_additional_items'])
        self.template.refresh_from_db()
        self.assertEqual(self.template.definition, original)

    def test_engineer_then_assigned_independent_qa_then_teamlead_release(self):
        revision = self.ready()
        with self.assertRaises(ValidationError):
            service.review(self.request(self.quality), self.checklist.pk, revision.pk, 'technical_approve')
        with self.assertRaises(ValidationError):
            service.review(self.request(), self.checklist.pk, revision.pk, 'engineer_complete')
        self.accept_complete(revision)
        with self.assertRaises(PermissionDenied):
            service.review(self.request(), self.checklist.pk, revision.pk, 'technical_approve')
        service.review(self.request(self.quality), self.checklist.pk, revision.pk, 'technical_approve')
        with self.assertRaises(ValidationError):
            service.review(self.request(self.lead), self.checklist.pk, revision.pk, 'release')
        self.checklist.status = Checklist.Status.FINAL
        self.checklist.save(update_fields=['status'])
        service.review(self.request(self.lead), self.checklist.pk, revision.pk, 'release')
        released = revision.drawing_sets.filter(released=True)
        self.assertEqual(released.count(), 1)
        self.assertTrue(revision.processing_events.filter(action='release', actor=self.lead).exists())
        service.review(self.request(self.lead), self.checklist.pk, revision.pk, 'release')
        self.assertEqual(released.count(), 1)

    def test_client_required_release_uses_real_decision_and_closed_route(self):
        from .review_route_models import ReviewRoute
        revision = self.ready()
        self.accept_complete(revision)
        service.review(self.request(self.quality), self.checklist.pk, revision.pk, 'technical_approve')
        self.checklist.status = Checklist.Status.FINAL
        self.checklist.client_review_required = True
        self.checklist.client_approval = {'decision': 'rejected', 'authenticated_client': True, 'user_id': self.customer.pk}
        self.checklist.save(update_fields=['status', 'client_review_required', 'client_approval'])
        with self.assertRaises(ValidationError):
            service.review(self.request(self.lead), self.checklist.pk, revision.pk, 'release')
        self.checklist.client_approval = {'decision': 'approved', 'authenticated_client': True, 'user_id': self.customer.pk}
        self.checklist.save(update_fields=['client_approval'])
        route = ReviewRoute.objects.create(checklist=self.checklist, layer_count=4, stage='client',
            reviewers={'quality_engineer': self.quality.pk, 'team_lead': self.lead.pk, 'client': self.customer.pk})
        with self.assertRaises(ValidationError):
            service.review(self.request(self.lead), self.checklist.pk, revision.pk, 'release')
        route.stage = 'closed'
        route.save(update_fields=['stage'])
        service.review(self.request(self.lead), self.checklist.pk, revision.pk, 'release')
        self.assertEqual(revision.drawing_sets.filter(released=True).count(), 1)

    def test_unknown_foreign_and_unverified_geometry_sources_are_rejected(self):
        revision = self.ready()
        for source_id, verified in [('photo:foreign', True), (f'photo:{self.photo.pk}', False)]:
            with self.assertRaises(ValidationError):
                service.review(self.request(), self.checklist.pk, revision.pk, 'geometry', reason='Synthetic measured record',
                    drawing_records=[{'source_id': source_id, 'verified': verified, 'unit': 'm', 'x': 0, 'y': 0, 'width': 5, 'height': 3}])
        self.assertFalse(revision.processing_events.filter(action='geometry').exists())

    def test_numeric_ai_value_is_proposed_without_a_false_type_conflict(self):
        snapshot = service.freeze_data(self.checklist)
        reconciliation = {'findings': [{'field_hint': 'tower_height', 'category': 'measurement',
            'component': 'tower', 'value': 30, 'unit': 'm', 'basis': 'recorded',
            'source_id': f'photo:{self.photo.pk}', 'reference': 'original', 'confidence': 'medium'}],
            'conflicts': [], 'missing': [], 'suggested_items': []}
        payload = service.prepare_checklist(snapshot, reconciliation)
        item = next(item for item in payload['checklist_items'] if item['id'] == 'tower_height')
        self.assertEqual(item['value'], '30')
        self.assertFalse(item['conflict'])
        self.assertEqual(reconciliation['findings'][0]['value'], 30)

    def test_qa_return_invalidates_older_package_approval(self):
        revision = self.ready()
        self.accept_complete(revision)
        service.review(self.request(self.quality), self.checklist.pk, revision.pk, 'technical_approve')
        service.review(self.request(self.quality), self.checklist.pk, revision.pk, 'technical_reject', reason='Confirm a missing cabinet label before release')
        self.checklist.status = Checklist.Status.FINAL
        self.checklist.save(update_fields=['status'])
        with self.assertRaises(ValidationError):
            service.review(self.request(self.lead), self.checklist.pk, revision.pk, 'release')

    def test_workspace_state_auth_csrf_and_project_isolation(self):
        workspace = reverse('survey_processing_workspace', args=[self.checklist.pk])
        state = reverse('survey_processing_state', args=[self.checklist.pk])
        action = reverse('survey_processing_action', args=[self.checklist.pk])
        self.assertEqual(self.client.get(state).status_code, 302)
        self.client.force_login(self.engineer)
        page = self.client.get(workspace)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'AI Checklist &amp; Drawings')
        self.assertIn('private', page['Cache-Control'])
        result = self.client.get(state)
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()['access']['can_submit'])
        self.assertEqual(result.json()['revisions'], [])
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.engineer)
        denied = strict.post(action, {'action': 'submit', 'uploads_finished': 'true'})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(SurveyProcessingRevision.objects.count(), 0)
        other = Project.objects.create(name='Other endpoint project', company=Company.objects.create(name='Other endpoint company'), checklist_template=self.template)
        outsider = self.person('endpoint_outsider', Profile.Roles.ENGINEER, other)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(state).status_code, 404)
        self.assertEqual(self.client.get(workspace).status_code, 404)
        self.assertEqual(self.client.post(action, {'action': 'submit', 'uploads_finished': 'true'}).status_code, 404)

    def test_document_upload_duplicate_download_and_crossproject_isolation(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .survey_processing_models import SurveyDocument
        action = reverse('survey_processing_action', args=[self.checklist.pk])
        self.client.force_login(self.engineer)
        raw = Path(self.photo.original.path).read_bytes()
        for attempt in range(2):
            posted = self.client.post(action, {'action': 'upload_document', 'files': [SimpleUploadedFile('synthetic-sketch.png', raw, content_type='image/png')]})
            self.assertEqual(posted.status_code, 200, posted.content)
        self.assertEqual(SurveyDocument.objects.count(), 1)
        self.assertFalse(self.checklist.survey_upload_sessions.filter(finished_at__isnull=True).exists())
        document = SurveyDocument.objects.get()
        url = reverse('survey_processing_document', args=[self.checklist.pk, document.pk])
        download = self.client.get(url)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b''.join(download.streaming_content), raw)
        self.assertIn('attachment', download['Content-Disposition'])
        self.assertEqual(download['X-Content-Type-Options'], 'nosniff')
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.engineer)
        other_checklist = Checklist.objects.create(project=self.project, user=self.engineer, site_id='SYNTHETIC-OTHER')
        wrong_record = reverse('survey_processing_document', args=[other_checklist.pk, document.pk])
        self.assertEqual(self.client.get(wrong_record).status_code, 404)

    def test_generated_package_releases_after_actual_three_layer_survey_route(self):
        self.run_actual_route_release(3)

    def test_generated_package_releases_after_actual_four_layer_client_route(self):
        self.run_actual_route_release(4)

    def run_actual_route_release(self, layers):
        from .models import WorkflowTemplateQualification
        from .roadmap_service import definition_digest
        from .independent_workflow import configure_policy, submit_revision
        from .review_route_service import act_on_route, route_context, route_for
        self.project.review_layers = layers
        self.project.save(update_fields=['review_layers'])
        self.checklist = Checklist.objects.create(project=self.project, user=self.engineer,
            quality_reviewer=self.quality, site_id='SYNTHETIC-INDEPENDENT-AI',
            answer_data={'custom': {'contact': 'Synthetic measured source contact'}},
            coordinate_reference={'source': 'Synthetic surveyed record', 'crs': 'EPSG:4326'})
        WorkflowTemplateQualification.objects.create(project=self.project, template=self.template,
            workflow_type=self.checklist.workflow_type, definition_digest=definition_digest(self.schema),
            criteria_reference='Synthetic qualified criteria', inspection_method='Synthetic review method',
            reviewed_by=self.lead, reason='Isolated integration fixture')
        configure_policy(self.admin, self.checklist, self.quality, self.lead,
            'Explicit synthetic route reviewers', customer_required=layers == 4,
            customer_reviewer=self.customer if layers == 4 else None, enable_route=True)
        self.photo, self.photo2 = self.add_photo('red'), self.add_photo('yellow')
        revision = self.ready()
        self.accept_complete(revision)
        service.review(self.request(self.quality), self.checklist.pk, revision.pk, 'technical_approve')
        # The package cannot bypass the real survey's independent review route.
        with self.assertRaises(ValidationError):
            service.review(self.request(self.lead), self.checklist.pk, revision.pk, 'release')
        self.checklist.refresh_from_db()
        submit_revision(self.engineer, self.checklist)
        for actor in [self.quality, self.lead]:
            self.checklist.refresh_from_db()
            token = route_context(actor, self.checklist)['token']
            act_on_route(actor, self.checklist, 'approve', 'Reviewed real synthetic route', token)
        if layers == 4:
            self.checklist.refresh_from_db()
            self.assertEqual(route_for(self.checklist).stage, 'client')
            with self.assertRaises(ValidationError):
                service.review(self.request(self.lead), self.checklist.pk, revision.pk, 'release')
            self.client.force_login(self.customer)
            state = self.client.get(reverse('survey_processing_state', args=[self.checklist.pk]))
            self.assertEqual(state.status_code, 200)
            self.assertEqual(state.json()['revisions'], [])
            token = route_context(self.customer, self.checklist)['token']
            act_on_route(self.customer, self.checklist, 'approve', 'Approved synthetic client package', token)
        self.checklist.refresh_from_db()
        self.assertEqual(route_for(self.checklist).stage, 'closed')
        self.assertEqual(self.checklist.status, Checklist.Status.FINAL)
        service.review(self.request(self.lead), self.checklist.pk, revision.pk, 'release')
        self.assertEqual(revision.drawing_sets.filter(released=True).count(), 1)
        if layers == 4:
            self.client.force_login(self.customer)
            state = self.client.get(reverse('survey_processing_state', args=[self.checklist.pk]))
            self.assertEqual(state.status_code, 200)
            self.assertEqual(len(state.json()['revisions']), 1)
            self.assertEqual(state.json()['active']['findings'], [])
            self.assertEqual(state.json()['active']['events'], [])

    def test_output_download_server_paths_and_record_scope_are_enforced(self):
        revision = self.ready()
        original = revision.drawing_sets.first()
        media = Path(self.photo.original.path).parents[2]
        # The actual files are a labelled synthetic fixture, never customer outputs.
        pdf = media / 'synthetic-output.pdf'
        dxf = media / 'synthetic-output.dxf'
        png = media / 'synthetic-output.png'
        pdf.write_bytes(b'%PDF synthetic test fixture')
        dxf.write_text('synthetic DXF test fixture')
        png.write_bytes(Path(self.photo.original.path).read_bytes())
        asset = SurveyDrawingSet.objects.create(revision=revision, edition=original.edition + 1, released=False,
            review_digest=original.review_digest, geometry={}, manifest={'pdf': str(pdf), 'sheets': [
                {'number': 'SYN-01', 'title': 'Synthetic only', 'dxf': str(dxf), 'preview': str(png)}]})
        url = reverse('survey_processing_output', args=[self.checklist.pk, asset.pk, 0, 'pdf'])
        self.client.force_login(self.engineer)
        output = self.client.get(url)
        self.assertEqual(output.status_code, 200)
        self.assertEqual(b''.join(output.streaming_content), b'%PDF synthetic test fixture')
        self.assertIn('private', output['Cache-Control'])
        other_checklist = Checklist.objects.create(project=self.project, user=self.engineer, site_id='SYNTHETIC-OTHER')
        wrong_record = reverse('survey_processing_output', args=[other_checklist.pk, asset.pk, 0, 'pdf'])
        self.assertEqual(self.client.get(wrong_record).status_code, 404)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.checklist.status = Checklist.Status.FINAL
        self.checklist.save(update_fields=['status'])
        self.assertEqual(self.client.get(url).status_code, 404)

    def keyed_ready(self):
        def keyed(source, model, **kwargs):
            payload = self.analysed(source, model, **kwargs)
            for index, finding in enumerate(payload['findings'], 1):
                finding['finding_key'] = f"{source['source_id']}:finding:{index}"
            return payload
        revision, _ = service.submit(self.request(), self.checklist.pk, True)
        self.processing(analyse=keyed)
        service.process_next()
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status, 'ready_for_review', revision.processing_job.error)
        return revision

    def test_extracted_record_correction_requires_owner_reason_and_keeps_raw_evidence(self):
        before = self.pristine()
        revision = self.keyed_ready()
        raw_payloads = list(revision.source_analyses.order_by('pk').values_list('payload', flat=True))
        key = f'photo:{self.photo.pk}:finding:2'
        for ids, corrections, reason in [
            ([key], {key: {'value': '35', 'unit': 'm'}}, ''),
            (['foreign-source'], {'foreign-source': {'value': '35', 'unit': 'm'}}, 'A reason'),
            ([key], {key: {'value': '35', 'unit': 'x' * 41}}, 'A reason'),
        ]:
            with self.assertRaises(ValidationError):
                service.review(self.request(), self.checklist.pk, revision.pk, 'record',
                               ids=ids, corrections=corrections, reason=reason)
        with self.assertRaises(PermissionDenied):
            service.review(self.request(self.quality), self.checklist.pk, revision.pk, 'record',
                           ids=[key], corrections={key: {'value': '35', 'unit': 'm'}}, reason='Wrong actor')
        service.review(self.request(), self.checklist.pk, revision.pk, 'record', ids=[key],
                       corrections={key: {'value': '35', 'unit': 'm'}}, reason='Verified transcription against the submitted sketch')
        payload = service.reviewed_payload(revision)
        corrected = next(finding for finding in payload['findings'] if finding['finding_key'] == key)
        self.assertEqual(corrected['value'], '35')
        self.assertEqual(corrected['verification_status'], 'confirmed')
        self.assertFalse(corrected['measured'])
        self.assertEqual(corrected['corrected_by'], self.engineer.pk)
        item = next(item for item in payload['checklist_items'] if item['id'] == 'tower_height')
        self.assertEqual(item['value'], '35')
        self.assertFalse(item['accepted'])
        self.assertEqual(item['status'], 'Needs review')
        self.assertEqual(raw_payloads, list(revision.source_analyses.order_by('pk').values_list('payload', flat=True)))
        self.assertEqual(self.pristine(), before)

    def test_record_correction_reopens_completed_package_before_original_submission(self):
        revision = self.keyed_ready()
        self.accept_complete(revision)
        self.checklist.refresh_from_db()
        service.require_engineer_review(self.checklist)
        key = f'photo:{self.photo.pk}:finding:2'
        service.review(self.request(), self.checklist.pk, revision.pk, 'record', ids=[key],
                       corrections={key: {'value': '35', 'unit': 'm'}}, reason='Corrected a recorded transcription')
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.answer_data['custom']['tower_height'], '30')
        with self.assertRaises(ValidationError):
            service.require_engineer_review(self.checklist)
        with self.assertRaises(ValidationError):
            service.review(self.request(self.quality), self.checklist.pk, revision.pk, 'technical_approve')

    def test_integrated_analysis_status_counts_processed_photos_without_legacy_jobs(self):
        from .field_photo_service import analysis_state
        initial = analysis_state(self.checklist)
        self.assertEqual(initial['analyzed_photo_ids'], [])
        revision = self.ready()
        self.checklist.refresh_from_db()
        state = analysis_state(self.checklist)
        self.assertEqual(state['analyzed_photo_ids'], sorted([self.photo.pk, self.photo2.pk]))
        self.assertEqual(state['unprocessed_photo_ids'], [])
        self.assertTrue(state['review_ready'])
        self.assertEqual(state['active_job_count'], 0)
        self.assertEqual(self.checklist.photo_jobs.count(), 0)
        self.assertFalse(revision.processing_events.filter(action='engineer_complete').exists())
        self.checklist.answer_data['custom']['contact'] = 'A changed submission source'
        self.checklist.save(update_fields=['answer_data'])
        stale = analysis_state(self.checklist)
        self.assertEqual(stale['analyzed_photo_ids'], [])
        self.assertEqual(stale['unprocessed_photo_ids'], sorted([self.photo.pk, self.photo2.pk]))

    def test_original_submit_url_requires_current_engineer_completed_ai_package(self):
        url = reverse('custom_checklist_submit', args=[self.checklist.pk])
        self.client.force_login(self.engineer)
        denied = self.client.post(url)
        self.assertEqual(denied.status_code, 302)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, Checklist.Status.DRAFT)
        revision = self.ready()
        self.client.post(url)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, Checklist.Status.DRAFT)
        self.accept_complete(revision)
        approved = self.client.post(url)
        self.assertEqual(approved.status_code, 302)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, Checklist.Status.SUBMITTED)
        self.assertEqual(self.checklist.quality_approval, {})
        self.assertEqual(self.checklist.client_approval, {})
        self.assertEqual(self.checklist.answer_data['custom']['manufacturer'], 'SyntheticCo')
        revision.refresh_from_db()
        self.assertNotIn('manufacturer', revision.snapshot['answers']['custom'])

    def test_original_submit_behavior_is_unchanged_for_excluded_templates(self):
        excluded = ChecklistTemplate.objects.create(name='Excluded AI package fixture', definition=self.schema,
                                                     published=True, checklist_required=False)
        self.checklist.checklist_template = excluded
        self.checklist.save(update_fields=['checklist_template'])
        self.client.force_login(self.engineer)
        response = self.client.post(reverse('custom_checklist_submit', args=[self.checklist.pk]))
        self.assertEqual(response.status_code, 302)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, Checklist.Status.SUBMITTED)
        self.assertEqual(self.checklist.processing_revisions.count(), 0)
