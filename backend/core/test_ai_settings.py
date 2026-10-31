"""Company-scoped AI settings use real forms, persisted records and audit events."""
from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import Company, GovernanceAudit, IndustryCatalog, Profile


class AISettingsFormTests(SimpleTestCase):
    def data(self, **changes):
        data = {'version': '0', 'primary_provider': 'local', 'local_model': 'qwen3.5:4b',
                'daily_request_limit': '400', 'request_timeout': '120'}
        data.update(changes)
        return data

    def test_omitted_boolean_controls_are_false(self):
        from .ai_settings_forms import AISettingsForm
        form = AISettingsForm(self.data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data['enabled'])
        self.assertFalse(form.cleaned_data['fallback_enabled'])
        self.assertFalse(form.cleaned_data['allow_external_evidence'])

    @override_settings(AI_PROVIDER_REGISTRY={'gateway': {'endpoint': 'https://example.test', 'credential_env': 'PRIVATE_KEY'}, 'bad alias': {}, '<script>': {}})
    def test_only_safe_alias_names_are_disclosed_not_registry_credentials(self):
        from .ai_settings_forms import AISettingsForm, provider_aliases
        self.assertEqual(provider_aliases(), ['gateway'])
        rendered = AISettingsForm().as_p()
        self.assertNotIn('PRIVATE_KEY', rendered)
        self.assertNotIn('https://example.test', rendered)
        self.assertNotIn('&lt;script&gt;', rendered)

    @override_settings(AI_PROVIDER_REGISTRY={'gateway': {}})
    def test_explicit_consent_is_required_for_fallback_even_with_local_primary(self):
        from .ai_settings_forms import AISettingsForm
        form = AISettingsForm(self.data(fallback_enabled='on', api_endpoint='gateway', api_model='model'))
        self.assertFalse(form.is_valid())
        self.assertIn('allow_external_evidence', form.errors)

    def test_invalid_limit_and_timeout_remain_validation_errors(self):
        from .ai_settings_forms import AISettingsForm
        form = AISettingsForm(self.data(daily_request_limit='-1', request_timeout='601'))
        self.assertFalse(form.is_valid())
        self.assertEqual(set(form.errors), {'daily_request_limit', 'request_timeout'})


