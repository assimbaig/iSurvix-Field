"""Independent role-plane and privileged-audit contracts on disposable accounts."""
import hashlib
import json
from urllib.parse import urlsplit
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (Checklist, ChecklistTemplate, Company, GovernanceAudit,
                     IndustryCatalog, Profile, Project, ProjectInvitation,
                     ProjectMembership)


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False, LOCAL_AI_ENABLED=True,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentPlatformCustomerTests(TestCase):
    def setUp(self):
        self.industry=IndustryCatalog.objects.get(code='telecom')
        self.other_industry=IndustryCatalog.objects.get(code='construction')
        self.company=Company.objects.create(name='Independent Company A')
        self.foreign_company=Company.objects.create(name='Independent Company B')
        schema={'title':'Independent role fixture','sections':[{'id':'general','title':'General',
                'fields':[{'id':'condition','label':'Condition','type':'text'}]}]}
        self.template=ChecklistTemplate.objects.create(name='Independent role fixture',
                                                       definition=schema,published=True)
        self.project=Project.objects.create(name='Independent Project A',company=self.company,
                                             checklist_template=self.template)
        self.foreign_project=Project.objects.create(name='Independent Project B',
                         company=self.foreign_company,checklist_template=self.template)
        self.owner=self.person('independent_owner',Profile.Roles.SUPER_ADMIN,superuser=True)
        self.admin=self.person('independent_admin',Profile.Roles.ADMIN,self.project)
        self.engineer=self.person('independent_engineer',Profile.Roles.ENGINEER,self.project)
        self.qa=self.person('independent_quality',Profile.Roles.QUALITY_ENGINEER,self.project)
        self.lead=self.person('independent_lead',Profile.Roles.TEAM_LEAD,self.project)
        self.customer=self.person('independent_client',Profile.Roles.CLIENT,self.project)
        self.foreign_admin=self.person('independent_foreign_admin',Profile.Roles.ADMIN,self.foreign_project)
        self.foreign_engineer=self.person('independent_foreign_engineer',Profile.Roles.ENGINEER,self.foreign_project)
        self.survey=Checklist.objects.create(user=self.engineer,project=self.project,
                     site_id='INDEPENDENT-ROLE-A',quality_reviewer=self.qa,
                     answer_data={'custom':{'condition':'Preserve answer'}})

    def person(self,name,role,project=None,superuser=False,company=None):
        user=User.objects.create_user(name,email=name+'@example.test',password='Independent-fixture-842!')
        User.objects.filter(pk=user.pk).update(is_superuser=superuser,is_staff=superuser)
        profile=user.profile
        profile.role=role;profile.project=project
        profile.company=project.company if project else company
        if role==Profile.Roles.ADMIN:profile.admin_industry=self.industry
        profile.save();user.refresh_from_db()
        return user

    def browser(self,actor=None):
        browser=Client(enforce_csrf_checks=True)
        self.assertEqual(browser.get('/login/').status_code,200)
        if actor:browser.force_login(actor)
        return browser

    def post(self,actor,name,data=None,args=None,browser=None):
        browser=browser or self.browser(actor)
        token=browser.cookies[settings.CSRF_COOKIE_NAME].value
        return browser.post(reverse(name,args=args),data or {},HTTP_X_CSRFTOKEN=token)

    def principal(self,user):
        user.refresh_from_db();profile=user.profile
        return {'is_superuser':user.is_superuser,'is_staff':user.is_staff,'is_active':user.is_active,
                'role':profile.role,'company_id':profile.company_id,'project_id':profile.project_id,
                'admin_industry_id':profile.admin_industry_id,'is_locked':profile.is_locked}

    def test_customer_admin_cannot_enter_platform_mutation_plane(self):
        before=self.principal(self.foreign_admin)
        cases=[('governance_project_admin',[self.project.pk],{'administrator':self.admin.pk}),
               ('governance_admin_industry',[self.admin.pk],{'admin_industry':self.other_industry.pk}),
               ('governance_project_company',[self.project.pk],{'company':self.foreign_company.pk}),
               ('governance_industry',None,{'name':'Forbidden industry','code':'forbidden','workflow_family':'other'}),
               ('governance_reset',None,{'confirmation':'RESET ACCESS','password':'synthetic-not-relevant'})]
        for route,args,data in cases:
            with self.subTest(route=route):
                self.assertEqual(self.post(self.admin,route,data,args).status_code,403)
        self.assertEqual(self.principal(self.foreign_admin),before)
        self.project.refresh_from_db();self.assertEqual(self.project.company_id,self.company.pk)
        self.assertFalse(IndustryCatalog.objects.filter(code='forbidden').exists())

    def test_operational_roles_cannot_grant_account_authority(self):
        before=self.principal(self.engineer)
        for actor in [self.engineer,self.qa,self.lead,self.customer]:
            for route,args,data in [
                ('governance_member',[self.engineer.pk],{'action':'role','role':Profile.Roles.TEAM_LEAD}),
                ('governance_membership',[self.engineer.pk],{'action':'grant','project':self.project.pk}),
                ('governance_invite',None,{'email':'must-not-exist@example.test','role':Profile.Roles.ENGINEER,'project':self.project.pk})]:
                with self.subTest(role=actor.profile.role,route=route):
                    self.assertEqual(self.post(actor,route,data,args).status_code,403)
        self.assertEqual(self.principal(self.engineer),before)
        self.assertFalse(ProjectInvitation.objects.filter(email='must-not-exist@example.test').exists())

    def test_admin_cannot_promote_self_other_admin_or_any_platform_role(self):
        for target in [self.admin,self.foreign_admin,self.owner]:
            before=self.principal(target)
            self.assertIn(self.post(self.admin,'governance_member',
                {'action':'deactivate'},[target.pk]).status_code,(403,404))
            self.assertEqual(self.principal(target),before)
        for role in [Profile.Roles.ADMIN,Profile.Roles.SUPER_ADMIN]:
            before=self.principal(self.engineer)
            self.assertIn(self.post(self.admin,'governance_member',
                {'action':'role','role':role},[self.engineer.pk]).status_code,(400,403))
            self.assertEqual(self.principal(self.engineer),before)
            self.assertIn(self.post(self.admin,'governance_invite',
                {'email':'escalation@example.test','role':role,'project':self.project.pk}).status_code,(400,403))
        self.assertFalse(ProjectInvitation.objects.filter(email='escalation@example.test').exists())

    def test_protected_post_flags_reject_entire_otherwise_valid_role_change(self):
        for key,value in [('is_superuser','1'),('is_staff','1'),('groups','1'),('user_permissions','1')]:
            before=self.principal(self.engineer)
            response=self.post(self.admin,'governance_member',
                     {'action':'role','role':Profile.Roles.QUALITY_ENGINEER,key:value},[self.engineer.pk])
            with self.subTest(key=key):
                self.assertEqual(response.status_code,400)
                self.assertEqual(self.principal(self.engineer),before)

    def test_customer_admin_scope_fields_cannot_be_smuggled_into_invitation(self):
        for key,value in [('company',self.foreign_company.pk),('is_superuser','1')]:
            email='forged-'+key+'@example.test'
            response=self.post(self.admin,'governance_invite',{'email':email,
                      'role':Profile.Roles.ENGINEER,'project':self.project.pk,key:value})
            with self.subTest(key=key):
                self.assertEqual(response.status_code,400)
                self.assertFalse(ProjectInvitation.objects.filter(email=email).exists())
        response=self.post(self.admin,'governance_invite',{'email':'compatibility-industry@example.test',
                    'role':Profile.Roles.ENGINEER,'project':self.project.pk,
                    'admin_industry':self.other_industry.pk})
        self.assertEqual(response.status_code,200)
        invitation=ProjectInvitation.objects.get(email='compatibility-industry@example.test')
        self.assertEqual(invitation.project_id,self.project.pk)
        self.assertIsNone(invitation.admin_industry_id)
        self.assertEqual(self.principal(self.admin)['admin_industry_id'],self.industry.pk)

    def test_safe_customer_admin_role_change_has_immutable_privileged_audit(self):
        response=self.post(self.admin,'governance_member',
                           {'action':'role','role':Profile.Roles.QUALITY_ENGINEER},[self.engineer.pk])
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.principal(self.engineer)['role'],Profile.Roles.QUALITY_ENGINEER)
        event=GovernanceAudit.objects.get(action='member_role',details__user_id=self.engineer.pk)
        envelope=event.details.get('privileged_change')
        self.assertIsInstance(envelope,dict)
        self.assertEqual(envelope['version'],1)
        self.assertEqual(envelope['actor']['id'],self.admin.pk)
        self.assertEqual(envelope['actor']['role'],Profile.Roles.ADMIN)
        self.assertEqual(envelope['actor']['company_id'],self.company.pk)
        self.assertEqual(envelope['target'],{'kind':'user','id':self.engineer.pk})
        self.assertEqual(envelope['scope'],{'company_id':self.company.pk,'project_id':self.project.pk})
        self.assertEqual(envelope['before']['role'],Profile.Roles.ENGINEER)
        self.assertEqual(envelope['after']['role'],Profile.Roles.QUALITY_ENGINEER)
        frozen=deepcopy(envelope)
        User.objects.filter(pk=self.admin.pk).update(username='renamed-after-audit')
        Profile.objects.filter(user=self.admin).update(company=self.foreign_company)
        event.refresh_from_db();self.assertEqual(event.details['privileged_change'],frozen)

    def test_audit_persistence_failure_rolls_back_privilege_change(self):
        before=self.principal(self.engineer)
        with patch('core.governance_views.GovernanceAudit.objects.create',side_effect=IntegrityError('isolated audit failure')):
            result=self.post(self.admin,'governance_member',
                            {'action':'role','role':Profile.Roles.TEAM_LEAD},[self.engineer.pk])
        self.assertEqual(result.status_code,409)
        self.assertEqual(self.principal(self.engineer),before)
        self.assertFalse(GovernanceAudit.objects.filter(action='member_role').exists())

    def test_platform_admin_assignment_is_audited_without_global_flag_changes(self):
        target=self.person('independent_new_admin',Profile.Roles.ADMIN,company=self.company)
        before=self.principal(target)
        response=self.post(self.owner,'governance_project_admin',{'administrator':target.pk},[self.project.pk])
        self.assertEqual(response.status_code,302)
        self.project.refresh_from_db();self.assertEqual(self.project.administrator_id,target.pk)
        target.refresh_from_db();self.assertFalse(target.is_superuser or target.is_staff)
        event=GovernanceAudit.objects.get(action='project_administrator_assigned')
        envelope=event.details.get('privileged_change');self.assertIsInstance(envelope,dict)
        self.assertEqual(envelope['actor']['id'],self.owner.pk)
        self.assertEqual(envelope['actor']['role'],Profile.Roles.SUPER_ADMIN)
        self.assertEqual(envelope['scope']['company_id'],self.company.pk)
        self.assertEqual(event.details['previous_administrator_id'],self.admin.pk)
        self.assertEqual(event.details['administrator_id'],target.pk)
        self.assertEqual(self.principal(target)['role'],before['role'])

    def test_invitation_acceptance_cannot_set_authority_or_log_secret_material(self):
        raw='independent-acceptance-private-token-593'
        invitation=ProjectInvitation.objects.create(email='accepted@example.test',role=Profile.Roles.ENGINEER,
             project=self.project,company=self.company,created_by=self.admin,
             token_hash=hashlib.sha256(raw.encode()).hexdigest(),expires_at=timezone.now()+timedelta(hours=1))
        data={'username':'independent_accepted','email':invitation.email,
              'password1':'DoNotAudit-Password-593!','password2':'DoNotAudit-Password-593!',
              'is_superuser':'1','is_staff':'1','role':Profile.Roles.SUPER_ADMIN}
        browser=self.browser();token=browser.cookies[settings.CSRF_COOKIE_NAME].value
        response=browser.post(reverse('governance_accept_invite',args=[raw]),data,HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,400)
        self.assertFalse(User.objects.filter(username=data['username']).exists())
        for key in ['is_superuser','is_staff','role']:data.pop(key)
        response=browser.post(reverse('governance_accept_invite',args=[raw]),data,HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,302)
        accepted=User.objects.get(username=data['username'])
        self.assertEqual(accepted.profile.role,Profile.Roles.ENGINEER)
        self.assertFalse(accepted.is_superuser or accepted.is_staff)
        payload=json.dumps(list(GovernanceAudit.objects.values('action','actor_name','details')),default=str)
        self.assertNotIn(raw,payload);self.assertNotIn(data['password1'],payload)
        self.assertNotIn(invitation.token_hash,payload)

    def test_platform_owner_cannot_perform_engineering_or_customer_actions(self):
        before=deepcopy(self.survey.answer_data)
        for route,args,data in [('governance_client_approval',[self.survey.pk],{'decision':'approved'}),
                                ('governance_company',None,{'name':'Forbidden owner client'}),
                                ('governance_projects',None,{'name':'Forbidden owner project'})]:
            self.assertEqual(self.post(self.owner,route,data,args).status_code,403)
        for route in ['custom_checklist','photo_workspace']:
            self.assertIn(self.browser(self.owner).get(reverse(route,args=[self.survey.pk])).status_code,(403,404))
        self.survey.refresh_from_db();self.assertEqual(self.survey.answer_data,before)
        self.assertFalse(Project.objects.filter(name='Forbidden owner project').exists())

    def test_owner_admin_invitation_acceptance_retains_assignment_before_after(self):
        project=Project.objects.create(name='Independent unassigned owner project',company=self.company,
                                       checklist_template=self.template)
        response=self.post(self.owner,'governance_invite',{'email':'new-admin@example.test',
                         'role':Profile.Roles.ADMIN,'project':project.pk,
                         'admin_industry':self.industry.pk,'company':self.company.pk})
        self.assertEqual(response.status_code,200)
        path=urlsplit(response.context['invite_url']).path
        browser=self.browser();token=browser.cookies[settings.CSRF_COOKIE_NAME].value
        result=browser.post(path,{'username':'independent_invited_admin','email':'new-admin@example.test',
                 'password1':'Independent-admin-accept-935!','password2':'Independent-admin-accept-935!'},
                 HTTP_X_CSRFTOKEN=token)
        self.assertEqual(result.status_code,302)
        accepted=User.objects.get(username='independent_invited_admin')
        self.assertEqual(accepted.profile.role,Profile.Roles.ADMIN)
        self.assertFalse(accepted.is_superuser or accepted.is_staff)
        self.assertEqual(accepted.profile.company_id,self.company.pk)
        project.refresh_from_db();self.assertEqual(project.administrator_id,accepted.pk)
        event=GovernanceAudit.objects.get(action='project_administrator_assigned',project=project)
        envelope=event.details['privileged_change']
        self.assertEqual(envelope['before']['administrator_id'],None)
        self.assertEqual(envelope['after']['administrator_id'],accepted.pk)
        self.assertEqual(envelope['actor']['id'],self.owner.pk)
        self.assertEqual(envelope['scope'],{'company_id':self.company.pk,'project_id':project.pk})

    def test_audit_visibility_is_project_scoped_for_customer_admin(self):
        own=GovernanceAudit.objects.create(actor=self.admin,action='independent_own',project=self.project,
                                          details={'marker':'VISIBLE-OWN-AUDIT-815'})
        foreign=GovernanceAudit.objects.create(actor=self.foreign_admin,action='independent_foreign',
                  project=self.foreign_project,details={'marker':'PRIVATE-FOREIGN-AUDIT-815'})
        response=self.browser(self.admin).get(reverse('governance_audit'))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'VISIBLE-OWN-AUDIT-815')
        self.assertNotContains(response,'PRIVATE-FOREIGN-AUDIT-815')
        owner_response=self.browser(self.owner).get(reverse('governance_audit'))
        self.assertContains(owner_response,'PRIVATE-FOREIGN-AUDIT-815')

    def test_retired_session_flags_and_bootstrap_do_not_create_platform_owner(self):
        browser=self.browser(self.admin);session=browser.session;session['is_dev_admin']=True;session.save()
        before=User.objects.filter(is_superuser=True).count()
        self.assertEqual(self.post(self.admin,'governance_reset',{},browser=browser).status_code,403)
        for path in ['/admin/','/admin/auth/user/','/devadmin/']:
            self.assertIn(browser.get(path).status_code,(302,403,404,410))
            self.assertIn(browser.post(path,{'is_superuser':'1'},HTTP_X_CSRFTOKEN=browser.cookies[settings.CSRF_COOKIE_NAME].value).status_code,(403,404,410))
        response=browser.post('/local/setup/',{'username':'must_not_be_root',
                   'password1':'NoSetup-Password-815!','password2':'NoSetup-Password-815!'},
                   HTTP_X_CSRFTOKEN=browser.cookies[settings.CSRF_COOKIE_NAME].value)
        self.assertIn(response.status_code,(302,403,404))
        self.assertEqual(User.objects.filter(is_superuser=True).count(),before)
        self.assertFalse(User.objects.filter(username='must_not_be_root').exists())
