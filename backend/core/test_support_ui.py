"""Support workspace presentation contracts use rendered templates and saved records."""
from types import SimpleNamespace
import uuid

from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone


class SupportNavigationTests(SimpleTestCase):
    def shell(self, role):
        request = SimpleNamespace(
            user=SimpleNamespace(username='synthetic-support-user', is_authenticated=True),
            resolver_match=SimpleNamespace(url_name='support_index'),
        )
        return render_to_string('base.html', {
            'request': request,
            'role_design': {'role': role, 'layout': 'enterprise', 'palette': 'navy'},
            'active_view': 'support',
        })

    def test_current_administrators_can_find_support_in_existing_user_menu(self):
        for role in ('ADMIN', 'SUPER_ADMIN'):
            with self.subTest(role=role):
                html = self.shell(role)
                self.assertIn('System Health &amp; Support</a>', html)

    def test_operational_roles_do_not_receive_administrator_support_actions(self):
        for role in ('ENGINEER', 'QUALITY_ENGINEER', 'TEAM_LEAD', 'CLIENT'):
            with self.subTest(role=role):
                self.assertNotIn('System Health &amp; Support</a>', self.shell(role))


class SupportTemplateTests(SimpleTestCase):
    def context(self, owner=True):
        case = SimpleNamespace(
            pk=uuid.uuid4(), category='upload', get_category_display=lambda: 'Upload issue',
            description='A saved report <script>unsafe()</script>', project=None,
            company=None, created_at=timezone.now(), status='reported',
            status_label='Reported', version=1, source_release='a' * 40,
            report_digest='b' * 64,
        )
        return {
            'case': case, 'cases': [case], 'is_support_owner': owner,
            'can_import_receipt': owner, 'request_key': str(uuid.uuid4()),
            'category_choices': [('upload', 'Upload issue')], 'projects': [],
            'health': {'scope': 'company', 'label': 'Your company', 'release': 'unknown',
                       'metrics': [{'label': 'Queued jobs', 'value': None}],
                       'checks': [{'label': 'Database', 'status': 'unavailable'}]},
            'references': [{'label': 'Test evidence', 'value': 'Receipt recorded',
                            'provenance': 'Operator-attested'}],
            'events': [{'sequence': 1, 'created_at': timezone.now(), 'label': 'Report created',
                        'status': 'reported', 'status_label': 'Reported',
                        'actor_label': 'Synthetic administrator',
                        'summary': 'Diagnostic snapshot saved.', 'references': []}],
            'allowed_actions': [{'value': 'request_repair', 'label': 'Request isolated repair',
                                 'help': 'Prepare a separate review workspace.',
                                 'needs_reason': False, 'needs_pr_url': False}],
        }

    def test_index_is_a_real_scoped_report_form_with_honest_unknown_counts(self):
        html = render_to_string('support/index.html', self.context())
        for content in ('System Health &amp; Support', 'Your company', 'Queued jobs',
                        'Not available', 'name="category"', 'name="description"',
                        'name="request_key"', 'Saved reports'):
            self.assertIn(content, html)
        self.assertNotIn('Queued jobs</dt><dd>0', html)

    def test_detail_keeps_attestation_human_approval_and_review_history_distinct(self):
        html = render_to_string('support/detail.html', self.context())
        for content in ('Operator-attested', 'Report created', 'Diagnostic snapshot saved.',
                        'name="expected_version"', 'name="request_key"',
                        'name="receipt"', 'Request isolated repair'):
            self.assertIn(content, html)
        self.assertIn('&lt;script&gt;unsafe()&lt;/script&gt;', html)
        self.assertNotIn('<script>unsafe()</script>', html)

    def test_company_administrator_cannot_see_owner_receipt_or_approval_controls(self):
        html = render_to_string('support/detail.html', self.context(owner=False))
        self.assertNotIn('name="receipt"', html)
        self.assertNotIn('Request isolated repair', html)
        self.assertIn('Report created', html)

    def test_unavailable_health_shows_an_explicit_error_and_refresh_action(self):
        context = self.context()
        context.update(health=None, health_error='Diagnostics are temporarily unavailable.')
        html = render_to_string('support/index.html', context)
        self.assertIn('Diagnostics are temporarily unavailable.', html)
        self.assertIn('role="alert"', html)
        self.assertIn('Refresh health', html)


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False, ISURVIX_RELEASE_ID='a' * 40,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SavedSupportUITests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from .models import Company, Profile, Project, ProjectMembership
        self.company = Company.objects.create(name='Synthetic support UI company')
        self.project = Project.objects.create(name='Synthetic support UI project', company=self.company)
        self.owner = User.objects.create_superuser('support-ui-owner', 'owner@example.test', 'synthetic-password')
        self.admin = User.objects.create_user('support-ui-admin', password='synthetic-password')
        profile = self.admin.profile
        profile.role = Profile.Roles.ADMIN
        profile.company = self.company
        profile.project = self.project
        profile.save()
        ProjectMembership.objects.create(user=self.admin, project=self.project, is_primary=True)
        self.client.force_login(self.admin)

    def create_report(self):
        payload = {'category': 'upload', 'description': 'Upload stopped <script>unsafe()</script>',
                   'project_id': str(self.project.pk), 'request_key': str(uuid.uuid4())}
        response = self.client.post(reverse('support_case_create'), payload)
        self.assertEqual(response.status_code, 302)
        return response, payload

    def test_saved_report_and_export_are_reachable_after_refresh_without_duplicate_creation(self):
        from .support_models import SupportCase
        response, payload = self.create_report()
        replay = self.client.post(reverse('support_case_create'), payload)
        self.assertEqual(replay.url, response.url)
        self.assertEqual(SupportCase.objects.count(), 1)
        case = SupportCase.objects.get()
        detail = self.client.get(response.url)
        self.assertContains(detail, '&lt;script&gt;unsafe()&lt;/script&gt;')
        self.assertContains(detail, 'Report saved')
        self.assertNotContains(detail, 'name="receipt"')
        self.assertNotContains(detail, 'Platform owner actions')
        self.assertContains(self.client.get(reverse('support_index')), response.url)
        export = self.client.get(reverse('support_case_export', args=[case.pk]))
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export['Content-Type'], 'application/zip')
        self.assertIn('private', export['Cache-Control'])

    def test_invalid_report_keeps_entered_description_and_does_not_claim_success(self):
        from .support_models import SupportCase
        response = self.client.post(reverse('support_case_create'), {
            'category': 'not-an-issue', 'description': 'Keep my exact report draft',
            'project_id': str(self.project.pk), 'request_key': str(uuid.uuid4()),
        })
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'Keep my exact report draft', status_code=400)
        self.assertContains(response, 'role="alert"', status_code=400)
        self.assertEqual(SupportCase.objects.count(), 0)

    def test_owner_action_persists_and_invalid_receipt_keeps_input_and_saved_state(self):
        from .support_models import SupportCase
        response, _payload = self.create_report()
        case = SupportCase.objects.get()
        self.client.force_login(self.owner)
        before = self.client.get(response.url)
        self.assertContains(before, 'Request isolated repair')
        action = self.client.post(reverse('support_case_action', args=[case.pk]), {
            'action': 'request_repair', 'expected_version': case.version,
            'request_key': str(uuid.uuid4()),
        })
        self.assertEqual(action.status_code, 302)
        case = SupportCase.objects.get(pk=case.pk)
        self.assertEqual(case.status, 'repair_requested')
        detail = self.client.get(response.url)
        self.assertContains(detail, 'Awaiting isolated repair')
        self.assertContains(detail, 'name="receipt"')
        invalid = '{ "do not lose my input": '
        failed = self.client.post(reverse('support_case_receipt', args=[case.pk]), {
            'receipt': invalid, 'expected_version': case.version, 'request_key': str(uuid.uuid4()),
        })
        self.assertEqual(failed.status_code, 400)
        self.assertContains(failed, 'do not lose my input', status_code=400)
        self.assertContains(failed, 'The change was not saved.', status_code=400)
        self.assertEqual(SupportCase.objects.get(pk=case.pk).status, 'repair_requested')