@override_settings(AI_PROVIDER_REGISTRY={
    'private-gateway': {'endpoint': 'https://gateway.example.test', 'credential_env': 'TEST_PRIVATE_CREDENTIAL'},
})
class AISettingsHTTPTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name='AI Settings Company A')
        cls.foreign = Company.objects.create(name='AI Settings Company B')
        cls.industry = IndustryCatalog.objects.get_or_create(code='telecom', defaults={'name': 'Telecom', 'workflow_family': 'telecom'})[0]
        cls.admin = cls.user('ai-admin', Profile.Roles.ADMIN, cls.company)
        cls.other = cls.user('ai-other', Profile.Roles.ADMIN, cls.foreign)
        cls.owner = cls.user('ai-owner', Profile.Roles.SUPER_ADMIN, None, owner=True)
        cls.engineer = cls.user('ai-engineer', Profile.Roles.ENGINEER, cls.company)

    @classmethod
    def user(cls, name, role, company, owner=False):
        user = get_user_model().objects.create_user(username=name, password='isolated-fixture-password', is_superuser=owner)
        Profile.objects.update_or_create(user=user, defaults={'role': role, 'company': company, 'admin_industry': cls.industry if role == Profile.Roles.ADMIN else None})
        return user

    def url(self, company=None):
        return reverse('ai_settings_company', args=[(company or self.company).pk])

    def data(self, **changes):
        value = {'enabled': 'on', 'version': '0', 'primary_provider': 'local', 'local_model': 'qwen3.5:4b', 'api_model': '', 'api_endpoint': '', 'daily_request_limit': '400', 'request_timeout': '120'}
        value.update(changes)
        return value

    def config(self):
        from .ai_processing_models import AIProcessingSettings
        return AIProcessingSettings.objects.get(company=self.company)

    def test_admin_lands_on_own_company_without_creating_config_on_get(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('ai_settings_index'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.company.name)
        self.assertContains(response, 'AI Settings')
        self.assertEqual(response.context['form']['version'].value(), 0)
        from .ai_processing_models import AIProcessingSettings
        self.assertFalse(AIProcessingSettings.objects.exists())

    def test_anonymous_redirects_and_operational_roles_are_denied(self):
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        for role in [Profile.Roles.ENGINEER, Profile.Roles.QUALITY_ENGINEER, Profile.Roles.TEAM_LEAD, Profile.Roles.CLIENT]:
            user = self.user('denied-' + role.lower(), role, self.company)
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url()).status_code, 403)
            self.assertEqual(self.client.post(self.url(), self.data()).status_code, 403)

    def test_foreign_admin_cannot_read_or_write_company_config(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url()).status_code, 403)
        self.assertEqual(self.client.post(self.url(), self.data()).status_code, 403)

    def test_owner_can_select_company_without_operational_records(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('ai_settings_index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.company.name)
        self.assertContains(response, self.foreign.name)
        self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_save_refresh_and_replay_preserve_one_config(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url(), self.data())
        self.assertRedirects(response, self.url())
        saved = self.config()
        self.assertTrue(saved.enabled)
        self.assertEqual(saved.daily_request_limit, 400)
        response = self.client.get(self.url())
        self.assertEqual(response.context['form']['version'].value(), saved.version)
        replay = self.client.post(self.url(), self.data())
        self.assertEqual(replay.status_code, 409)
        self.assertEqual(self.config().pk, saved.pk)

    def test_stale_save_keeps_input_and_reports_conflict_without_false_success(self):
        self.client.force_login(self.admin)
        self.client.post(self.url(), self.data())
        response = self.client.post(self.url(), self.data(local_model='unsaved-model'))
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, 'unsaved-model', status_code=409)
        self.assertNotEqual(self.config().local_model, 'unsaved-model')

    def test_checkboxes_can_be_disabled_without_reusing_saved_true_values(self):
        self.client.force_login(self.admin)
        self.client.post(self.url(), self.data())
        payload = self.data(version=str(self.config().version))
        payload.pop('enabled')
        response = self.client.post(self.url(), payload)
        self.assertRedirects(response, self.url())
        self.assertFalse(self.config().enabled)

    def test_invalid_input_remains_visible_and_does_not_persist(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url(), self.data(request_timeout='601', local_model='still-my-input'))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'still-my-input', status_code=400)
        self.assertContains(response, '600', status_code=400)
        from .ai_processing_models import AIProcessingSettings
        self.assertFalse(AIProcessingSettings.objects.exists())

    def test_secret_injection_is_rejected_without_echo_or_audit(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url(), self.data(api_key='fixture-private-value'))
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, 'fixture-private-value', status_code=400)
        self.assertFalse(GovernanceAudit.objects.filter(action='ai_settings_updated').exists())

    def test_external_provider_requires_disclosure_and_server_alias(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url(), self.data(primary_provider='https_ollama', api_model='vision', api_endpoint='private-gateway'))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'external', status_code=400)
        response = self.client.post(self.url(), self.data(primary_provider='https_ollama', api_model='vision', api_endpoint='https://arbitrary.example/', allow_external_evidence='on'))
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(self.client.get(self.url()), 'https://gateway.example.test')

    def test_csrf_is_required_for_authenticated_save(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(self.url(), self.data()).status_code, 403)

    def test_locked_and_pending_admins_are_denied_using_current_authority(self):
        self.client.force_login(self.admin)
        Profile.objects.filter(user=self.admin).update(is_locked=True)
        self.assertEqual(self.client.get(self.url()).status_code, 403)
        Profile.objects.filter(user=self.admin).update(is_locked=False, admin_industry_pending=True)
        self.assertEqual(self.client.post(self.url(), self.data()).status_code, 403)

    def test_settings_page_is_private_and_does_not_offer_model_execution(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url())
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertNotContains(response, 'TEST_PRIVATE_CREDENTIAL')
        self.assertNotContains(response, 'Run AI now')
