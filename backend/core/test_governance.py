"""Independent governance regression tests; synthetic users/projects only."""
import hashlib
from datetime import timedelta
from urllib.parse import urlsplit
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import Checklist, ChecklistTemplate, Profile, Project, WorkAssignment, ProjectInvitation, GovernanceAudit, IndustryCatalog


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False, LOCAL_AI_ENABLED=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GovernanceTests(TestCase):
    def setUp(self):
        self.schema={'title':'Governance fixture','sections':[{'id':'general','title':'General','fields':[{'id':'condition','label':'Condition','type':'text'}]}]}
        self.template=ChecklistTemplate.objects.create(name='Governance fixture',published=True,definition=self.schema)
        self.project=Project.objects.create(name='Project A',checklist_template=self.template)
        self.other=Project.objects.create(name='Project B',checklist_template=self.template)
        self.super=self.person('super',Profile.Roles.SUPER_ADMIN,superuser=True)
        self.admin=self.person('admin',Profile.Roles.ADMIN,self.project)
        self.lead=self.person('lead',Profile.Roles.TEAM_LEAD,self.project)
        self.engineer=self.person('engineer',Profile.Roles.ENGINEER,self.project)
        self.quality=self.person('quality',Profile.Roles.QUALITY_ENGINEER,self.project)
        self.other_admin=self.person('other_admin',Profile.Roles.ADMIN,self.other)
        self.other_engineer=self.person('other_engineer',Profile.Roles.ENGINEER,self.other)
        self.survey=Checklist.objects.create(user=self.engineer,project=self.project,site_id='SYNTHETIC-GOV')
        self.client.force_login(self.super)

    def person(self,name,role,project=None,superuser=False):
        user=User.objects.create_user(name,email=name+'@example.test',password='Fixture-secure-849!')
        user.is_superuser=superuser
        user.is_staff=superuser
        user.save()
        user.profile.role=role
        user.profile.project=project
        user.profile.save()
        return user

    def login(self,user):
        self.client.force_login(user)

    def invite(self,email='new@example.test',role=None,project=None):
        return self.client.post(reverse('governance_invite'),{'email':email,'role':role or Profile.Roles.ENGINEER,'project':(project or self.project).pk,**({'admin_industry':IndustryCatalog.objects.get(code=(project or self.project).industry).pk} if role==Profile.Roles.ADMIN else {})})

    def token(self):
        row=ProjectInvitation.objects.create(email='new@example.test',role=Profile.Roles.ENGINEER,project=self.project,created_by=self.admin,token_hash=hashlib.sha256(b'synthetic-invite-token').hexdigest(),expires_at=timezone.now()+timedelta(hours=1))
        return row,'synthetic-invite-token'

    def accept_data(self,**kwargs):
        data={'username':'invited','email':'new@example.test','password1':'Invitation-fixture-457!','password2':'Invitation-fixture-457!'}
        data.update(kwargs)
        return data

    def test_invite_privileges_email_scope_and_no_escalation(self):
        for user in [self.engineer,self.lead]:
            self.login(user)
            self.assertEqual(self.invite().status_code,403)
        self.login(self.admin)
        for role in [Profile.Roles.ADMIN,Profile.Roles.SUPER_ADMIN]:
            self.assertIn(self.invite(role=role).status_code,(400,403))
        self.assertIn(self.invite(project=self.other).status_code,(400,403,404))
        self.assertEqual(ProjectInvitation.objects.count(),0)
        response=self.invite()
        self.assertEqual(response.status_code,200)
        row=ProjectInvitation.objects.get()
        self.assertEqual(row.project,self.project)
        self.assertEqual(row.role,Profile.Roles.ENGINEER)
        self.assertEqual(len(row.token_hash),64)
        raw=urlsplit(response.context['invite_url']).path.rstrip('/').split('/')[-1]
        self.assertNotEqual(row.token_hash,raw)
        self.assertEqual(row.token_hash,hashlib.sha256(raw.encode()).hexdigest())
        self.assertFalse(User.objects.filter(email='new@example.test').exists())
        self.assertTrue(GovernanceAudit.objects.exists())

    def test_invite_email_bound_single_use_and_expired(self):
        row,token=self.token()
        url=reverse('governance_accept_invite',args=[token])
        response=Client().post(url,self.accept_data(email='different@example.test'))
        self.assertNotEqual(response.status_code,302)
        self.assertFalse(User.objects.filter(username='invited').exists())
        response=Client().post(url,self.accept_data())
        self.assertEqual(response.status_code,302)
        user=User.objects.get(username='invited')
        self.assertFalse(user.is_superuser or user.is_staff)
        self.assertEqual(user.profile.project,self.project)
        self.assertEqual(user.profile.role,Profile.Roles.ENGINEER)
        row.refresh_from_db()
        self.assertEqual(row.accepted_by,user)
        self.assertNotEqual(Client().post(url,self.accept_data(username='reused')).status_code,302)
        self.assertFalse(User.objects.filter(username='reused').exists())
        row.accepted_by=None
        row.accepted_at=None
        row.expires_at=timezone.now()-timedelta(seconds=1)
        row.save()
        self.assertNotEqual(Client().post(url,self.accept_data(username='expired')).status_code,302)
        self.assertFalse(User.objects.filter(username='expired').exists())

    def test_public_invite_accept_requires_csrf_and_get_has_no_mutation(self):
        row,token=self.token()
        url=reverse('governance_accept_invite',args=[token])
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.get(url).status_code,200)
        self.assertEqual(User.objects.count(),7)
        self.assertEqual(client.post(url,self.accept_data()).status_code,403)
        row.refresh_from_db()
        self.assertIsNone(row.accepted_at)

    def test_governance_writes_require_authentication_and_csrf(self):
        paths=[reverse('governance_projects'),reverse('governance_invite'),reverse('governance_assign'),reverse('governance_client_approval',args=[self.survey.pk]),reverse('governance_reset'),reverse('governance_member',args=[self.engineer.pk]),reverse('governance_revoke_invite',args=[0])]
        for path in paths:
            self.assertIn(Client().post(path).status_code,(302,401,403,404))
        strict=Client(enforce_csrf_checks=True)
        strict.force_login(self.super)
        for path in paths:
            self.assertEqual(strict.post(path).status_code,403)

    def test_only_bound_admin_creates_projects_and_super_invites_project_admin(self):
        for user in [self.super,self.lead,self.engineer]:
            self.login(user)
            self.assertEqual(self.client.post(reverse('governance_projects'),{'name':'Forbidden','review_layers':3}).status_code,403)
        from .models import Company
        company=Company.objects.create(name='Scoped project creation tenant')
        self.admin.profile.company=company
        self.admin.profile.admin_industry=IndustryCatalog.objects.get(code='telecom')
        self.admin.profile.save()
        self.login(self.admin)
        self.assertEqual(self.client.post(reverse('governance_projects'),{'name':'New synthetic','review_layers':3}).status_code,302)
        self.assertTrue(Project.objects.filter(name='New synthetic',company=company,administrator=self.admin).exists())
        self.login(self.super)
        self.assertEqual(self.client.post(reverse('governance_invite'),{'email':'new@example.test',
            'role':Profile.Roles.ADMIN,'company':company.pk,'admin_industry':IndustryCatalog.objects.get(code='telecom').pk}).status_code,200)
        self.assertEqual(ProjectInvitation.objects.get().role,Profile.Roles.ADMIN)
        self.assertNotEqual(self.invite(email='escalate@example.test',role=Profile.Roles.SUPER_ADMIN).status_code,200)

    def test_assignment_scope_and_review_task_creation(self):
        payload={'project':self.project.pk,'engineer':self.engineer.pk,'quality_reviewer':self.quality.pk,'site_id':'ASSIGNED-001','latitude':'24.1','longitude':'46.2','description':'Synthetic assignment'}
        self.login(self.engineer)
        self.assertEqual(self.client.post(reverse('governance_assign'),payload).status_code,403)
        self.login(self.lead)
        self.assertEqual(self.client.post(reverse('governance_assign'),payload).status_code,302)
        assignment=WorkAssignment.objects.get(site_id='ASSIGNED-001')
        self.assertEqual(assignment.assigned_to,self.engineer)
        self.assertIsNotNone(assignment.checklist)
        before=WorkAssignment.objects.count()
        payload['engineer']=self.other_engineer.pk
        self.assertIn(self.client.post(reverse('governance_assign'),payload).status_code,(400,403,404))
        self.assertEqual(WorkAssignment.objects.count(),before)

    def test_client_decision_separate_authorized_and_stale_guarded(self):
        url=reverse('governance_client_approval',args=[self.survey.pk])
        payload={'decision':'approved','approver_name':'External Reviewer','approver_email':'client@example.test','reference':'Synthetic signed approval','expected_updated_at':self.survey.updated_at.isoformat(),'expected_review_token':self.survey.client_review_token}
        self.login(self.admin)
        self.assertIn(self.client.post(url,payload).status_code,(400,409))
        self.survey.status=Checklist.Status.FINAL
        self.survey.section_approvals={'general':{'by':'lead'}}
        self.survey.save()
        payload['expected_updated_at']=self.survey.updated_at.isoformat()
        payload['expected_review_token']=self.survey.client_review_token
        for user in [self.engineer,self.lead,self.other_admin]:
            self.login(user)
            self.assertIn(self.client.post(url,payload).status_code,(403,404))
        self.login(self.admin)
        stale=dict(payload)
        self.survey.comment='Changed since administrator loaded page'
        self.survey.save()
        self.assertEqual(self.client.post(url,stale).status_code,409)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.client_approval,{})
        payload['expected_updated_at']=self.survey.updated_at.isoformat()
        payload['expected_review_token']=self.survey.client_review_token
        self.assertEqual(self.client.post(url,payload).status_code,302)
        self.survey.refresh_from_db()
        self.assertTrue(self.survey.client_approval)
        self.assertIn('client@example.test',str(self.survey.client_approval))
        self.assertEqual(self.survey.status,Checklist.Status.FINAL)
        self.assertEqual(self.survey.section_approvals,{'general':{'by':'lead'}})
        self.assertTrue(GovernanceAudit.objects.filter(project=self.project).exists())

    def test_project_admin_not_global_admin_and_audit_is_scoped(self):
        self.login(self.admin)
        foreign_template=ChecklistTemplate.objects.create(name='PRIVATE-FOREIGN-TEMPLATE',definition=self.schema)
        response=self.client.get(reverse('checklist_templates'))
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'PRIVATE-FOREIGN-TEMPLATE')
        self.assertEqual(self.client.get(reverse('checklist_template_edit',args=[foreign_template.pk])).status_code,404)
        other_survey=Checklist.objects.create(user=self.other_engineer,project=self.other,site_id='PRIVATE-OTHER')
        self.assertEqual(self.client.get(reverse('custom_checklist',args=[other_survey.pk])).status_code,404)
        GovernanceAudit.objects.create(action='synthetic_a',actor=self.super,project=self.project,details={'marker':'PUBLIC-OWN'})
        GovernanceAudit.objects.create(action='synthetic_b',actor=self.super,project=self.other,details={'marker':'PRIVATE-OTHER-AUDIT'})
        response=self.client.get(reverse('governance_audit'))
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'PRIVATE-OTHER-AUDIT')
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_superuser)

    def test_maintenance_reset_reauthenticates_and_preserves_survey_data(self):
        row,token=self.token()
        self.survey.answer_data={'custom':{'condition':'Preserve this engineer record'}}
        self.survey.save()
        self.engineer.profile.failed_attempts=5
        self.engineer.profile.is_locked=True
        self.engineer.profile.save()
        url=reverse('governance_reset')
        self.login(self.admin)
        self.assertEqual(self.client.post(url,{'typed_confirmation':'RESET ACCESS','password':'Fixture-secure-849!'}).status_code,403)
        self.login(self.super)
        self.assertNotEqual(self.client.post(url,{'typed_confirmation':'RESET ACCESS','password':'wrong'}).status_code,302)
        self.engineer.profile.refresh_from_db()
        self.assertTrue(self.engineer.profile.is_locked)
        response=self.client.post(url,{'typed_confirmation':'RESET ACCESS','password':'Fixture-secure-849!'})
        self.assertEqual(response.status_code,302)
        self.survey.refresh_from_db()
        self.engineer.profile.refresh_from_db()
        row.refresh_from_db()
        self.assertEqual(self.survey.answer_data,{'custom':{'condition':'Preserve this engineer record'}})
        self.assertEqual(Project.objects.count(),2)
        self.assertEqual(User.objects.count(),7)
        self.assertFalse(self.engineer.profile.is_locked)
        self.assertEqual(self.engineer.profile.failed_attempts,0)
        self.assertIsNotNone(row.revoked_at)
        self.assertEqual(Session.objects.count(),0)
        self.assertTrue(GovernanceAudit.objects.exists())

    def test_login_cannot_promote_project_admin_or_trust_legacy_role_session(self):
        client=Client()
        response=client.post(reverse('login'),{'username':self.admin.username,'password':'Fixture-secure-849!','role':'SUPER_ADMIN'})
        self.assertEqual(response.status_code,302)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_superuser or self.admin.is_staff)
        self.assertEqual(self.admin.profile.role,Profile.Roles.ADMIN)
        session=client.session
        session['is_dev_admin']=True
        session.save()
        self.assertEqual(client.get(reverse('checklist_templates')).status_code,200)
        foreign_template=ChecklistTemplate.objects.create(name='Other admin private',definition=self.schema,created_by=self.other_admin)
        self.assertEqual(client.get(reverse('checklist_template_edit',args=[foreign_template.pk])).status_code,404)
        self.engineer.profile.is_locked=True
        self.engineer.profile.save()
        blocked=Client()
        self.assertEqual(blocked.post(reverse('login'),{'username':self.engineer.username,'password':'Fixture-secure-849!'}).status_code,200)
        self.assertNotIn('_auth_user_id',blocked.session)

    def test_invitation_issuer_revocation_and_case_insensitive_email_duplicates(self):
        row,token=self.token()
        url=reverse('governance_accept_invite',args=[token])
        self.admin.profile.role=Profile.Roles.ENGINEER
        self.admin.profile.save()
        self.assertEqual(Client().post(url,self.accept_data()).status_code,404)
        self.admin.profile.role=Profile.Roles.ADMIN
        self.admin.profile.save()
        self.admin.is_active=False
        self.admin.save()
        self.assertEqual(Client().get(url).status_code,404)
        self.assertFalse(User.objects.filter(username='invited').exists())
        self.admin.is_active=True
        self.admin.save()
        self.login(self.admin)
        before=ProjectInvitation.objects.count()
        self.assertEqual(self.invite(email='ENGINEER@EXAMPLE.TEST').status_code,400)
        self.assertEqual(ProjectInvitation.objects.count(),before)

    def test_member_and_invitation_controls_cannot_cross_scope_or_escalate(self):
        row,token=self.token()
        other=ProjectInvitation.objects.create(email='outside@example.test',role=Profile.Roles.ENGINEER,project=self.other,created_by=self.other_admin,token_hash=hashlib.sha256(b'outside-token-long-enough').hexdigest(),expires_at=timezone.now()+timedelta(hours=1))
        self.login(self.admin)
        for target in [self.super,self.other_engineer,self.other_admin,self.admin]:
            self.assertIn(self.client.post(reverse('governance_member',args=[target.pk]),{'action':'deactivate'}).status_code,(403,404))
        self.assertEqual(self.client.post(reverse('governance_member',args=[self.engineer.pk]),{'action':'role','role':'SUPER_ADMIN'}).status_code,403)
        self.assertIn(self.client.post(reverse('governance_revoke_invite',args=[other.pk])).status_code,(403,404))
        self.assertEqual(self.client.post(reverse('governance_revoke_invite',args=[row.pk])).status_code,302)
        self.assertEqual(Client().get(reverse('governance_accept_invite',args=[token])).status_code,404)
        self.engineer.profile.is_locked=True
        self.engineer.profile.failed_attempts=5
        self.engineer.profile.save()
        self.assertEqual(self.client.post(reverse('governance_member',args=[self.engineer.pk]),{'action':'unlock'}).status_code,302)
        self.engineer.profile.refresh_from_db()
        self.assertFalse(self.engineer.profile.is_locked)
        self.assertEqual(self.engineer.profile.failed_attempts,0)

    def test_forged_super_profile_never_grants_global_permission(self):
        self.admin.profile.role=Profile.Roles.SUPER_ADMIN
        self.admin.profile.save()
        self.login(self.admin)
        self.assertEqual(self.client.post(reverse('governance_projects'),{'name':'Forged global project'}).status_code,403)
        self.assertFalse(Project.objects.filter(name='Forged global project').exists())

    def test_client_approval_rejects_changed_answers_even_unchanged_timestamp(self):
        self.survey.status=Checklist.Status.FINAL
        self.survey.save()
        payload={'decision':'approved','approver_name':'External Reviewer','approver_email':'client@example.test','reference':'Synthetic','expected_updated_at':self.survey.updated_at.isoformat(),'expected_review_token':self.survey.client_review_token}
        Checklist.objects.filter(pk=self.survey.pk).update(answer_data={'custom':{'condition':'Changed directly'}})
        self.login(self.admin)
        self.assertEqual(self.client.post(reverse('governance_client_approval',args=[self.survey.pk]),payload).status_code,409)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.client_approval,{})

