"""Notification controls are reachable through existing authorized workspaces."""
from django.test import TestCase, override_settings
from django.urls import reverse
from . import test_workflow_email as fixtures


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False, NOTIFICATION_EMAIL_ENABLED=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class NotificationNavigationTests(TestCase):
    setUp = fixtures.WorkflowEmailTests.setUp
    user = fixtures.WorkflowEmailTests.user

    def test_owner_finds_notifications_in_system_and_retains_system_selection(self):
        from django.contrib.auth.models import User
        owner = User.objects.create_superuser('notification-owner', 'owner@example.test', 'test')
        self.client.force_login(owner)
        response = self.client.get(reverse('governance_home'), {'view': 'system'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(('href="' + reverse('notification_settings_index') + '"').encode() in response.content, 'System must link to notification settings')
        response = self.client.get(reverse('notification_settings_index'))
        self.assertContains(response, 'aria-current="page">System')
        self.assertContains(response, '<span>Notification settings</span>', html=True)

    def test_company_admin_finds_own_settings_from_administration(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('governance_home'), {'view': 'administration'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(('href="' + reverse('notification_settings_index') + '"').encode() in response.content, 'Company administration must link to notification settings')
        self.assertRedirects(self.client.get(reverse('notification_settings_index')),
                             reverse('notification_settings_company', args=[self.company.pk]))
        self.assertEqual(self.client.get(reverse('notification_settings_company', args=[self.foreign.pk])).status_code, 403)

    def test_engineer_has_no_settings_action_or_access(self):
        self.client.force_login(self.engineer)
        response = self.client.get(reverse('governance_home'), {'view': 'my_work'})
        self.assertNotContains(response, 'href="' + reverse('notification_settings_index') + '"')
        self.assertEqual(self.client.get(reverse('notification_settings_index')).status_code, 403)
