"""Independent company and explicit project-membership authorization tests."""
import hashlib
from datetime import timedelta
from django.contrib.auth.models import User
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import Company, Project, Profile, ProjectMembership, ChecklistTemplate, Checklist, ProjectInvitation, ClientOrganization, IndustryCatalog
from .access import can_access_project, user_project_ids


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CompanyAccessTests(TestCase):
    def setUp(self):
        self.company=Company.objects.create(name='Synthetic company A')
        self.foreign_company=Company.objects.create(name='Synthetic company B')
        schema={'title':'Membership fixture','sections':[{'id':'general','title':'General','fields':[{'id':'condition','label':'Condition','type':'text'}]}]}
        self.template=ChecklistTemplate.objects.create(name='Membership fixture',definition=schema,published=True)
        self.a=Project.objects.create(name='Synthetic project A',company=self.company,checklist_template=self.template)
        self.b=Project.objects.create(name='Synthetic project B',company=self.company,checklist_template=self.template)
        self.c=Project.objects.create(name='Synthetic project C',company=self.company,checklist_template=self.template)
        self.foreign=Project.objects.create(name='Foreign company project',company=self.foreign_company,checklist_template=self.template)
        self.super=self.person('membership_super',Profile.Roles.SUPER_ADMIN,superuser=True)
        self.admin=self.person('membership_admin',Profile.Roles.ADMIN,self.a)
        self.engineer=self.person('membership_engineer',Profile.Roles.ENGINEER,self.a)
        self.lead=self.person('membership_lead',Profile.Roles.TEAM_LEAD,self.a)
        self.reviewer=self.person('membership_client',Profile.Roles.CLIENT,self.a)
        self.client.force_login(self.super)
        self.assertEqual(self.change(self.admin,self.b).status_code,302)
        self.client.force_login(self.admin)

    def person(self,name,role,project=None,superuser=False):
        user=User.objects.create_user(name,email=name+'@example.test',password='Membership-fixture-381!')
        user.is_superuser=superuser
        user.save()
        user.profile.role=role
        user.profile.project=project
        user.profile.company=project.company if project else None
        user.profile.save()
        if project:
            ProjectMembership.objects.create(user=user,project=project,is_primary=True)
        return user

    def change(self,user,project,action='grant',primary=False):
        return self.client.post(reverse('governance_membership',args=[user.pk]),{'project':project.pk,'action':action,'make_primary':'on' if primary else ''})

    def test_admin_multi_project_scope_requires_explicit_same_company_grants(self):
        self.admin.refresh_from_db()
        self.assertEqual(set(user_project_ids(self.admin)),{self.a.pk,self.b.pk})
        self.assertFalse(can_access_project(self.admin,self.c))
        self.assertFalse(can_access_project(self.admin,self.foreign))
        for user in [self.engineer,self.lead,self.reviewer]:
            self.assertFalse(can_access_project(user,self.b))
            self.assertEqual(self.change(user,self.b).status_code,302)
            user.refresh_from_db()
            self.assertTrue(can_access_project(user,self.b))
            self.assertEqual(user.profile.project,self.a)
            self.assertEqual(user.profile.company,self.company)
        self.assertEqual(self.change(self.engineer,self.c).status_code,400)
        self.assertEqual(self.change(self.engineer,self.foreign).status_code,400)
        self.assertEqual(self.change(self.admin,self.b).status_code,403)

    def test_workspace_primary_default_explicit_project_all_and_foreign_scope(self):
        for user in [self.engineer,self.lead,self.reviewer]:
            self.assertEqual(self.change(user,self.b).status_code,302)
            for project in [self.a,self.b]:
                Checklist.objects.create(user=user,project=project,site_id=f'{user.pk}-PROJECT-{project.pk}',status=Checklist.Status.FINAL)
            browser=Client()
            browser.force_login(user)
            response=browser.get(reverse('governance_home'))
            self.assertEqual(response.status_code,200)
            self.assertEqual({p.pk for p in response.context['projects']},{self.a.pk})
            response=browser.get(reverse('governance_home'),{'project':self.b.pk})
            self.assertEqual({p.pk for p in response.context['projects']},{self.b.pk})
            response=browser.get(reverse('governance_home'),{'project':'all'})
            self.assertEqual({p.pk for p in response.context['projects']},{self.a.pk,self.b.pk})
            for invalid in [self.c.pk,self.foreign.pk,'not-a-project']:
                self.assertEqual(browser.get(reverse('governance_home'),{'project':invalid}).status_code,404)
        response=self.client.get(reverse('governance_home'))
        self.assertEqual({p.pk for p in response.context['projects']},{self.a.pk,self.b.pk})

    def test_primary_switch_and_revocation_preserve_history_without_fallback_access(self):
        survey=Checklist.objects.create(user=self.engineer,project=self.a,site_id='PRESERVED-HISTORY',status=Checklist.Status.FINAL,answer_data={'custom':{'condition':'Keep'}},section_approvals={'general':{'by':self.lead.pk}})
        self.assertEqual(self.change(self.engineer,self.b,primary=True).status_code,302)
        self.engineer.profile.refresh_from_db()
        self.assertEqual(self.engineer.profile.project,self.b)
        self.assertEqual(self.change(self.engineer,self.b,'revoke').status_code,302)
        self.engineer.refresh_from_db()
        self.assertEqual(self.engineer.profile.project,self.a)
        self.assertFalse(can_access_project(self.engineer,self.b))
        self.assertEqual(self.change(self.engineer,self.a,'revoke').status_code,302)
        self.engineer.refresh_from_db()
        self.assertIsNone(self.engineer.profile.project)
        # A stale legacy primary pointer must not restore an explicitly revoked grant.
        Profile.objects.filter(user=self.engineer).update(project=self.a)
        self.engineer.refresh_from_db()
        self.assertFalse(can_access_project(self.engineer,self.a))
        browser=Client()
        browser.force_login(self.engineer)
        self.assertEqual(browser.get(reverse('custom_checklist',args=[survey.pk])).status_code,404)
        survey.refresh_from_db()
        self.assertEqual(survey.answer_data,{'custom':{'condition':'Keep'}})
        self.assertEqual(survey.section_approvals,{'general':{'by':self.lead.pk}})
        self.assertEqual(survey.status,Checklist.Status.FINAL)

    def test_cross_company_grants_and_reclassification_cannot_transfer_access(self):
        outsider=self.person('other_company_engineer',Profile.Roles.ENGINEER,self.foreign)
        self.assertEqual(self.change(outsider,self.a).status_code,400)
        self.client.force_login(self.super)
        self.assertEqual(self.change(self.engineer,self.foreign).status_code,400)
        self.assertEqual(self.client.post(reverse('governance_project_company',args=[self.a.pk]),{'company':self.foreign_company.pk}).status_code,409)
        self.a.refresh_from_db()
        self.assertEqual(self.a.company,self.company)
        self.engineer.refresh_from_db()
        self.assertEqual(self.engineer.profile.company,self.company)
        self.assertFalse(can_access_project(self.engineer,self.foreign))

    def test_account_wide_actions_require_all_target_projects_but_scoped_revoke_allowed(self):
        self.client.force_login(self.super)
        self.assertEqual(self.change(self.engineer,self.c).status_code,302)
        self.client.force_login(self.admin)
        url=reverse('governance_member',args=[self.engineer.pk])
        for payload in [{'action':'deactivate'},{'action':'role','role':Profile.Roles.TEAM_LEAD},{'action':'unlock'}]:
            self.assertEqual(self.client.post(url,payload).status_code,403)
        self.assertEqual(self.change(self.engineer,self.a,'revoke').status_code,302)
        self.engineer.refresh_from_db()
        self.assertTrue(self.engineer.is_active)
        self.assertEqual(self.engineer.profile.role,Profile.Roles.ENGINEER)
        self.assertTrue(can_access_project(self.engineer,self.c))
        self.assertFalse(can_access_project(self.engineer,self.a))

    def test_invitation_acceptance_rechecks_issuer_revoked_additional_project(self):
        response=self.client.post(reverse('governance_invite'),{'email':'revoked-issuer@example.test','role':Profile.Roles.ENGINEER,'project':self.b.pk})
        self.assertEqual(response.status_code,200)
        path=__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(response.context['invite_url']).path
        self.client.force_login(self.super)
        self.assertEqual(self.change(self.admin,self.b,'revoke').status_code,302)
        response=Client().post(path,{'username':'must_not_be_created','email':'revoked-issuer@example.test','password1':'Invited-fixture-842!','password2':'Invited-fixture-842!'})
        self.assertEqual(response.status_code,404)
        self.assertFalse(User.objects.filter(username='must_not_be_created').exists())

    def test_additional_client_membership_triggers_snapshot_and_cannot_be_removed_to_bypass(self):
        from .workflow_service import configured_client_review,internal_review_completed
        from django.db import transaction
        self.assertFalse(configured_client_review(self.b.pk))
        self.assertEqual(self.change(self.reviewer,self.b).status_code,302)
        self.assertTrue(configured_client_review(self.b.pk))
        survey=Checklist.objects.create(user=self.engineer,project=self.b,site_id='ADDITIONAL-CLIENT-REVIEW',status=Checklist.Status.FINAL)
        with transaction.atomic():
            internal_review_completed(survey,self.lead)
        survey.refresh_from_db()
        self.assertTrue(survey.client_review_required)
        self.assertEqual(self.change(self.reviewer,self.b,'revoke').status_code,302)
        self.assertFalse(configured_client_review(self.b.pk))
        survey.refresh_from_db()
        self.assertTrue(survey.client_review_required)

    def test_membership_company_actions_require_role_authentication_and_csrf(self):
        paths=[reverse('governance_membership',args=[self.engineer.pk]),reverse('governance_company'),reverse('governance_project_company',args=[self.a.pk])]
        strict=Client(enforce_csrf_checks=True)
        strict.force_login(self.super)
        for path in paths:
            self.assertEqual(strict.post(path,{'project':self.b.pk,'action':'grant','company':self.company.pk}).status_code,403)
            self.assertIn(Client().post(path).status_code,(302,403))
        for actor in [self.engineer,self.lead,self.reviewer]:
            self.client.force_login(actor)
            self.assertEqual(self.change(self.engineer,self.b).status_code,403)
            self.assertEqual(self.client.post(reverse('governance_company'),{'name':'Forbidden company'}).status_code,403)
        self.assertFalse(Company.objects.filter(name='Forbidden company').exists())
        self.assertFalse(ClientOrganization.objects.filter(name='Forbidden company').exists())
        self.admin.profile.admin_industry=IndustryCatalog.objects.get(code='telecom')
        self.admin.profile.save()
        self.client.force_login(self.admin)
        employers=Company.objects.count()
        self.assertEqual(self.client.post(reverse('governance_company'),{'name':'Authorized scoped client'}).status_code,302)
        organization=ClientOrganization.objects.get(name='Authorized scoped client')
        self.assertEqual(organization.company_id,self.company.pk)
        self.assertEqual(organization.created_by_id,self.admin.pk)
        self.assertEqual(Company.objects.count(),employers)

    def test_super_assigns_admin_additional_project_without_moving_primary(self):
        self.client.force_login(self.super)
        response=self.client.post(reverse('governance_project_admin',args=[self.b.pk]),{'administrator':self.admin.pk})
        self.assertEqual(response.status_code,302)
        self.admin.refresh_from_db()
        self.b.refresh_from_db()
        self.assertEqual(self.admin.profile.project,self.a)
        self.assertEqual(self.b.administrator,self.admin)
        self.assertEqual(set(user_project_ids(self.admin)),{self.a.pk,self.b.pk})
        self.assertEqual(self.client.post(reverse('governance_project_admin',args=[self.foreign.pk]),{'administrator':self.admin.pk}).status_code,400)

