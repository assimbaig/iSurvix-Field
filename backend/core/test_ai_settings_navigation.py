"""The real shared shell exposes company AI administration only to its roles."""
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class AISettingsNavigationTests(SimpleTestCase):
    def test_administrators_can_find_settings_from_the_existing_navigation(self):
        for role in ('ADMIN', 'SUPER_ADMIN'):
            with self.subTest(role=role):
                html = render_to_string('dashboards/_primary_navigation.html', {
                    'role_design': {'role': role}, 'active_view': 'ai_settings'})
                self.assertIn('>AI Settings</a>', html)
                self.assertIn('aria-current="page">AI Settings', html)

    def test_operational_roles_do_not_get_company_configuration_actions(self):
        for role in ('ENGINEER', 'QUALITY_ENGINEER', 'TEAM_LEAD', 'CLIENT'):
            with self.subTest(role=role):
                html = render_to_string('dashboards/_primary_navigation.html', {
                    'role_design': {'role': role}, 'active_view': 'tasks'})
                self.assertNotIn('>AI Settings</a>', html)
