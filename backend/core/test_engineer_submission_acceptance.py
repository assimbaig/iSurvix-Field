"""Independent saved-record acceptance for the existing Engineer/reviewer journey.

Only native inference/rendering is controlled. HTTP authorization, uploads,
persistent jobs, explicit decisions, revision snapshots and review routing use
the real application. These tests do not establish real-site AI accuracy.
"""
import hashlib
import json
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import survey_processing as pipeline, test_survey_processing as fixtures
from .independent_workflow import configure_policy
from .models import (Checklist, ChecklistTemplate, PhotoEvidence, Profile, WorkAssignment,
                     WorkflowTemplateQualification)
from .review_route_service import route_context
from .roadmap_service import definition_digest
from .survey_processing_models import SurveyProcessingJob


@override_settings(SECRET_KEY='independent-engineer-acceptance',
                   ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EngineerSubmissionAcceptanceTests(TestCase):
    setUp = fixtures.SurveyProcessingTests.setUp
    person = fixtures.SurveyProcessingTests.person
    request = fixtures.SurveyProcessingTests.request
    add_photo = fixtures.SurveyProcessingTests.add_photo
    analysed = fixtures.SurveyProcessingTests.analysed
    processing = fixtures.SurveyProcessingTests.processing

    def configure(self, layers=4):
        self.project.review_layers = layers
        self.project.save(update_fields=['review_layers'])
        # Frozen task policies are supplied at creation, never retrofitted onto
        # an existing record merely because project settings changed.
        self.checklist = Checklist.objects.create(
            project=self.project, user=self.engineer, quality_reviewer=self.quality,
            site_id='SYNTHETIC-INDEPENDENT-ROUTED',
            answer_data={'custom': {'contact': 'Synthetic contact'}},
            intake_metadata={'project_review_layers': layers},
            coordinate_reference={'source': 'Explicit synthetic recorded coordinate',
                                  'crs': 'EPSG:4326'})
        self.photo = self.add_photo('red')
        self.photo2 = self.add_photo('gray')
        WorkflowTemplateQualification.objects.create(
            project=self.project, template=self.template,
            workflow_type=self.checklist.workflow_type,
            definition_digest=definition_digest(self.schema),
            criteria_reference='Synthetic label inspection specification',
            inspection_method='Synthetic evidence and source review',
            reviewed_by=self.lead, reason='Independent acceptance fixture')
        configure_policy(self.admin, self.checklist, self.quality, self.lead,
                         'Synthetic project reviewer assignments',
                         customer_reviewer=self.customer if layers == 4 else None,
                         customer_required=layers == 4, enable_route=True)
        self.checklist.refresh_from_db()
        self.assignment = WorkAssignment.objects.create(
            project=self.project, assigned_by=self.lead, assigned_to=self.engineer,
            checklist=self.checklist, site_id=self.checklist.site_id,
            latitude=24, longitude=46, description='Independent synthetic site task')

    def action(self, actor, **data):
        self.client.force_login(actor)
        return self.client.post(reverse('survey_processing_action', args=[self.checklist.pk]), data)

    def upload(self, actor=None, token=None, color='purple', group=''):
        image = BytesIO()
        Image.new('RGB', (48, 32), color).save(image, 'PNG')
        raw = image.getvalue()
        data = {'group': group, 'files': [SimpleUploadedFile(
            'synthetic-field.png', raw, content_type='image/png')]}
        if token:
            data['processing_upload_token'] = token
        self.client.force_login(actor or self.engineer)
        response = self.client.post(reverse('photo_upload', args=[self.checklist.pk]), data)
        return response, raw

    def process_and_review(self):
        signed_count = self.checklist.submission_revisions.count()
        response = self.action(self.engineer, action='submit', uploads_finished='true')
        self.assertIn(response.status_code, (200, 201), response.content)
        revision = self.checklist.processing_revisions.get(pk=response.json()['revision_id'])
        self.processing()
        self.assertTrue(pipeline.process_next())
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status, 'ready_for_review', revision.processing_job.error)
        self.checklist.refresh_from_db()
        # Saved AI proposals never sign an Engineer or advance to QA on their own.
        self.assertEqual(self.checklist.review_route_record.stage, 'engineer')
        self.assertEqual(self.checklist.submission_revisions.count(), signed_count)
        for ident in ['site_id', 'contact', 'manufacturer', 'tower_height']:
            decision = self.action(self.engineer, action='review', revision_id=revision.pk,
                                   decision='accept', finding_ids=json.dumps([ident]))
            self.assertEqual(decision.status_code, 200, decision.content)
        rejected = self.action(self.engineer, action='review', revision_id=revision.pk,
                               decision='reject', finding_ids=json.dumps(['cabinet_condition']),
                               reason='No supported condition evidence; recorded as missing.')
        self.assertEqual(rejected.status_code, 200, rejected.content)
        complete = self.action(self.engineer, action='review', revision_id=revision.pk,
                               decision='engineer_complete',
                               reason='Reviewed all source evidence and retained unsupported fields.')
        self.assertEqual(complete.status_code, 200, complete.content)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.answer_data['custom']['manufacturer'], 'SyntheticCo')
        self.client.force_login(self.engineer)
        return_url = reverse('photo_workspace', args=[self.checklist.pk])
        handoff = self.client.post(reverse('custom_checklist_submit', args=[self.checklist.pk]),
                                   {'return_to': return_url})
        self.assertRedirects(handoff, return_url, fetch_redirect_response=False)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage, 'quality_engineer')
        return revision

    def route_action(self, actor, action, reason='Synthetic independent review', token=None):
        self.checklist.refresh_from_db()
        self.client.force_login(actor)
        return self.client.post(reverse('review_route_action', args=[self.checklist.pk]), {
            'action': action, 'reason': reason,
            'expected_token': token or route_context(actor, self.checklist)['token']})

    def test_real_upload_preserves_bytes_deduplicates_and_waits_for_completed_submission(self):
        self.configure()
        started = self.action(self.engineer, action='start_upload')
        self.assertEqual(started.status_code, 201, started.content)
        token = started.json()['token']
        uploaded, original = self.upload(token=token)
        self.assertEqual(uploaded.status_code, 201, uploaded.content)
        photo = PhotoEvidence.objects.get(pk=uploaded.json()['photos'][0]['id'])
        self.assertEqual(Path(photo.original.path).read_bytes(), original)
        self.assertEqual(photo.sha256, hashlib.sha256(original).hexdigest())
        self.assertNotEqual(photo.original.name, photo.preview.name)
        duplicate, _ = self.upload(token=token)
        self.assertEqual(duplicate.status_code, 201, duplicate.content)
        self.assertTrue(duplicate.json()['photos'][0]['duplicate'])
        self.assertEqual(self.checklist.photo_evidence.count(), 3)
        self.assertFalse(SurveyProcessingJob.objects.exists())
        premature = self.action(self.engineer, action='submit', uploads_finished='true')
        self.assertEqual(premature.status_code, 409, premature.content)
        self.assertFalse(SurveyProcessingJob.objects.exists())
        finished = self.action(self.engineer, action='finish_upload', token=token)
        self.assertEqual(finished.status_code, 200, finished.content)
        for _ in range(2):
            queued = self.action(self.engineer, action='submit', uploads_finished='true')
            self.assertIn(queued.status_code, (200, 201), queued.content)
        self.assertEqual(SurveyProcessingJob.objects.count(), 1)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage, 'engineer')

    def test_engineer_correction_retains_old_ai_and_submission_revisions(self):
        self.configure()
        revision = self.process_and_review()
        old_input = deepcopy(revision.snapshot)
        signed = self.checklist.submission_revisions.get()
        old_signature = signed.digest
        self.assertEqual(self.route_action(self.quality, 'approve').status_code, 302)
        self.assertEqual(self.route_action(self.lead, 'reject', 'Check the cabinet label').status_code, 302)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage, 'quality_engineer')
        self.assertEqual(self.route_action(self.quality, 'return', 'Engineer must correct recorded contact').status_code, 302)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, Checklist.Status.REJECTED)
        self.client.force_login(self.engineer)
        saved = self.client.post(reverse('custom_checklist_save', args=[self.checklist.pk]),
                                 json.dumps({'answers': {'contact': 'Corrected synthetic contact'}}),
                                 content_type='application/json')
        self.assertEqual(saved.status_code, 200, saved.content)
        # A returned record cannot skip analysis/review of its changed inputs.
        blocked = self.client.post(reverse('custom_checklist_submit', args=[self.checklist.pk]))
        self.assertEqual(blocked.status_code, 302)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage, 'engineer')
        next_revision = self.process_and_review()
        self.assertNotEqual(next_revision.pk, revision.pk)
        self.assertEqual(self.checklist.processing_revisions.count(), 2)
        self.assertEqual(self.checklist.submission_revisions.count(), 2)
        revision.refresh_from_db(); signed.refresh_from_db()
        self.assertEqual(revision.snapshot, old_input)
        self.assertEqual(signed.digest, old_signature)
        newest = self.checklist.submission_revisions.order_by('-number').first()
        self.assertEqual(newest.number, 2)
        self.assertEqual(newest.parent_id, signed.pk)

    def test_four_layer_client_return_is_one_step_and_preserves_authorization(self):
        self.configure()
        self.process_and_review()
        self.assertEqual(self.route_action(self.quality, 'approve').status_code, 302)
        self.checklist.refresh_from_db()
        before = self.checklist.review_route_record.generation
        # A scoped Admin can administer projects, never substitute a technical signature.
        self.assertEqual(self.route_action(self.admin, 'approve').status_code, 403)
        self.assertEqual(self.route_action(self.lead, 'approve').status_code, 302)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage, 'client')
        rejected = self.route_action(self.customer, 'reject', 'Clarify the retained evidence gap')
        self.assertEqual(rejected.status_code, 302, rejected.content)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage, 'team_lead')
        self.assertEqual(self.checklist.review_route_record.mode, 'clarification')
        self.assertGreater(self.checklist.review_route_record.generation, before)
        self.assertEqual(self.route_action(self.lead, 'clarify', 'Gap remains explicitly marked missing').status_code, 302)
        self.assertEqual(self.route_action(self.customer, 'approve').status_code, 302)
        self.checklist.refresh_from_db();self.assignment.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage, 'closed')
        self.assertEqual(self.assignment.status, WorkAssignment.Status.COMPLETED)
        self.assertTrue(self.checklist.client_approval['authenticated_client'])
        self.client.force_login(self.engineer)
        forbidden = self.client.post(reverse('custom_checklist_save', args=[self.checklist.pk]),
                                     json.dumps({'answers': {'contact': 'Forbidden after release'}}),
                                     content_type='application/json')
        self.assertIn(forbidden.status_code, (400, 403))

    def test_three_layer_project_closes_without_client_and_stale_review_fails(self):
        self.configure(3)
        self.process_and_review()
        self.checklist.refresh_from_db()
        token = route_context(self.quality, self.checklist)['token']
        self.assertEqual(self.route_action(self.quality, 'approve', token=token).status_code, 302)
        stale = self.route_action(self.quality, 'approve', token=token)
        self.assertIn(stale.status_code, (403, 409))
        self.assertEqual(self.route_action(self.lead, 'approve').status_code, 302)
        self.checklist.refresh_from_db();self.assignment.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage, 'closed')
        self.assertFalse(self.checklist.client_review_required)
        self.assertEqual(self.assignment.status, WorkAssignment.Status.COMPLETED)
        # No Client stage means this Client is never shared this task revision.
        self.assertEqual(self.route_action(self.customer, 'approve').status_code, 404)

    def test_wrong_roles_cannot_upload_submit_or_accept_engineer_results(self):
        self.configure()
        peer = self.person('independent_peer', Profile.Roles.ENGINEER)
        super_admin = User.objects.create_superuser('independent_super', password=None)
        for actor in [self.admin, self.quality, self.lead, self.customer, peer, super_admin]:
            with self.subTest(actor=actor.username):
                response, _ = self.upload(actor)
                self.assertIn(response.status_code, (403, 404))
                submitted = self.action(actor, action='submit', uploads_finished='true')
                self.assertIn(submitted.status_code, (403, 404))
        self.assertEqual(self.checklist.photo_evidence.count(), 2)
        self.assertFalse(SurveyProcessingJob.objects.exists())
        revision = self.process_and_review()
        decisions = revision.processing_events.count()
        for actor in [self.admin, self.quality, self.lead, self.customer, peer, super_admin]:
            with self.subTest(proposal_actor=actor.username):
                rejected = self.action(actor, action='review', revision_id=revision.pk,
                                       decision='accept', finding_ids=json.dumps(['manufacturer']))
                self.assertIn(rejected.status_code, (403, 404))
        self.assertEqual(revision.processing_events.count(), decisions)

    def test_engineer_submit_does_not_follow_an_external_return_destination(self):
        self.template = ChecklistTemplate.objects.create(
            name='Synthetic safe-return checklist', definition=deepcopy(self.schema),
            published=True, checklist_required=False)
        self.project.checklist_template = self.template
        self.project.save(update_fields=['checklist_template'])
        self.configure(3)
        self.client.force_login(self.engineer)
        response = self.client.post(reverse('custom_checklist_submit', args=[self.checklist.pk]),
                                    {'return_to': 'https://untrusted.example.test/capture'})
        self.assertRedirects(response, reverse('custom_checklist', args=[self.checklist.pk]),
                             fetch_redirect_response=False)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage, 'quality_engineer')
