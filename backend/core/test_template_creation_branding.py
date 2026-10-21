"""Unassigned new drafts are neutral; deliberate saved-source copies keep brands."""
from copy import deepcopy
from io import BytesIO
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook
from PIL import Image

from . import test_checklist_wizard as fixtures
from .models import Checklist, ChecklistTemplate
from .template_service import default_definition, export_custom_excel


@override_settings(SECRET_KEY='isolated-template-branding-tests', ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TemplateCreationBrandingTests(TestCase):
    setUp = fixtures.ChecklistWizardTests.setUp
    person = fixtures.ChecklistWizardTests.person
    post = fixtures.ChecklistWizardTests.post
    before = fixtures.ChecklistWizardTests.before
    records = fixtures.ChecklistWizardTests.records
    workbook = fixtures.ChecklistWizardTests.workbook
    upload = fixtures.ChecklistWizardTests.upload
    stage = fixtures.ChecklistWizardTests.stage
    commit = fixtures.ChecklistWizardTests.commit

    def assert_neutral(self, template):
        self.assertEqual(template.client_left_name, '')
        self.assertEqual(template.client_right_name, '')
        self.assertFalse(template.client_left_logo)
        self.assertFalse(template.client_right_logo)
        self.assertFalse(template.company_logo)

    def test_wizard_create_from_zero_has_no_unassigned_client_branding(self):
        before = self.before()
        response = self.post('create_blank', name='Neutral zero draft', industry='telecom', workflow_type='telecom_survey')
        self.assertEqual(response.status_code, 302, response.content)
        self.assert_neutral(ChecklistTemplate.objects.get(name='Neutral zero draft'))
        self.assertEqual(self.before(), before)

    def test_imported_checklists_have_no_unassigned_client_branding(self):
        before = self.before()
        batch = self.stage()
        response = self.commit(batch)
        self.assertEqual(response.status_code, 302, response.content)
        batch.refresh_from_db()
        self.assertEqual(len(batch.created_template_ids), 2)
        for template in ChecklistTemplate.objects.filter(pk__in=batch.created_template_ids):
            self.assert_neutral(template)
        self.assertEqual(self.before(), before)

    def test_legacy_new_drafts_and_full_original_structure_have_neutral_branding(self):
        before = self.before()
        for action in ['create_blank', 'create_original']:
            with self.subTest(action=action):
                response = self.client.post(reverse('checklist_templates'), {'action': action})
                self.assertEqual(response.status_code, 302, response.content)
                draft = ChecklistTemplate.objects.latest('pk')
                self.assert_neutral(draft)
                if action == 'create_original':
                    self.assertEqual(draft.definition, default_definition())
        self.assertEqual(self.before(), before)

    def test_standard_library_new_drafts_are_neutral_including_full_fded(self):
        before = self.before()
        for key in ['telecom_survey_default', 'telecom_inspection_bts']:
            with self.subTest(key=key):
                response = self.client.post(reverse('standard_checklists'), {'key': key, 'name': 'Neutral ' + key, 'wizard': '1'})
                self.assertEqual(response.status_code, 302, response.content)
                draft = ChecklistTemplate.objects.latest('pk')
                self.assert_neutral(draft)
                if key == 'telecom_survey_default':
                    self.assertEqual(draft.definition['sections'], default_definition()['sections'])
        self.assertEqual(self.before(), before)

    def test_builtin_original_subset_does_not_assume_clients(self):
        before = self.before()
        first = default_definition()['sections'][0]['fields'][0]['id']
        response = self.client.post(reverse('checklist_template_select'),
            {'source': 'original', 'name': 'Neutral built-in subset', 'field_ids': [first]})
        self.assertEqual(response.status_code, 302, response.content)
        self.assert_neutral(ChecklistTemplate.objects.get(name='Neutral built-in subset'))
        self.assertEqual(self.before(), before)

    def test_existing_record_replication_revision_and_subset_preserve_all_source_branding(self):
        historic = deepcopy(self.survey.branding_snapshot)
        source = ChecklistTemplate(name='Explicitly branded source', definition=deepcopy(self.source.definition),
            created_by=self.admin, client_left_name='Synthetic assigned left client',
            client_right_name='Synthetic assigned right client', checklist_required=True)
        for attribute, color in [('company_logo', 'blue'), ('client_left_logo', 'red'), ('client_right_logo', 'green')]:
            image = BytesIO()
            Image.new('RGB', (32, 16), color).save(image, 'PNG')
            getattr(source, attribute).save(attribute + '.png', ContentFile(image.getvalue()), save=False)
        source.published = True
        source.save()
        self.project.checklist_template = source
        self.project.save(update_fields=['checklist_template'])
        branded = source.branding()
        responses = [
            self.post('replicate', source_id=source.pk, name='Explicit branded replication'),
            self.client.post(reverse('checklist_template_edit', args=[source.pk]), {'action': 'duplicate'}),
            self.client.post(reverse('checklist_template_select'), {'source': str(source.pk),
                'name': 'Explicit branded subset', 'field_ids': [source.definition['sections'][0]['fields'][0]['id']]}),
        ]
        ids = []
        for response in responses:
            self.assertEqual(response.status_code, 302, response.content)
            ids.append(int(response.url.rstrip('/').split('/')[-1]))
        for copied in ChecklistTemplate.objects.filter(pk__in=ids):
            self.assertEqual(copied.branding(), branded)
            self.assertFalse(copied.published)
        self.assertEqual(len(set(ids)), 3)
        source.refresh_from_db()
        self.assertEqual(source.branding(), branded)
        self.assertTrue(source.published)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.branding_snapshot, historic)

    def test_neutral_template_report_has_blank_client_slots(self):
        response = self.post('create_blank', name='Neutral report draft', industry='telecom', workflow_type='telecom_survey')
        self.assertEqual(response.status_code, 302)
        template = ChecklistTemplate.objects.get(name='Neutral report draft')
        template.published = True
        template.save(update_fields=['published'])
        self.project.checklist_template = template
        self.project.save(update_fields=['checklist_template'])
        survey = Checklist.objects.create(project=self.project, user=self.engineer, site_id='SYNTHETIC-NEUTRAL-REPORT')
        self.assertEqual(survey.branding_snapshot['clients'], [{'name': '', 'logo': ''}, {'name': '', 'logo': ''}])
        workbook = load_workbook(BytesIO(export_custom_excel(survey)))
        self.assertIsNone(workbook['Site survey']['A1'].value)
        self.assertIsNone(workbook['Site survey']['D1'].value)
        self.assertEqual(len(workbook['Site survey']._images), 0)