class InvitationLoggingTests(SimpleTestCase):
    def test_bearer_invitation_redacted_from_formatted_log_records(self):
        import logging
        from .governance_logging import RedactInvitations
        token='synthetic-secret-invitation-credential'
        record=logging.LogRecord('django.server',logging.INFO,__file__,0,'GET %s 200',('/governance/invite/'+token+'/',),None)
        self.assertTrue(RedactInvitations().filter(record))
        self.assertNotIn(token,record.getMessage())
        self.assertIn('/governance/invite/[redacted]/',record.getMessage())
        self.assertEqual(record.args,())

@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class InvitationConcurrencyTests(TransactionTestCase):
    def test_concurrent_consumers_create_at_most_one_account(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections
        from .models import GovernanceState
        project=Project.objects.create(name='Race fixture')
        issuer=User.objects.create_user('race_issuer')
        issuer.profile.role=Profile.Roles.ADMIN
        issuer.profile.project=project
        issuer.profile.save()
        raw='synthetic-race-token-long-enough'
        invitation=ProjectInvitation.objects.create(email='race@example.test',role=Profile.Roles.ENGINEER,project=project,created_by=issuer,token_hash=hashlib.sha256(raw.encode()).hexdigest(),expires_at=timezone.now()+timedelta(hours=1))
        GovernanceState.objects.create(key='membership')
        barrier=threading.Barrier(2)
        def consume(index):
            close_old_connections()
            try:
                client=Client(raise_request_exception=False)
                barrier.wait(timeout=10)
                response=client.post(reverse('governance_accept_invite',args=[raw]),{'username':f'race_member_{index}','email':'race@example.test','password1':'Concurrent-fixture-824!','password2':'Concurrent-fixture-824!'})
                return response.status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(consume,[1,2]))
        self.assertTrue(all(status in (302,404,409,503) for status in statuses),statuses)
        self.assertLessEqual(statuses.count(302),1,statuses)
        self.assertLessEqual(User.objects.filter(email='race@example.test').count(),1)
        if 302 not in statuses:
            response=Client().post(reverse('governance_accept_invite',args=[raw]),{'username':'race_retry','email':'race@example.test','password1':'Concurrent-fixture-824!','password2':'Concurrent-fixture-824!'})
            self.assertEqual(response.status_code,302)
            statuses.append(302)
        self.assertEqual(User.objects.filter(email='race@example.test').count(),1)
        if 302 in statuses:
            invitation.refresh_from_db()
            self.assertIsNotNone(invitation.accepted_at)
            self.assertIsNotNone(invitation.accepted_by)
