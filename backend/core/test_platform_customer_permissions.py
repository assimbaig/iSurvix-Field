"""Platform/customer administration contracts, using isolated users and HTTP."""
import hashlib
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .access import role_for
from .models import Company, GovernanceAudit, IndustryCatalog, Profile, Project, ProjectInvitation, ProjectMembership


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PlatformCustomerPermissionTests(TestCase):
    def setUp(self):
        self.a=Company.objects.create(name='Synthetic administrative company A')
        self.b=Company.objects.create(name='Synthetic administrative company B')
        self.industry=IndustryCatalog.objects.get(code='telecom')
        self.pa=Project.objects.create(name='Synthetic administrative project A',company=self.a)
        self.pb=Project.objects.create(name='Synthetic administrative project B',company=self.b)
        self.owner=self.person('platform_owner',Profile.Roles.SUPER_ADMIN,superuser=True)
        self.admin=self.person('customer_admin',Profile.Roles.ADMIN,self.pa)
        self.foreign_admin=self.person('foreign_customer_admin',Profile.Roles.ADMIN,self.pb)
        self.engineer=self.person('administrative_engineer',Profile.Roles.ENGINEER,self.pa)
        self.lead=self.person('administrative_lead',Profile.Roles.TEAM_LEAD,self.pa)
        self.qa=self.person('administrative_quality',Profile.Roles.QUALITY_ENGINEER,self.pa)
        self.customer=self.person('administrative_client',Profile.Roles.CLIENT,self.pa)
        self.client.force_login(self.admin)

    def person(self,name,role,project=None,superuser=False):
        user=User.objects.create_user(name,email=name+'@example.test',password='Fixture-admin-849!')
        user.is_superuser=superuser;user.is_staff=superuser;user.save()
        profile=user.profile;profile.role=role;profile.project=project
        profile.company=project.company if project else None
        if role==Profile.Roles.ADMIN:profile.admin_industry=self.industry
        profile.save()
        return user

    def test_customer_member_update_rejects_protected_authority_fields_atomically(self):
        protected={'is_superuser':'1','is_staff':'1','groups':'1','user_permissions':'1',
                   'company':str(self.b.pk),'company_id':str(self.b.pk),
                   'admin_industry':str(self.industry.pk),'admin_industry_id':str(self.industry.pk)}
        for key,value in protected.items():
            with self.subTest(key=key):
                Profile.objects.filter(user=self.engineer).update(role=Profile.Roles.ENGINEER)
                before=GovernanceAudit.objects.count()
                response=self.client.post(reverse('governance_member',args=[self.engineer.pk]),
                    {'action':'role','role':Profile.Roles.TEAM_LEAD,key:value})
                self.assertEqual(response.status_code,400)
                self.engineer.refresh_from_db()
                self.assertEqual(self.engineer.profile.role,Profile.Roles.ENGINEER)
                self.assertFalse(self.engineer.is_staff or self.engineer.is_superuser)
                self.assertEqual(self.engineer.profile.company_id,self.a.pk)
                self.assertEqual(GovernanceAudit.objects.count(),before)

    def test_invitation_rejects_platform_flags_instead_of_creating_lower_role_side_effect(self):
        for index,key in enumerate(['is_superuser','is_staff','groups','user_permissions']):
            with self.subTest(key=key):
                before=ProjectInvitation.objects.count()
                response=self.client.post(reverse('governance_invite'),
                    {'email':f'flag-{index}@example.test','role':Profile.Roles.ENGINEER,
                     'project':self.pa.pk,key:'1'})
                self.assertEqual(response.status_code,400)
                self.assertEqual(ProjectInvitation.objects.count(),before)

    def test_customer_invitation_rejects_foreign_company_override(self):
        before=ProjectInvitation.objects.count()
        response=self.client.post(reverse('governance_invite'),
            {'email':'company-override@example.test','role':Profile.Roles.ENGINEER,
             'project':self.pa.pk,'company':self.b.pk})
        self.assertEqual(response.status_code,400)
        self.assertEqual(ProjectInvitation.objects.count(),before)

    def test_operational_invitation_ignores_posted_industry_without_changing_authority(self):
        other=IndustryCatalog.objects.get(code='construction')
        response=self.client.post(reverse('governance_invite'),{'email':'ignored-industry@example.test',
            'role':Profile.Roles.ENGINEER,'project':self.pa.pk,'admin_industry':other.pk})
        self.assertEqual(response.status_code,200)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.profile.admin_industry_id,self.industry.pk)
        invite=ProjectInvitation.objects.get(email='ignored-industry@example.test')
        self.assertEqual(invite.company_id,self.a.pk)
        self.assertEqual(invite.project_id,self.pa.pk)
        self.assertIsNone(invite.admin_industry_id)
        after=GovernanceAudit.objects.get(action='invitation_created').details['privileged_change']['after']
        self.assertEqual(after['role'],Profile.Roles.ENGINEER)
        self.assertIsNone(after['admin_industry_id'])

    def test_membership_route_cannot_smuggle_account_or_tenant_authority(self):
        for key,value in [('role',Profile.Roles.ADMIN),('is_superuser','1'),('is_staff','1'),
                          ('company',self.b.pk),('admin_industry',self.industry.pk)]:
            with self.subTest(key=key):
                ProjectMembership.objects.filter(user=self.engineer,project=self.pa).delete()
                before=GovernanceAudit.objects.count()
                response=self.client.post(reverse('governance_membership',args=[self.engineer.pk]),
                    {'project':self.pa.pk,'action':'grant',key:value})
                self.assertEqual(response.status_code,400)
                self.assertFalse(ProjectMembership.objects.filter(user=self.engineer,project=self.pa).exists())
                self.engineer.refresh_from_db()
                self.assertEqual(self.engineer.profile.role,Profile.Roles.ENGINEER)
                self.assertEqual(self.engineer.profile.company_id,self.a.pk)
                self.assertEqual(GovernanceAudit.objects.count(),before)

    def invitation(self,token='synthetic-platform-separation-token'):
        row=ProjectInvitation.objects.create(email='new-role@example.test',role=Profile.Roles.ENGINEER,
            project=self.pa,company=self.a,created_by=self.admin,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),expires_at=timezone.now()+timedelta(hours=1))
        return row,token

    def test_invitation_acceptance_rejects_posted_authority_and_keeps_token_unconsumed(self):
        row,token=self.invitation()
        anonymous=Client()
        for key,value in [('role',Profile.Roles.ADMIN),('is_superuser','1'),('is_staff','1'),
                          ('company',self.b.pk),('project',self.pb.pk),('admin_industry',self.industry.pk)]:
            with self.subTest(key=key):
                response=anonymous.post(reverse('governance_accept_invite',args=[token]),
                    {'username':'new_role_user','email':row.email,'password1':'Invitation-fixture-457!',
                     'password2':'Invitation-fixture-457!',key:value})
                self.assertEqual(response.status_code,400)
                self.assertFalse(User.objects.filter(username='new_role_user').exists())
                row.refresh_from_db()
                self.assertIsNone(row.accepted_at)
                self.assertIsNone(row.accepted_by_id)

    def test_roles_reject_platform_actions_without_privilege_or_scope_changes(self):
        paths=[reverse('governance_industry'),reverse('governance_project_admin',args=[self.pa.pk]),
               reverse('governance_project_company',args=[self.pa.pk]),
               reverse('governance_admin_industry',args=[self.foreign_admin.pk]),reverse('governance_reset')]
        for actor in [self.admin,self.engineer,self.lead,self.qa,self.customer]:
            browser=Client();browser.force_login(actor)
            for path in paths:
                with self.subTest(actor=actor.pk,path=path):
                    count=GovernanceAudit.objects.count()
                    self.assertEqual(browser.post(path,{'role':Profile.Roles.SUPER_ADMIN,'is_superuser':'1'}).status_code,403)
                    actor.refresh_from_db()
                    self.assertFalse(actor.is_superuser or actor.is_staff)
                    self.assertEqual(GovernanceAudit.objects.count(),count)

    def test_customer_admin_cannot_promote_self_peer_admin_or_staff_to_global_admin(self):
        for target in [self.admin,self.foreign_admin,self.engineer]:
            for role in [Profile.Roles.ADMIN,Profile.Roles.SUPER_ADMIN]:
                with self.subTest(target=target.pk,role=role):
                    before=target.profile.role
                    response=self.client.post(reverse('governance_member',args=[target.pk]),{'action':'role','role':role})
                    self.assertEqual(response.status_code,403)
                    target.refresh_from_db();self.assertEqual(target.profile.role,before)
                    self.assertFalse(target.is_superuser)

    def test_platform_preserves_supported_nonclient_account_administration(self):
        self.client.force_login(self.owner)
        response=self.client.post(reverse('governance_invite'),{'email':'owner-engineer@example.test',
            'role':Profile.Roles.ENGINEER,'project':self.pa.pk})
        self.assertEqual(response.status_code,200)
        self.assertTrue(ProjectInvitation.objects.filter(email='owner-engineer@example.test',role=Profile.Roles.ENGINEER).exists())
        self.assertEqual(self.client.post(reverse('governance_invite'),{'email':'owner-client@example.test',
            'role':Profile.Roles.CLIENT,'project':self.pa.pk}).status_code,400)
        self.assertEqual(self.client.post(reverse('governance_projects'),{'name':'Forbidden platform project'}).status_code,403)

    def test_successful_role_change_has_current_actor_scope_and_before_after_audit(self):
        response=self.client.post(reverse('governance_member',args=[self.engineer.pk]),
            {'action':'role','role':Profile.Roles.TEAM_LEAD})
        self.assertEqual(response.status_code,302)
        event=GovernanceAudit.objects.get(action='member_role')
        change=event.details['privileged_change']
        self.assertEqual(event.actor_id,self.admin.pk)
        self.assertEqual(change['actor']['role'],Profile.Roles.ADMIN)
        self.assertEqual(change['target'],{'kind':'user','id':self.engineer.pk})
        self.assertEqual(change['scope'],{'company_id':self.a.pk,'project_id':self.pa.pk})
        self.assertEqual(change['before']['role'],Profile.Roles.ENGINEER)
        self.assertEqual(change['after']['role'],Profile.Roles.TEAM_LEAD)
        self.assertFalse(change['before']['is_superuser'] or change['after']['is_superuser'])
        serialized=json.dumps(event.details)
        self.assertNotIn(self.engineer.password,serialized)
        self.assertNotIn('Fixture-admin-849!',serialized)

    def test_failed_audit_rolls_back_the_privileged_change(self):
        with patch('core.governance_views.audit',side_effect=IntegrityError('synthetic audit failure')):
            response=self.client.post(reverse('governance_member',args=[self.engineer.pk]),
                {'action':'role','role':Profile.Roles.TEAM_LEAD})
        self.assertEqual(response.status_code,409)
        self.engineer.refresh_from_db()
        self.assertEqual(self.engineer.profile.role,Profile.Roles.ENGINEER)
        self.assertFalse(GovernanceAudit.objects.filter(action='member_role').exists())

    def test_membership_grant_and_revoke_audit_include_effective_primary_history(self):
        url=reverse('governance_membership',args=[self.engineer.pk])
        self.assertEqual(self.client.post(url,{'project':self.pa.pk,'action':'grant','make_primary':'on'}).status_code,302)
        change=GovernanceAudit.objects.get(action='project_membership_grant').details['privileged_change']
        self.assertFalse(change['before']['exists'])
        self.assertEqual(change['before']['primary_project_id'],self.pa.pk)
        self.assertTrue(change['after']['is_active'])
        self.assertEqual(self.client.post(url,{'project':self.pa.pk,'action':'revoke'}).status_code,302)
        change=GovernanceAudit.objects.get(action='project_membership_revoke').details['privileged_change']
        self.assertTrue(change['before']['is_active'])
        self.assertFalse(change['after']['is_active'])
        self.assertIsNone(change['after']['primary_project_id'])

    def test_accept_admin_invitation_audits_owner_before_automatic_membership_assignment(self):
        project=Project.objects.create(name='Synthetic unowned administrative project',company=self.a)
        token='synthetic-platform-admin-acceptance-token'
        invitation=ProjectInvitation.objects.create(email='accepted-admin@example.test',role=Profile.Roles.ADMIN,
            project=project,company=self.a,admin_industry=self.industry,created_by=self.owner,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),expires_at=timezone.now()+timedelta(hours=1))
        browser=Client()
        response=browser.post(reverse('governance_accept_invite',args=[token]),{'username':'accepted_admin','email':invitation.email,
            'password1':'Invitation-fixture-457!','password2':'Invitation-fixture-457!'})
        self.assertEqual(response.status_code,302)
        accepted=User.objects.get(username='accepted_admin')
        change=GovernanceAudit.objects.get(action='project_administrator_assigned').details['privileged_change']
        self.assertIsNone(change['before']['administrator_id'])
        self.assertEqual(change['after']['administrator_id'],accepted.pk)
        created=GovernanceAudit.objects.get(action='invitation_accepted').details['privileged_change']
        self.assertIsNone(created['before'])
        self.assertEqual(created['after']['role'],Profile.Roles.ADMIN)
        self.assertEqual(created['actor']['id'],accepted.pk)

    def test_regular_profile_cannot_claim_platform_authority_without_superuser_flag(self):
        Profile.objects.filter(user=self.engineer).update(role=Profile.Roles.SUPER_ADMIN)
        self.engineer.refresh_from_db()
        self.assertIsNone(role_for(self.engineer))
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.post(reverse('governance_industry'),{'code':'bad','name':'Bad'}).status_code,403)
