"""Failed draft saves retain valid entered work without changing saved records."""
import json
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import test_checklist_editor as fixtures
from .models import ChecklistTemplate


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EditorSaveFailureTests(TestCase):
    setUp = fixtures.ChecklistEditorTests.setUp
    page = fixtures.ChecklistEditorTests.page

    def logo(self, filename='synthetic-original.png', color='blue'):
        output = BytesIO()
        Image.new('RGB', (48, 24), color).save(output, 'PNG')
        return SimpleUploadedFile(filename, output.getvalue(), content_type='image/png')

    def values(self):
        definition = deepcopy(self.selected.definition)
        definition['sections'][0]['fields'][0]['label'] = 'Unsaved but valid renamed checkpoint'
        return {'action': 'save', 'name': 'Entered draft name', 'definition': json.dumps(definition),
            'editor_template_id': self.selected.pk, 'editor_version': self.selected.version,
            'wizard_expected_digest': self.page().context['wizard_expected_digest'],
            'processing_setting_present': '1', 'checklist_required': 'on',
            'client_left_name': 'Entered left client', 'client_right_name': 'Entered right client'}

    def test_corrupt_logo_keeps_entered_tree_controls_and_saved_logos_unchanged(self):
        self.selected.company_logo.save('saved-company.png', self.logo(), save=False)
        self.selected.client_left_logo.save('saved-client.png', self.logo(color='green'), save=False)
        self.selected.save()
        before = deepcopy(self.selected.definition)
        paths = [self.selected.company_logo.name, self.selected.client_left_logo.name]
        values = self.values()
        values['company_logo'] = SimpleUploadedFile('corrupt.png', b'not an image', content_type='image/png')
        response = self.client.post(reverse('checklist_wizard_edit', args=[self.selected.pk]), values)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context['editor_unsaved'])
        self.assertEqual(response.context['definition'], json.loads(values['definition']))
        shown = response.context['selected_template']
        self.assertEqual(shown.name, values['name'])
        self.assertTrue(shown.checklist_required)
        self.assertEqual(shown.client_left_name, values['client_left_name'])
        self.assertEqual(shown.client_right_name, values['client_right_name'])
        self.assertEqual([shown.company_logo.name, shown.client_left_logo.name], paths)
        self.selected.refresh_from_db()
        self.assertEqual(self.selected.definition, before)
        self.assertEqual(self.selected.name, '5G7 - Existing Survey')
        self.assertFalse(self.selected.checklist_required)
        for field in [self.selected.company_logo, self.selected.client_left_logo]:
            self.assertTrue(Path(field.path).is_file())
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.answer_data['custom']['unique_civil'], 'Saved human value')

    def test_storage_save_failure_retains_work_and_removes_only_new_logo_files(self):
        self.selected.company_logo.save('original.png', self.logo(), save=True)
        old_path = Path(self.selected.company_logo.path)
        root = old_path.parents[1]
        before_files = set(root.rglob('*'))
        values = self.values()
        values['company_logo'] = self.logo('replacement.png', color='red')
        with patch.object(ChecklistTemplate, 'save', side_effect=OSError('Synthetic write failure')):
            response = self.client.post(reverse('checklist_wizard_edit', args=[self.selected.pk]), values)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context['editor_unsaved'])
        self.assertEqual(response.context['definition'], json.loads(values['definition']))
        self.assertTrue(old_path.is_file())
        self.assertEqual(set(root.rglob('*')), before_files)
        self.selected.refresh_from_db()
        self.assertEqual(self.selected.name, '5G7 - Existing Survey')
        self.assertEqual(Path(self.selected.company_logo.path), old_path)

    def test_stale_save_retains_work_and_old_token_without_overwriting_newer_data(self):
        values = self.values()
        ChecklistTemplate.objects.filter(pk=self.selected.pk).update(name='Concurrent saved name')
        response = self.client.post(reverse('checklist_wizard_edit', args=[self.selected.pk]), values)
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.context['editor_unsaved'])
        self.assertEqual(response.context['wizard_expected_digest'], values['wizard_expected_digest'])
        self.assertEqual(response.context['definition'], json.loads(values['definition']))
        self.assertEqual(response.context['selected_template'].name, values['name'])
        self.assertTrue(response.context['selected_template'].checklist_required)
        self.selected.refresh_from_db()
        self.assertEqual(self.selected.name, 'Concurrent saved name')

    def test_wrong_editor_identity_does_not_render_another_drafts_entered_fields(self):
        values = self.values()
        values['editor_template_id'] = self.second.pk
        response = self.client.post(reverse('checklist_wizard_edit', args=[self.selected.pk]), values)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.context['editor_unsaved'])
        self.assertEqual(response.context['selected_template'].pk, self.selected.pk)
        self.assertEqual(response.context['definition'], self.selected.definition)