class CompanyMigrationPreservationTests(TransactionTestCase):
    def test_company_migration_preserves_legacy_scope_without_extra_grants(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        previous=[('core','0019_client_review_routing')]
        executor=MigrationExecutor(connection)
        latest=executor.loader.graph.leaf_nodes()
        executor.migrate(previous)
        try:
            apps=executor.loader.project_state(previous).apps
            OldUser=apps.get_model('auth','User')
            OldProfile=apps.get_model('core','Profile')
            OldProject=apps.get_model('core','Project')
            OldChecklist=apps.get_model('core','Checklist')
            a=OldProject.objects.create(name='Legacy migration A')
            b=OldProject.objects.create(name='Legacy migration B')
            c=OldProject.objects.create(name='Legacy migration unassigned')
            first=OldUser.objects.create(username='legacy_migration_engineer')
            second=OldUser.objects.create(username='legacy_migration_lead')
            unassigned=OldUser.objects.create(username='legacy_migration_unassigned')
            OldProfile.objects.create(user_id=first.pk,role='ENGINEER',project_id=a.pk)
            OldProfile.objects.create(user_id=second.pk,role='TEAM_LEAD',project_id=b.pk)
            OldProfile.objects.create(user_id=unassigned.pk,role='ENGINEER')
            survey=OldChecklist.objects.create(user_id=first.pk,project_id=a.pk,site_id='LEGACY-MIGRATION-HISTORY',status='FINAL',answer_data={'custom':{'condition':'Preserve'}},section_approvals={'general':{'by':second.pk}},client_review_required=False)
            MigrationExecutor(connection).migrate(latest)
            self.assertEqual(set(ProjectMembership.objects.values_list('user_id','project_id')),{(first.pk,a.pk),(second.pk,b.pk)})
            self.assertEqual(ProjectMembership.objects.filter(is_active=True,is_primary=True).count(),2)
            self.assertEqual(set(user_project_ids(User.objects.get(pk=first.pk))),{a.pk})
            self.assertEqual(set(user_project_ids(User.objects.get(pk=second.pk))),{b.pk})
            self.assertEqual(set(user_project_ids(User.objects.get(pk=unassigned.pk))),set())
            self.assertFalse(ProjectMembership.objects.filter(project_id=c.pk).exists())
            migrated=Checklist.objects.get(pk=survey.pk)
            self.assertEqual(migrated.status,'FINAL')
            self.assertIs(migrated.client_review_required,False)
            self.assertEqual(migrated.answer_data,{'custom':{'condition':'Preserve'}})
            self.assertEqual(migrated.section_approvals,{'general':{'by':second.pk}})
            self.assertEqual(Company.objects.count(),1)
        finally:
            MigrationExecutor(connection).migrate(latest)
