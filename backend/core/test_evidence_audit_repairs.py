"""Executed regressions for private evidence state and literal workbook metadata."""
from io import BytesIO
import json

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from . import test_survey_processing as fixtures
from .models import Checklist, ChecklistTemplate


@override_settings(SECRET_KEY='isolated-evidence-audit-repairs',
    ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EvidenceAuditRepairTests(TestCase):
    setUp = fixtures.SurveyProcessingTests.setUp
    person = fixtures.SurveyProcessingTests.person
    add_photo = fixtures.SurveyProcessingTests.add_photo

    def test_each_permitted_internal_photo_state_response_prohibits_storage(self):
        for actor in (self.engineer, self.quality, self.lead, self.admin):
            with self.subTest(role=actor.profile.role):
                browser = Client()
                browser.force_login(actor)
                response = browser.get(reverse('photo_state', args=[self.checklist.pk]))
                self.assertEqual(response.status_code, 200, response.content)
                self.assertIn('private', response.get('Cache-Control', ''))
                self.assertIn('no-store', response.get('Cache-Control', ''))

    def test_published_template_name_is_literal_in_downloaded_revision_metadata(self):
        self.client.force_login(self.admin)
        template = ChecklistTemplate.objects.create(name='Literal candidate',
            definition=self.schema, created_by=self.admin)
        response = self.client.post(reverse('checklist_template_edit', args=[template.pk]), {
            'action': 'publish', 'name': '=1+1', 'definition': json.dumps(self.schema)})
        self.assertEqual(response.status_code, 302, response.content)
        template.refresh_from_db()
        self.assertTrue(template.published)
        survey = Checklist.objects.create(project=self.project, user=self.engineer,
            checklist_template=template, site_id='SYNTHETIC-LITERAL-REVISION')
        response = self.client.get(reverse('custom_checklist_download', args=[survey.pk]))
        self.assertEqual(response.status_code, 200, response.content)
        workbook = load_workbook(BytesIO(response.content), data_only=False)
        try:
            cell = workbook.active['C6']
            self.assertEqual(cell.data_type, 's')
            self.assertEqual(cell.value, "'=1+1 · v1")
        finally:
            workbook.close()

