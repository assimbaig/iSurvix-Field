"""Client evidence reads exclude internal inference proposals and diagnostics."""
import hashlib
import json
import tempfile
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .field_photo_service import schema_digest
from .models import (Checklist, ChecklistTemplate, Company, PhotoDraft, PhotoEvidence,
                     PhotoJob, PhotoPlacement, Profile, Project)


@override_settings(ROOT_URLCONF='checklist.urls', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False, LOCAL_AI_ENABLED=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ClientPhotoPrivacyTests(TestCase):
    markers = ('PRIVATE_PENDING_VALUE', 'PRIVATE_REASON', 'PRIVATE_BASELINE',
               'PRIVATE_JOB_ERROR', 'PRIVATE_PROVIDER', 'PRIVATE_VISUAL',
               'PRIVATE_AUDIT', 'PRIVATE_REJECTED', 'PRIVATE_MODEL')

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='client-photo-privacy-')
        self.addCleanup(temporary.cleanup)
        storage = override_settings(MEDIA_ROOT=temporary.name)
        storage.enable()
        self.addCleanup(storage.disable)
        self.schema = {'title': 'Client photo privacy fixture', 'sections': [
            {'id': 'general', 'title': 'General', 'fields': [
                {'id': 'condition', 'label': 'Condition', 'type': 'text'},
                {'id': 'evidence', 'label': 'Reviewed photo', 'type': 'photo'},
                {'id': 'pending', 'label': 'Pending photo', 'type': 'photo'},
                {'id': 'rejected', 'label': 'Rejected photo', 'type': 'photo'}]}]}
        template = ChecklistTemplate.objects.create(name='Client photo privacy fixture',
                                                     definition=self.schema, published=True)
        company = Company.objects.create(name='Client photo privacy fixture')
        self.project = Project.objects.create(name='Client photo privacy fixture',
                                               company=company, checklist_template=template)
        self.engineer = self.person('engineer', Profile.Roles.ENGINEER)
        self.lead = self.person('lead', Profile.Roles.TEAM_LEAD)
        self.customer = self.person('client', Profile.Roles.CLIENT)
        self.checklist = Checklist.objects.create(project=self.project, user=self.engineer,
            site_id='PHOTO-PRIVACY-FIXTURE', status=Checklist.Status.FINAL,
            schema_snapshot=self.schema, answer_data={'custom': {'condition': 'Reviewed final answer'}},
            review_history=[{'action': 'internal_note', 'reason': 'PRIVATE_AUDIT'}])
        image = BytesIO()
        Image.new('RGB', (30, 20), 'blue').save(image, 'PNG')
        self.original = image.getvalue()
        self.photo = PhotoEvidence.objects.create(checklist=self.checklist,
            uploaded_by=self.engineer, filename='reviewed-source.png', group='Civil',
            sha256=hashlib.sha256(self.original).hexdigest(),
            metadata={'format': 'PNG', 'width': 30, 'height': 20,
                      'gps': {'latitude': 24.5, 'longitude': 46.5, 'provider': 'PRIVATE_PROVIDER'},
                      'captured_at': '2026:10:23 12:00:00', 'provider': 'PRIVATE_PROVIDER'},
            analysis_metadata={'caption': 'PRIVATE_VISUAL'}, analysis_signature='synthetic')
        self.photo.original.save('source.bin', ContentFile(self.original))
        self.photo.preview.save('preview.jpg', ContentFile(self.original))
        self.job = PhotoJob.objects.create(checklist=self.checklist, requested_by=self.engineer,
            model='PRIVATE_MODEL', schema=self.schema, status='failed', error='PRIVATE_JOB_ERROR')
        self.job.photos.add(self.photo)
        self.proposal = PhotoDraft.objects.create(job=self.job, photo=self.photo,
            field_id='condition', label='Condition', value='PRIVATE_PENDING_VALUE',
            reason='PRIVATE_REASON', baseline='PRIVATE_BASELINE', uncertainty='high', status='pending')
        PhotoDraft.objects.create(job=self.job, photo=self.photo, field_id='condition',
            label='Rejected', value='PRIVATE_REJECTED', reason='PRIVATE_REASON',
            uncertainty='high', status='rejected')
        for field, status in [('evidence', 'confirmed'), ('pending', 'proposed'), ('rejected', 'rejected')]:
            PhotoPlacement.objects.create(photo=self.photo, field_id=field, section_id='general',
                status=status, schema_digest=schema_digest(self.checklist),
                reason='PRIVATE_REASON', confidence='high', uncertainty='low')
        self.client.force_login(self.customer)

    def person(self, name, role, project=None):
        user = User.objects.create_user('photo_privacy_' + name)
        user.profile.role = role
        user.profile.project = project or self.project
        user.profile.company = (project or self.project).company
        user.profile.save()
        return user

    def assert_private_markers_absent(self, value):
        encoded = json.dumps(value, default=str)
        for marker in self.markers:
            self.assertNotIn(marker, encoded)

    def test_client_state_excludes_proposals_diagnostics_and_raw_model_metadata(self):
        with patch('core.evidence_pipeline.saved_state', side_effect=AssertionError('Client must not load internal analysis')):
            response = self.client.get(reverse('photo_state', args=[self.checklist.pk]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assert_private_markers_absent(data)
        self.assertEqual(data['drafts'], [])
        self.assertEqual(data['jobs'], [])
        self.assertIsNone(data['evidence_analysis'])
        self.assertIsNone(data['analysis'])
        self.assertEqual(data['photos'][0]['metadata']['gps'], {'latitude': 24.5, 'longitude': 46.5})
        self.assertIsNone(data['photos'][0]['visual_metadata'])
        self.assertEqual([(row['field_id'], row['status']) for row in data['mappings']],
                         [('evidence', 'confirmed')])
        self.assertTrue(all(not slot['proposed_photo_ids'] for slot in data['coverage']['required']))
        self.assertEqual(data['photos'][0]['original_url'],
                         reverse('photo_evidence', args=[self.checklist.pk, self.photo.pk, 'original']))

    def test_client_report_contains_sources_and_reviewed_links_without_internal_history(self):
        with patch('core.evidence_pipeline.saved_state', side_effect=AssertionError('Client must not load internal analysis')):
            response = self.client.get(reverse('photo_report', args=[self.checklist.pk]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assert_private_markers_absent(data)
        self.assertEqual(data['drafts'], [])
        self.assertEqual(data['jobs'], [])
        self.assertEqual(data['audit'], [])
        self.assertEqual(data['evidence'][0]['sha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(data['evidence'][0]['metadata']['width'], 30)
        self.assertEqual([row['field_id'] for row in data['placements']], ['evidence'])
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_client_html_context_does_not_receive_internal_jobs_or_drafts(self):
        response = self.client.get(reverse('photo_workspace', args=[self.checklist.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['jobs']), [])
        self.assertEqual(list(response.context['drafts']), [])
        self.assertFalse(response.context['can_process_photos'])
        self.assertEqual(response.context['model'], '')
        self.assertTrue(response.context['client_evidence_view'])
        self.assertContains(response, 'id="evidence-analysis-panel" hidden')
        self.assert_private_markers_absent(response.content.decode())
        self.assertContains(response, 'Reviewed final answer')

    def test_client_original_download_preserves_source_bytes(self):
        response = self.client.get(reverse('photo_evidence',
                                          args=[self.checklist.pk, self.photo.pk, 'original']))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), self.original)
        response.close()

    def test_client_matching_panel_is_hidden_but_original_evidence_remains_accessible(self):
        """A read-only recipient inspects sources without a misleading mapping task."""
        class ElementsById(HTMLParser):
            def __init__(self, text):
                super().__init__()
                self.elements = {}
                self.feed(text)

            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if attributes.get('id'):
                    self.elements[attributes['id']] = attributes

        response = self.client.get(reverse('photo_workspace', args=[self.checklist.pk]))
        self.assertEqual(response.status_code, 200)
        elements = ElementsById(response.content.decode()).elements
        panel = elements['photo-batch-matches']
        self.assertIn('hidden', panel)
        self.assertIn('display:none!important', panel.get('style', '').replace(' ', ''))
        # Retain the actual source-photo surface rather than hiding all evidence.
        self.assertNotIn('hidden', elements['photo-evidence-details'])
        self.assertIn('photo-thumbs', elements)
        self.assertIn('photo-original', elements)
        state = self.client.get(reverse('photo_state', args=[self.checklist.pk]))
        self.assertEqual(state.status_code, 200)
        self.assert_private_markers_absent(state.json())
        self.assertEqual([photo['id'] for photo in state.json()['photos']], [self.photo.pk])
        original = self.client.get(state.json()['photos'][0]['original_url'])
        self.assertEqual(original.status_code, 200)
        self.assertEqual(b''.join(original.streaming_content), self.original)
        original.close()
        for actor in (self.lead,):
            with self.subTest(role=actor.profile.role):
                self.client.force_login(actor)
                staff = self.client.get(reverse('photo_workspace', args=[self.checklist.pk]))
                self.assertEqual(staff.status_code, 200)
                staff_panel = ElementsById(staff.content.decode()).elements['photo-batch-matches']
                self.assertNotIn('hidden', staff_panel)
                self.assertNotIn('display:none', staff_panel.get('style', ''))
        self.client.force_login(self.engineer)
        capture=self.client.get(reverse('photo_workspace',args=[self.checklist.pk]))
        self.assertContains(capture,'id="engineer-capture"')
        self.assertNotContains(capture,'id="photo-batch-matches"')

    def test_team_lead_keeps_legacy_internal_review_data_engineer_has_capture_only(self):
        for actor in (self.lead,):
            with self.subTest(role=actor.profile.role):
                self.client.force_login(actor)
                with patch('core.photo_metadata.metadata_is_current', return_value=True), \
                     patch('core.evidence_pipeline.saved_state', return_value={'records': []}):
                    state = self.client.get(reverse('photo_state', args=[self.checklist.pk]))
                    report = self.client.get(reverse('photo_report', args=[self.checklist.pk]))
                self.assertEqual(state.status_code, 200)
                self.assertEqual(report.status_code, 200)
                self.assertEqual(state.json()['jobs'][0]['error'], 'PRIVATE_JOB_ERROR')
                self.assertEqual(state.json()['photos'][0]['visual_metadata']['caption'], 'PRIVATE_VISUAL')
                self.assertIn('PRIVATE_PENDING_VALUE', json.dumps(state.json()['drafts']))
                self.assertIn('PRIVATE_BASELINE', json.dumps(report.json()['drafts']))
                self.assertEqual(len(state.json()['mappings']), 3)
        self.client.force_login(self.engineer)
        state=self.client.get(reverse('photo_state',args=[self.checklist.pk]))
        self.assertEqual(state.status_code,200)
        self.assertNotIn('drafts',state.json())
        self.assertNotIn('jobs',state.json())
        self.assertEqual(state.json()['photos'][0]['id'],self.photo.pk)

    def test_client_cannot_use_final_evidence_projection_for_draft_or_foreign_project(self):
        self.checklist.status = Checklist.Status.DRAFT
        self.checklist.save()
        for route in ('photo_state', 'photo_report', 'photo_workspace'):
            self.assertEqual(self.client.get(reverse(route, args=[self.checklist.pk])).status_code, 404)
        self.checklist.status = Checklist.Status.FINAL
        self.checklist.save()
        other = Project.objects.create(name='Foreign photo privacy fixture', company=self.project.company)
        outsider = self.person('foreign_client', Profile.Roles.CLIENT, other)
        self.client.force_login(outsider)
        for route in ('photo_state', 'photo_report', 'photo_workspace'):
            self.assertEqual(self.client.get(reverse(route, args=[self.checklist.pk])).status_code, 404)
