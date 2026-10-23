"""Hosted navigation and evidence capture work without a local inference server."""
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Checklist, Profile, Project


@override_settings(
    DEBUG=False,
    LOCAL_AI_ENABLED=False,
    ROOT_URLCONF='checklist.urls',
    ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=True,
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
    MIDDLEWARE=[entry for entry in settings.MIDDLEWARE
                if entry != 'core.local_ai.LoopbackOnlyMiddleware'],
)
class ProductionWorkspaceTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name='Hosted workspace fixture')
        self.admin = User.objects.create_superuser(
            'hosted-super-admin', 'hosted@example.test', password=None)
        self.engineer = self.person('hosted-engineer', Profile.Roles.ENGINEER)
        self.lead = self.person('hosted-lead', Profile.Roles.TEAM_LEAD)
        self.survey = Checklist.objects.create(
            user=self.engineer, project=self.project, site_id='HOSTED-SYNTHETIC',
            schema_snapshot={'title': 'Hosted fixture', 'sections': [{
                'id': 'general', 'title': 'General', 'fields': [{
                    'id': 'condition', 'label': 'Condition', 'type': 'text',
                }],
            }]},
        )

    def person(self, username, role, project=None):
        user = User.objects.create_user(username)
        user.profile.role = role
        user.profile.project = project or self.project
        user.profile.save()
        return user

    def page(self, url):
        return self.client.get(url, secure=True, REMOTE_ADDR='198.51.100.20')

    def test_super_admin_keeps_navigation_layout_and_account_controls(self):
        self.client.force_login(self.admin)
        response = self.page(reverse('governance_home'))
        self.assertContains(response, 'id="role-navigation"')
        self.assertContains(response, 'data-layout="enterprise"')
        self.assertContains(response, 'core/css/enterprise.css')
        self.assertContains(response, 'aria-label="Logout"')
        self.assertFalse(response.context['local_ai_enabled'])

    def test_engineer_keeps_task_navigation_and_scoped_project_selector(self):
        Project.objects.create(name='Unrelated private project')
        self.client.force_login(self.engineer)
        response = self.page(reverse('governance_home'))
        self.assertContains(response, 'id="role-navigation"')
        self.assertContains(response, 'My tasks')
        self.assertContains(response, 'id="enterprise-project"')
        self.assertEqual(
            [project.pk for project in response.context['shell_projects']],
            [self.project.pk],
        )
        self.assertContains(response, 'Hosted workspace fixture')
        self.assertNotContains(response, 'Unrelated private project')

    def test_engineer_can_open_photos_and_find_upload_link_without_local_ai(self):
        self.client.force_login(self.engineer)
        response = self.page(reverse('custom_checklist', args=[self.survey.pk]))
        photo_url = reverse('photo_workspace', args=[self.survey.pk])
        self.assertRedirects(response,photo_url,fetch_redirect_response=False)
        page=self.page(photo_url)
        self.assertEqual(page.status_code,200)
        self.assertContains(page,'id="capture-upload-form"')

    def test_readonly_review_keeps_photo_view_but_hides_upload_control(self):
        self.survey.status = Checklist.Status.FINAL
        self.survey.save()
        self.client.force_login(self.lead)
        response = self.page(reverse('custom_checklist', args=[self.survey.pk]))
        self.assertContains(
            response, f'href="{reverse("photo_workspace", args=[self.survey.pk])}"')
        self.assertNotContains(response, 'id="upload-site-photos"')

    def test_unrelated_engineer_cannot_open_survey_or_evidence(self):
        other = Project.objects.create(name='Other hosted project')
        outsider = self.person('hosted-outsider', Profile.Roles.ENGINEER, other)
        self.client.force_login(outsider)
        for name in ('custom_checklist', 'photo_workspace'):
            with self.subTest(route=name):
                response = self.page(reverse(name, args=[self.survey.pk]))
                self.assertIn(response.status_code, (403, 404))

    def test_anonymous_login_has_no_role_navigation_and_http_redirects(self):
        response = self.page(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="role-navigation"')
        self.assertEqual(self.client.get(reverse('login')).status_code, 301)
        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.CSRF_COOKIE_SECURE)
        self.assertFalse(settings.DEBUG)
        self.assertFalse(settings.LOCAL_AI_ENABLED)
