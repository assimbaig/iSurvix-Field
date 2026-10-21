"""Project-scoped real files; nginx enforcement is probed separately, natively."""
import hashlib
from pathlib import Path

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from . import survey_processing as pipeline, test_survey_processing as fixtures
from .models import Checklist, Company, Profile, Project
from .survey_processing_models import SurveyDocument, SurveyDrawingSet, SurveySourceAnalysis


@override_settings(SECRET_KEY='isolated-private-files', ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PrivateFileDeliveryTests(TestCase):
    setUp = fixtures.SurveyProcessingTests.setUp
    person = fixtures.SurveyProcessingTests.person
    request = fixtures.SurveyProcessingTests.request
    add_photo = fixtures.SurveyProcessingTests.add_photo

    def get_bytes(self, url, actor=None):
        if actor:
            self.client.force_login(actor)
        else:
            self.client.logout()
        response = self.client.get(url)
        if response.status_code == 200:
            content = b''.join(response.streaming_content)
            response.close()
            return response, content
        return response, b''

    def legacy_attachment(self):
        self.checklist.image_data = {'legacy-14': [self.photo.original.name]}
        self.checklist.save(update_fields=['image_data'])
        return reverse('private_checklist_file', args=[self.checklist.pk]) + '?path=' + self.photo.original.name

    def test_exact_saved_legacy_attachment_preserves_authorised_access_and_bytes(self):
        expected = Path(self.photo.original.path).read_bytes()
        before = hashlib.sha256(expected).hexdigest()
        url = self.legacy_attachment()
        for actor in (self.engineer, self.lead, self.admin):
            response, content = self.get_bytes(url, actor)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(content, expected)
            self.assertEqual(response['Cache-Control'], 'private, no-store')
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(hashlib.sha256(Path(self.photo.original.path).read_bytes()).hexdigest(), before)

    def test_legacy_delivery_rejects_anonymous_foreign_project_and_wrong_role(self):
        url = self.legacy_attachment()
        company = Company.objects.create(name='Synthetic foreign file company')
        project = Project.objects.create(name='Synthetic foreign file project', company=company, checklist_template=self.template)
        foreign = self.person('foreign_private_files', Profile.Roles.ENGINEER, project)
        unassigned = self.person('unassigned_private_files', Profile.Roles.ENGINEER)
        for actor in (None, foreign, unassigned, self.customer):
            response, _ = self.get_bytes(url, actor)
            self.assertIn(response.status_code, (403, 404), (str(actor), response.status_code))

    def test_legacy_delivery_cannot_read_unsaved_or_traversal_paths(self):
        base = self.legacy_attachment().split('?', 1)[0]
        self.client.force_login(self.engineer)
        for name in (self.photo2.original.name, '../django-secret', '/etc/passwd',
                     'F:/iSurvix/iSurvix-Field/.local/django-secret', 'photo_pilot/../../django-secret',
                     'photo_pilot\\originals\\anything.bin', '%2e%2e/django-secret'):
            with self.subTest(name=name):
                response = self.client.get(base, {'path': name})
                self.assertEqual(response.status_code, 404)

    def test_legacy_stored_media_prefix_is_normalised_without_opening_directory_access(self):
        self.checklist.image_data = {'14': ['/media/' + self.photo.original.name]}
        self.checklist.save(update_fields=['image_data'])
        self.client.force_login(self.engineer)
        response = self.client.get(reverse('private_checklist_file', args=[self.checklist.pk]),
                                   {'path': '/media/' + self.photo.original.name})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), Path(self.photo.original.path).read_bytes())
        response.close()

    def private_assets(self):
        self.photo.metadata = {'format': 'PNG'}
        self.photo.preview.save('synthetic-preview.png', ContentFile(Path(self.photo.original.path).read_bytes()))
        self.photo.save(update_fields=['metadata'])
        raw = Path(self.photo.original.path).read_bytes()
        doc = SurveyDocument(checklist=self.checklist, uploaded_by=self.engineer,
            filename='synthetic-support.png', sha256=hashlib.sha256(raw).hexdigest(), content_type='image/png', size=len(raw))
        doc.original.save(doc.filename, ContentFile(raw), save=False)
        doc.save()
        revision, _ = pipeline.submit(self.request(), self.checklist.pk, True)
        payload = {'preview_file': self.photo.preview.name, 'source_id': f'photo:{self.photo.pk}', 'reference': 'Synthetic source'}
        source = SurveySourceAnalysis.objects.create(revision=revision, source_id=f'photo:{self.photo.pk}',
            payload=payload, digest=pipeline.digest(payload))
        return [reverse('photo_evidence', args=[self.checklist.pk, self.photo.pk, 'original']),
                reverse('photo_evidence', args=[self.checklist.pk, self.photo.pk, 'preview']),
                reverse('survey_processing_document', args=[self.checklist.pk, doc.pk]),
                reverse('survey_processing_source', args=[self.checklist.pk, source.pk])], revision

    def test_modern_photo_document_and_extracted_preview_require_project_authorisation(self):
        urls, _ = self.private_assets()
        expected = Path(self.photo.original.path).read_bytes()
        company = Company.objects.create(name='Synthetic foreign modern file company')
        project = Project.objects.create(name='Synthetic foreign modern project', company=company, checklist_template=self.template)
        foreign = self.person('foreign_modern_files', Profile.Roles.TEAM_LEAD, project)
        for url in urls:
            with self.subTest(url=url):
                for actor in (None, foreign):
                    response, _ = self.get_bytes(url, actor)
                    self.assertIn(response.status_code, (302, 403, 404))
                response, content = self.get_bytes(url, self.engineer)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(content, expected)

    def test_direct_media_url_is_never_an_application_download_even_when_authenticated(self):
        urls, _ = self.private_assets()
        for actor in (None, self.engineer, self.admin):
            for name in (self.photo.original.name, self.photo.preview.name,
                         self.checklist.survey_documents.get().original.name):
                response, _ = self.get_bytes('/media/' + name, actor)
                self.assertEqual(response.status_code, 404)

    def test_real_draft_pdf_dxf_zip_are_private_and_clients_cannot_bypass_release_gate(self):
        from .survey_drawings import build_geometry, render_outputs
        _, revision = self.private_assets()
        folder = Path(self.photo.original.path).parents[2] / 'survey_processing' / 'security-draft'
        geometry = build_geometry(revision.snapshot, [])
        manifest = render_outputs(geometry, folder)
        output = SurveyDrawingSet.objects.create(revision=revision, edition=1, review_digest='unreleased-synthetic',
                                                 geometry=geometry, manifest=manifest)
        self.checklist.status = Checklist.Status.FINAL
        self.checklist.save(update_fields=['status'])
        for kind in ('pdf', 'dxf', 'preview', 'bundle'):
            url = reverse('survey_processing_output', args=[self.checklist.pk, output.pk, 0, kind])
            denied, _ = self.get_bytes(url, self.customer)
            self.assertEqual(denied.status_code, 404)
            response, content = self.get_bytes(url, self.engineer)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(content)
            name = manifest.get(kind) if kind in {'pdf', 'bundle'} else manifest['sheets'][0][kind]
            self.assertEqual(content, Path(name).read_bytes())

    def test_client_branding_uses_scoped_delivery_and_direct_logo_url_is_denied(self):
        self.checklist.branding_snapshot = {'clients': [{'name': 'Synthetic client', 'logo': self.photo.original.name}]}
        self.checklist.save(update_fields=['branding_snapshot'])
        url = reverse('custom_client_logo', args=[self.checklist.pk, 0])
        for actor in (None, self.customer):
            response, _ = self.get_bytes(url, actor)
            self.assertEqual(response.status_code, 404)
        response, content = self.get_bytes(url, self.engineer)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(content, Path(self.photo.original.path).read_bytes())
