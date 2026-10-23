"""A hosted workspace offers only assistant URLs its deployment can resolve."""
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Profile, Project


@override_settings(
    DEBUG=False, ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=True,
    MIDDLEWARE=[entry for entry in settings.MIDDLEWARE
                if entry != 'core.local_ai.LoopbackOnlyMiddleware'],
)
class AssistantCapabilityTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name='Assistant capability fixture')

    def person(self, role):
        user = User.objects.create_user(
            'assistant-' + role.value.lower(),
            is_superuser=role == Profile.Roles.SUPER_ADMIN,
            is_staff=role == Profile.Roles.SUPER_ADMIN,
        )
        user.profile.role = role
        user.profile.project = self.project
        user.profile.save()
        return user

    def workspace(self, role):
        self.client.force_login(self.person(role))
        return self.client.get(reverse('governance_home'), secure=True)

    @override_settings(ROOT_URLCONF='checklist.urls', LOCAL_AI_ENABLED=False)
    def test_hosted_roles_have_no_missing_local_assistant_action(self):
        for role in (
            Profile.Roles.SUPER_ADMIN, Profile.Roles.ADMIN,
            Profile.Roles.TEAM_LEAD, Profile.Roles.QUALITY_ENGINEER,
            Profile.Roles.ENGINEER, Profile.Roles.CLIENT,
        ):
            with self.subTest(role=role):
                response = self.workspace(role)
                self.assertNotContains(response, 'href="/local/assistant/"')
                self.assertContains(response, 'id="role-navigation"')

    @override_settings(ROOT_URLCONF='checklist.urls', LOCAL_AI_ENABLED=True)
    def test_flag_alone_does_not_offer_an_unregistered_route(self):
        response = self.workspace(Profile.Roles.ENGINEER)
        self.assertFalse(response.context['local_assistant_available'])
        self.assertNotContains(response, 'href="/local/assistant/"')

    @override_settings(ROOT_URLCONF='checklist.urls_local', LOCAL_AI_ENABLED=False)
    def test_registered_route_is_not_offered_when_inference_is_disabled(self):
        response = self.workspace(Profile.Roles.ENGINEER)
        self.assertFalse(response.context['local_assistant_available'])
        self.assertNotContains(response, 'href="/local/assistant/"')

    @override_settings(ROOT_URLCONF='checklist.urls_local', LOCAL_AI_ENABLED=True)
    @patch('core.local_ai.ollama')
    def test_enabled_local_route_is_clickable_without_inference_on_render(self, model):
        response = self.workspace(Profile.Roles.ENGINEER)
        url = reverse('local_assistant')
        self.assertTrue(response.context['local_assistant_available'])
        self.assertContains(response, 'href="' + url + '"')
        self.assertEqual(self.client.get(url, secure=True).status_code, 200)
        model.assert_not_called()
