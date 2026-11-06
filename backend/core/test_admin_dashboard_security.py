"""Independent adversarial checks for the company Admin overview.

Only synthetic records are used. A failing assertion is retained as evidence;
this review does not modify implementation or waive approval requirements.
"""
import hashlib
import json
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from .admin_dashboard import build_admin_dashboard
from .models import (
    Checklist, ClientOrganization, Company, GovernanceAudit, IndustryCatalog,
    PhotoEvidence, PhotoPlacement, Profile, Project, ProjectInvitation,
    ProjectMembership, ReviewRoute, WorkAssignment,
)


@override_settings(
    ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False, NOTIFICATION_EMAIL_ENABLED=False,
    WORKFLOW_NOTIFICATION_EMAIL_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class AdminDashboardSecurityTests(TestCase):
    def setUp(self):
        self.industry = IndustryCatalog.objects.get(code='telecom')
        self.company = Company.objects.create(name='AppSec company A')
        self.outside = Company.objects.create(name='AppSec company B sentinel')
        self.admin = self.person('appsec_owner', Profile.Roles.ADMIN)
        self.peer = self.person('appsec_peer_owner', Profile.Roles.ADMIN)
        self.other_admin = self.person('appsec_other_owner', Profile.Roles.ADMIN, company=self.outside)
        self.project = self.project_for('AppSec visible project', self.admin)
        self.peer_project = self.project_for('AppSec other owner private sentinel', self.peer)
        self.foreign_project = self.project_for('AppSec foreign project private sentinel', self.other_admin, self.outside)
        self.engineer = self.person('appsec_engineer', Profile.Roles.ENGINEER, self.project)
        self.customer = self.person('appsec_customer', Profile.Roles.CLIENT, self.project)
        self.checklist = Checklist.objects.create(user=self.engineer, project=self.project,
            site_id='VISIBLE-SITE', status=Checklist.Status.REVIEW)
        ReviewRoute.objects.create(checklist=self.checklist, layer_count=3, stage='quality_engineer')
        WorkAssignment.objects.create(project=self.project, site_id=self.checklist.site_id,
            assigned_to=self.engineer, assigned_by=self.admin, latitude=0, longitude=0,
            description='Synthetic linked work', checklist=self.checklist)
        self.photo = self.photo_for(self.checklist, 'visible')
        for field in ('one', 'two', 'three'):
            PhotoPlacement.objects.create(photo=self.photo, field_id=field, section_id='civil',
                schema_digest='f' * 64, status='confirmed')
        for project in (self.peer_project, self.foreign_project):
            record = Checklist.objects.create(user=self.engineer, project=project,
                site_id='PRIVATE-SITE-' + str(project.pk), status=Checklist.Status.REVIEW)
            self.photo_for(record, 'hidden-' + str(project.pk))
            GovernanceAudit.objects.create(project=project, actor_name='PRIVATE-ACTOR-SENTINEL',
                action='private_event_sentinel', details={'site_id': 'PRIVATE-SITE-SENTINEL'})
        self.client.force_login(self.admin)

    def person(self, name, role, project=None, company=None):
        user = User.objects.create_user(name, email=name + '@example.test', password='Synthetic-AppSec-only!')
        profile = user.profile
        profile.role = role
        profile.company = company or self.company
        profile.project = project
        if role == Profile.Roles.ADMIN:
            profile.admin_industry = self.industry
        profile.save()
        if project:
            ProjectMembership.objects.create(user=user, project=project, is_active=True)
        return user

    def project_for(self, name, admin, company=None):
        project = Project.objects.create(name=name, company=company or self.company,
            administrator=admin, industry=self.industry.code, review_layers=3)
        ProjectMembership.objects.create(user=admin, project=project, is_active=True)
        return project

    def photo_for(self, checklist, key):
        return PhotoEvidence.objects.create(checklist=checklist, uploaded_by=self.engineer,
            filename=key + '.jpg', sha256=hashlib.sha256(key.encode()).hexdigest(),
            original='synthetic/' + key + '.jpg', preview='synthetic/' + key + '-preview.jpg',
            analysis_metadata={'private_secret': 'PHOTO-ANALYSIS-MUST-NOT-RENDER'})

    def home(self, **query):
        return self.client.get(reverse('governance_home'), {'view': 'dashboard', **query})

    def test_injected_foreign_grants_and_same_company_owners_do_not_expand_summary(self):
        ProjectMembership.objects.create(user=self.admin, project=self.foreign_project,
            is_active=True, legacy_admin_access=True)
        ProjectMembership.objects.create(user=self.admin, project=self.peer_project, is_active=True)
        foreign_person = self.person('appsec_foreign_member', Profile.Roles.ENGINEER,
            company=self.outside)
        ProjectMembership.objects.create(user=foreign_person, project=self.project, is_active=True)
        response = self.home()
        self.assertEqual(response.status_code, 200)
        data = response.context['admin_dashboard']
        self.assertEqual(data['summary']['projects'], 1)
        self.assertEqual(data['summary']['photos'], 1)
        self.assertEqual(data['summary']['activities'], 1)
        self.assertEqual(data['summary']['sites'], 1)
        self.assertEqual(data['summary']['people'], 3)
        for sentinel in ('private sentinel', 'PRIVATE-ACTOR-SENTINEL', 'PRIVATE-SITE-SENTINEL',
                         'PHOTO-ANALYSIS-MUST-NOT-RENDER'):
            self.assertNotContains(response, sentinel)
        for project in (self.peer_project, self.foreign_project):
            self.assertEqual(self.home(project=project.pk).status_code, 404)

    def test_direct_helper_cannot_broaden_scope_or_use_stale_authority(self):
        request = RequestFactory().get('/governance/?view=dashboard')
        request.user = self.admin
        data = build_admin_dashboard(request, Project.objects.all())
        self.assertEqual(data['summary']['projects'], 1)
        self.assertEqual(data['summary']['photos'], 1)
        # Cached actor.profile remains Admin, persisted authority is revoked.
        _ = self.admin.profile.role
        Profile.objects.filter(user=self.admin).update(role=Profile.Roles.ENGINEER)
        with self.assertRaises(PermissionDenied):
            build_admin_dashboard(request, Project.objects.all())

    def test_inactive_locked_and_revoked_accounts_cannot_read_cached_dashboard(self):
        for field in ('is_active', 'is_locked', 'membership'):
            with self.subTest(field=field):
                actor = self.person('appsec_revoked_' + field, Profile.Roles.ADMIN)
                project = self.project_for('Revoked visible ' + field, actor)
                self.client.force_login(actor)
                self.assertEqual(self.home().status_code, 200)
                if field == 'is_active':
                    User.objects.filter(pk=actor.pk).update(is_active=False)
                elif field == 'is_locked':
                    Profile.objects.filter(user=actor).update(is_locked=True)
                else:
                    ProjectMembership.objects.filter(user=actor, project=project).update(is_active=False)
                response = self.home()
                if field == 'membership':
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.context['admin_dashboard']['summary']['projects'], 0)
                    self.assertNotContains(response, project.name)
                else:
                    self.assertIn(response.status_code, (302, 403))
                    self.assertNotContains(response, 'id="admin-dashboard"', status_code=response.status_code)

    def test_foreign_client_reference_does_not_leak_through_name_or_search(self):
        foreign = ClientOrganization.objects.create(name='FOREIGN-CLIENT-NAME-SENTINEL',
            company=self.outside, industry=self.industry, created_by=self.other_admin)
        Project.objects.filter(pk=self.project.pk).update(client_organization=foreign)
        response = self.home()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, foreign.name)
        self.assertEqual(response.context['admin_dashboard']['summary']['clients'], 0)
        response = self.home(admin_project_q=foreign.name)
        self.assertEqual(response.context['admin_dashboard']['projects'], [])
        self.assertNotContains(response, foreign.name + '</')

    def test_union_aggregate_treats_site_text_as_data_and_counts_ids_once(self):
        payload = "x') UNION SELECT 99,99; --"
        Checklist.objects.filter(pk=self.checklist.pk).update(site_id=payload)
        WorkAssignment.objects.filter(checklist=self.checklist).update(site_id=payload)
        response = self.home()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['admin_dashboard']['summary']['sites'], 1)
        self.assertEqual(response.context['admin_dashboard']['summary']['photos'], 1)
        self.assertTrue(Project.objects.filter(pk=self.foreign_project.pk).exists())
        self.assertEqual(response.context['admin_dashboard']['projects'][0]['site_count'], 1)

    def test_project_identifiers_are_bounded_and_fail_without_server_error(self):
        for view in ('dashboard', 'my_work'):
            for value in ('-1', '１２', '1 OR 1=1', '9' * 19, '9' * 1000, '9' * 5000):
                with self.subTest(view=view, value_length=len(value)):
                    client = Client(raise_request_exception=False)
                    client.force_login(self.admin)
                    response = client.get(reverse('governance_home'), {'view': view, 'project': value})
                    self.assertIn(response.status_code, (400, 404))
                    self.assertNotContains(response, 'id="admin-dashboard"', status_code=response.status_code)

    def test_search_and_pagination_payloads_remain_data_and_metadata_stays_private(self):
        payload = '\"><script>window.appsecInjected=1</script>'
        response = self.home(admin_project_q=payload, admin_projects_page='9' * 5000,
            next='https://attacker.example/steal')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<script>window.appsecInjected=1</script>')
        self.assertTrue({'private', 'no-store'}.issubset(
            {part.strip() for part in response['Cache-Control'].split(',')}))
        self.assertNotContains(response, 'PHOTO-ANALYSIS-MUST-NOT-RENDER')

    def test_stored_project_company_audit_names_are_escaped(self):
        payload = '<script>window.appsecStored=1</script>'
        Company.objects.filter(pk=self.company.pk).update(name='Company ' + payload)
        Project.objects.filter(pk=self.project.pk).update(name='Project ' + payload)
        GovernanceAudit.objects.create(project=self.project, actor_name='Actor ' + payload,
            action='untrusted_' + payload, details={'site_id': payload, 'client_secret': 'AUDIT-SECRET-SENTINEL'})
        response = self.home()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, payload)
        self.assertContains(response, '&lt;script&gt;window.appsecStored=1&lt;/script&gt;')
        self.assertNotContains(response, 'AUDIT-SECRET-SENTINEL')

    def test_csrf_is_required_for_all_dashboard_mutations(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.get(reverse('governance_home')).status_code, 200)
        before = (Project.objects.count(), ClientOrganization.objects.count(), ProjectInvitation.objects.count())
        for name, data in (
            ('governance_projects', {'name': 'CSRF project', 'review_layers': 3}),
            ('governance_company', {'name': 'CSRF client'}),
            ('governance_invite', {'project': self.project.pk, 'email': 'csrf@example.test', 'role': Profile.Roles.ENGINEER}),
        ):
            with self.subTest(route=name):
                response = client.post(reverse(name), {**data, 'return_view': 'dashboard'})
                self.assertEqual(response.status_code, 403)
        self.assertEqual(before, (Project.objects.count(), ClientOrganization.objects.count(), ProjectInvitation.objects.count()))

    def test_nonadmin_direct_posts_and_admin_invite_escalation_are_denied(self):
        self.client.force_login(self.engineer)
        for route, data in (
            ('governance_projects', {'name': 'Unauthorized project', 'review_layers': 3}),
            ('governance_company', {'name': 'Unauthorized client'}),
            ('governance_invite', {'project': self.project.pk, 'email': 'unauthorized@example.test', 'role': Profile.Roles.CLIENT}),
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.post(reverse(route), {**data, 'return_view': 'dashboard'}).status_code, 403)
        self.client.force_login(self.admin)
        for role in (Profile.Roles.ADMIN, Profile.Roles.SUPER_ADMIN):
            response = self.client.post(reverse('governance_invite'), {'return_view': 'dashboard',
                'project': self.project.pk, 'email': 'elevated@example.test', 'role': role})
            self.assertIn(response.status_code, (400, 403))
        self.assertFalse(ProjectInvitation.objects.exists())

    def test_safe_return_hints_cannot_redirect_or_assign_authority(self):
        response = self.client.post(reverse('governance_company'), {
            'name': 'AppSec saved client', 'return_view': 'dashboard',
            'dashboard_project': self.foreign_project.pk, 'dashboard_industry': "<script>evil</script>",
            'next': 'https://attacker.example/steal', 'company': self.outside.pk,
            'industry': self.industry.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.url).netloc, '')
        self.assertEqual(urlsplit(response.url).path, reverse('governance_home'))
        self.assertEqual(parse_qs(urlsplit(response.url).query)['project'], ['all'])
        record = ClientOrganization.objects.get(name='AppSec saved client')
        self.assertEqual((record.company_id, record.industry_id), (self.company.pk, self.industry.pk))

    def test_invitation_bearer_is_shown_only_to_authorized_issuer_and_not_persisted_raw(self):
        response = self.client.post(reverse('governance_invite'), {'return_view': 'dashboard',
            'project': self.project.pk, 'email': 'appsec_invitee@example.test', 'role': Profile.Roles.ENGINEER})
        self.assertEqual(response.status_code, 200)
        invitation_url = response.context['invite_url']
        token = urlsplit(invitation_url).path.rstrip('/').rsplit('/', 1)[-1]
        self.assertGreater(len(token), 16)
        self.assertTrue(ProjectInvitation.objects.filter(token_hash=hashlib.sha256(token.encode()).hexdigest()).exists())
        self.assertNotIn(token, json.dumps(dict(self.client.session.items()), default=str))
        self.assertFalse(any(token in json.dumps(row, default=str) for row in GovernanceAudit.objects.values('details')))
        self.assertNotContains(response, 'Email sent')
        self.client.force_login(self.other_admin)
        self.assertNotContains(self.home(), token)

    def test_overview_does_not_mutate_technical_decisions_or_read_photo_analysis(self):
        before = (Checklist.objects.get(pk=self.checklist.pk).status,
            list(PhotoPlacement.objects.filter(photo=self.photo).values('field_id', 'status')),
            GovernanceAudit.objects.count())
        with CaptureQueriesContext(connection) as queries:
            response = self.home(project=self.project.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(before, (Checklist.objects.get(pk=self.checklist.pk).status,
            list(PhotoPlacement.objects.filter(photo=self.photo).values('field_id', 'status')),
            GovernanceAudit.objects.count()))
        sql = '\n'.join(row['sql'] for row in queries.captured_queries).lower()
        self.assertNotIn('"core_photoevidence"."analysis_metadata"', sql)
        self.assertNotIn('"core_photoanalysis"', sql)

    def test_expired_grants_do_not_reappear_via_primary_profile(self):
        actor = self.person('appsec_expired_primary', Profile.Roles.ENGINEER, self.project)
        ProjectMembership.objects.filter(user=actor).update(expires_at=timezone.now()-timedelta(seconds=1))
        response = self.home()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['admin_dashboard']['summary']['people'], 3)
