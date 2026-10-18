"""Independent activity routing tests, using synthetic records in the test database."""
import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from django.contrib.auth.models import User
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import Checklist, ChecklistTemplate, Profile, Project, WorkAssignment, ProjectInvitation, GovernanceAudit, Company, IndustryCatalog


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ReviewWorkflowTests(TestCase):
    def setUp(self):
        self.schema={'title':'Synthetic activity checklist','sections':[{'id':'general','title':'General','fields':[{'id':'condition','label':'Condition','type':'text','required':True}]},{'id':'power','title':'Power','fields':[{'id':'power_notes','label':'Power evidence','type':'text','required':True}]}]}
        self.template=ChecklistTemplate.objects.create(name='Activity fixture',definition=deepcopy(self.schema),published=True)
        self.project=Project.objects.create(name='Activity project',checklist_template=self.template)
        self.other=Project.objects.create(name='Other activity project',checklist_template=self.template)
        self.super=self.person('activity_super',Profile.Roles.SUPER_ADMIN,superuser=True)
        self.admin=self.person('activity_admin',Profile.Roles.ADMIN,self.project)
        self.lead=self.person('activity_lead',Profile.Roles.TEAM_LEAD,self.project)
        self.quality=self.person('activity_quality',Profile.Roles.QUALITY_ENGINEER,self.project)
        self.engineer=self.person('activity_engineer',Profile.Roles.ENGINEER,self.project)
        self.survey=Checklist.objects.create(user=self.engineer,project=self.project,site_id='SYNTHETIC-ACTIVITY',quality_reviewer=self.quality)
        self.task=WorkAssignment.objects.create(project=self.project,assigned_by=self.lead,assigned_to=self.engineer,site_id=self.survey.site_id,latitude=24,longitude=46,description='Synthetic lifecycle task',checklist=self.survey)
        self.client.force_login(self.engineer)

    def person(self,name,role,project=None,superuser=False):
        user=User.objects.create_user(name,email=name+'@example.test',password='Activity-fixture-841!')
        user.is_superuser=superuser
        user.save()
        user.profile.role=role
        user.profile.project=project
        user.profile.save()
        return user

    def submit(self):
        self.client.force_login(self.engineer)
        response=self.client.post(reverse('custom_checklist_save',args=[self.survey.pk]),json.dumps({'answers':{'condition':'Recorded visual evidence','power_notes':'Recorded power evidence'}}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.post(reverse('custom_checklist_submit',args=[self.survey.pk])).status_code,302)
        self.survey.refresh_from_db()
        self.task.refresh_from_db()
        self.assertEqual(self.survey.status,Checklist.Status.SUBMITTED)
        self.assertEqual(self.task.status,WorkAssignment.Status.SUBMITTED)
        self.assertIsNone(self.task.completed_at)

    def review(self,action='approve',sections=None):
        from .quality_workflow import review_quality,quality_is_current
        self.survey.refresh_from_db()
        if not quality_is_current(self.survey):
            review_quality(self.quality,self.survey,'approve','Synthetic Quality Control',self.survey.updated_at.isoformat())
            self.survey.refresh_from_db()
        self.client.force_login(self.lead)
        response=self.client.post(reverse('custom_checklist_review',args=[self.survey.pk]),{'action':action,'sections':sections or []})
        self.assertEqual(response.status_code,302)
        self.survey.refresh_from_db()
        self.task.refresh_from_db()
        return response

    def decision(self,actor,decision='approved',payload=None):
        self.survey.refresh_from_db()
        self.client.force_login(actor)
        data=payload or {'decision':decision,'reference':'Synthetic review','expected_updated_at':self.survey.updated_at.isoformat(),'expected_review_token':self.survey.client_review_token,'approver_name':'External Approver','approver_email':'external@example.test'}
        response=self.client.post(reverse('governance_client_approval',args=[self.survey.pk]),data)
        self.survey.refresh_from_db()
        self.task.refresh_from_db()
        return response

    def test_engineer_team_lead_and_configured_client_required_before_close(self):
        reviewer=self.person('activity_client',Profile.Roles.CLIENT,self.project)
        self.submit()
        self.review()
        self.assertEqual(self.survey.status,Checklist.Status.FINAL)
        self.assertTrue(self.survey.client_review_required)
        self.assertIsNotNone(self.survey.client_review_routed_at)
        self.assertEqual(self.task.status,WorkAssignment.Status.CLIENT_REVIEW)
        self.assertIsNone(self.task.completed_at)
        self.assertEqual(set(self.survey.section_approvals),{'general','power'})
        self.client.force_login(self.engineer)
        blocked=self.client.post(reverse('custom_checklist_save',args=[self.survey.pk]),json.dumps({'answers':{'condition':'Unauthorized change'}}),content_type='application/json')
        self.assertEqual(blocked.status_code,400)
        self.assertEqual(self.decision(reviewer).status_code,302)
        self.assertEqual(self.task.status,WorkAssignment.Status.COMPLETED)
        self.assertIsNotNone(self.task.completed_at)
        self.assertEqual(self.survey.status,Checklist.Status.FINAL)
        self.assertEqual(self.survey.client_approval['recorded_by'],reviewer.pk)
        self.assertTrue(self.survey.client_approval['authenticated_client'])

    def test_no_configured_client_closes_after_full_internal_approval(self):
        self.submit()
        self.review()
        self.assertEqual(self.survey.status,Checklist.Status.FINAL)
        self.assertIs(self.survey.client_review_required,False)
        self.assertEqual(self.task.status,WorkAssignment.Status.COMPLETED)
        self.assertIsNotNone(self.task.completed_at)
        self.assertEqual(self.survey.client_approval,{})

    def test_partial_approval_never_closes_or_snapshots_early(self):
        self.person('partial_client',Profile.Roles.CLIENT,self.project)
        self.submit()
        self.review('partial',['general'])
        self.assertEqual(self.survey.status,Checklist.Status.PARTIAL)
        self.assertNotEqual(self.task.status,WorkAssignment.Status.COMPLETED)
        self.assertIsNone(self.task.completed_at)
        self.assertIsNone(self.survey.client_review_required)
        self.review('partial',['power'])
        self.assertEqual(self.survey.status,Checklist.Status.FINAL)
        self.assertTrue(self.survey.client_review_required)
        self.assertIsNotNone(self.survey.client_review_routed_at)
        self.assertEqual(self.task.status,WorkAssignment.Status.CLIENT_REVIEW)

    def test_inactive_locked_or_removed_client_cannot_bypass_snapshotted_requirement(self):
        reviewer=self.person('required_client',Profile.Roles.CLIENT,self.project)
        reviewer.is_active=False
        reviewer.save()
        reviewer.profile.is_locked=True
        reviewer.profile.save()
        self.submit()
        self.review()
        self.assertTrue(self.survey.client_review_required)
        reviewer.profile.project=None
        reviewer.profile.save()
        self.assertEqual(self.decision(self.admin).status_code,302)
        self.assertEqual(self.task.status,WorkAssignment.Status.CLIENT_REVIEW)
        self.assertIsNone(self.task.completed_at)
        self.assertFalse(self.survey.client_approval['authenticated_client'])
        self.assertTrue(self.survey.client_review_required)
        reviewer.is_active=True
        reviewer.save()
        reviewer.profile.project=self.project
        reviewer.profile.is_locked=False
        reviewer.profile.save()
        self.assertEqual(self.decision(reviewer).status_code,302)
        self.assertEqual(self.task.status,WorkAssignment.Status.COMPLETED)

    def test_valid_pending_client_invitation_routes_to_client_but_expired_revoked_do_not(self):
        ProjectInvitation.objects.create(email='pending-client@example.test',role=Profile.Roles.CLIENT,project=self.project,created_by=self.admin,token_hash=hashlib.sha256(b'pending-client-synthetic').hexdigest(),expires_at=timezone.now()+timedelta(hours=1))
        self.submit()
        self.review()
        self.assertTrue(self.survey.client_review_required)
        self.assertIsNotNone(self.survey.client_review_routed_at)
        self.assertEqual(self.task.status,WorkAssignment.Status.CLIENT_REVIEW)
        ProjectInvitation.objects.update(revoked_at=timezone.now(),expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.decision(self.admin).status_code,302)
        self.assertEqual(self.task.status,WorkAssignment.Status.CLIENT_REVIEW)
        self.assertIsNone(self.task.completed_at)

    def test_expired_or_revoked_client_invites_and_foreign_clients_do_not_require_client(self):
        self.person('other_project_client',Profile.Roles.CLIENT,self.other)
        for index,attrs in enumerate([{'expires_at':timezone.now()-timedelta(seconds=1)},{'expires_at':timezone.now()+timedelta(hours=1),'revoked_at':timezone.now()}]):
            ProjectInvitation.objects.create(email=f'unavailable{index}@example.test',role=Profile.Roles.CLIENT,project=self.project,created_by=self.admin,token_hash=hashlib.sha256(str(index).encode()).hexdigest(),**attrs)
        self.submit()
        self.review()
        self.assertIs(self.survey.client_review_required,False)
        self.assertEqual(self.task.status,WorkAssignment.Status.COMPLETED)

    def test_client_rejection_keeps_open_reapproval_closes_once_and_cannot_reopen(self):
        reviewer=self.person('deciding_client',Profile.Roles.CLIENT,self.project)
        self.submit()
        self.review()
        self.assertEqual(self.decision(reviewer,'rejected').status_code,302)
        self.assertEqual(self.task.status,WorkAssignment.Status.CLIENT_REVIEW)
        self.assertIsNone(self.task.completed_at)
        self.assertEqual(self.survey.client_approval['decision'],'rejected')
        self.assertEqual(self.decision(reviewer,'approved').status_code,302)
        completed=self.task.completed_at
        self.assertIsNotNone(completed)
        history=deepcopy(self.survey.review_history)
        repeated=self.decision(reviewer,'approved')
        self.assertEqual(repeated.status_code,409)
        self.assertEqual(self.survey.review_history,history)
        self.assertEqual(self.task.completed_at,completed)
        self.assertEqual(self.decision(reviewer,'rejected').status_code,409)
        self.assertEqual(self.task.status,WorkAssignment.Status.COMPLETED)
        self.assertEqual(self.task.completed_at,completed)
        self.assertEqual(self.survey.client_approval['decision'],'approved')

    def test_stale_client_decision_never_closes_activity(self):
        reviewer=self.person('stale_client',Profile.Roles.CLIENT,self.project)
        self.submit()
        self.review()
        payload={'decision':'approved','reference':'Stale synthetic review','expected_updated_at':self.survey.updated_at.isoformat(),'expected_review_token':self.survey.client_review_token}
        Checklist.objects.filter(pk=self.survey.pk).update(review_history=[*self.survey.review_history,{'action':'Concurrent review note'}])
        self.assertEqual(self.decision(reviewer,payload=payload).status_code,409)
        self.assertEqual(self.task.status,WorkAssignment.Status.CLIENT_REVIEW)
        self.assertIsNone(self.task.completed_at)
        self.assertEqual(self.survey.client_approval,{})

    def test_client_added_after_no_client_snapshot_cannot_reopen_closed_activity(self):
        self.submit()
        self.review()
        completed=self.task.completed_at
        reviewer=self.person('late_client',Profile.Roles.CLIENT,self.project)
        self.assertEqual(self.decision(reviewer,'rejected').status_code,409)
        self.assertIs(self.survey.client_review_required,False)
        self.assertEqual(self.task.status,WorkAssignment.Status.COMPLETED)
        self.assertEqual(self.task.completed_at,completed)

    def test_super_admin_assigns_only_eligible_project_admin_and_synchronizes_scope(self):
        candidate=self.person('unassigned_project_admin',Profile.Roles.ADMIN)
        url=reverse('governance_project_admin',args=[self.project.pk])
        self.client.force_login(self.super)
        response=self.client.post(url,{'administrator':candidate.pk})
        self.assertEqual(response.status_code,302)
        self.project.refresh_from_db()
        candidate.profile.refresh_from_db()
        self.assertEqual(self.project.administrator,candidate)
        self.assertEqual(candidate.profile.project,self.project)
        self.assertEqual(candidate.profile.role,Profile.Roles.ADMIN)
        self.assertFalse(candidate.is_superuser)
        self.assertTrue(GovernanceAudit.objects.filter(actor=self.super,project=self.project).exists())
        # A different project in the same company is now a valid additional grant.
        # Preserve the security assertion using an actual different-company boundary.
        self.other.company=Company.objects.create(name='Foreign administrator company')
        self.other.save(update_fields=['company'])
        foreign=self.person('foreign_project_admin',Profile.Roles.ADMIN,self.other)
        self.assertEqual(self.client.post(url,{'administrator':foreign.pk}).status_code,400)
        self.project.refresh_from_db()
        foreign.profile.refresh_from_db()
        self.assertEqual(self.project.administrator,candidate)
        self.assertEqual(foreign.profile.project,self.other)
        for user in [self.engineer,self.lead,self.super]:
            self.assertEqual(self.client.post(url,{'administrator':user.pk}).status_code,400)
        self.project.refresh_from_db()
        self.assertEqual(self.project.administrator,candidate)
        self.client.force_login(candidate)
        for index,role in enumerate([Profile.Roles.ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.CLIENT]):
            email=f'assigned-admin-invite-{index}@example.test'
            response=self.client.post(reverse('governance_invite'),{'email':email,'role':role,'project':self.project.pk})
            self.assertEqual(response.status_code,200)
            invitation=ProjectInvitation.objects.get(email=email)
            self.assertEqual(invitation.project,self.project)
            self.assertEqual(invitation.role,role)
        self.assertIn(self.client.post(reverse('governance_invite'),{'email':'wrong-project-invite@example.test','role':Profile.Roles.TEAM_LEAD,'project':self.other.pk}).status_code,(400,403,404))

    def test_project_admin_assignment_requires_super_auth_csrf_and_rejects_locked_super(self):
        url=reverse('governance_project_admin',args=[self.project.pk])
        candidate=self.person('candidate_admin',Profile.Roles.ADMIN)
        for actor in [self.admin,self.engineer,self.lead]:
            self.client.force_login(actor)
            self.assertEqual(self.client.post(url,{'administrator':candidate.pk}).status_code,403)
        self.assertIn(Client().post(url,{'administrator':candidate.pk}).status_code,(302,403))
        strict=Client(enforce_csrf_checks=True)
        strict.force_login(self.super)
        self.assertEqual(strict.post(url,{'administrator':candidate.pk}).status_code,403)
        self.super.profile.is_locked=True
        self.super.profile.save()
        self.client.force_login(self.super)
        self.assertEqual(self.client.post(url,{'administrator':candidate.pk}).status_code,403)
        self.project.refresh_from_db()
        self.assertIsNone(self.project.administrator)

    def test_project_admin_invitation_acceptance_sets_project_administrator_and_bound_scope(self):
        self.client.force_login(self.super)
        email='new-project-administrator@example.test'
        response=self.client.post(reverse('governance_invite'),{'email':email,'role':Profile.Roles.ADMIN,'project':self.project.pk,'admin_industry':IndustryCatalog.objects.get(code=self.project.industry).pk})
        self.assertEqual(response.status_code,200)
        path=__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(response.context['invite_url']).path
        accepted=Client().post(path,{'username':'accepted_project_admin','email':email,'password1':'Accepted-admin-629!','password2':'Accepted-admin-629!'})
        self.assertEqual(accepted.status_code,302)
        user=User.objects.get(email=email)
        self.project.refresh_from_db()
        self.assertEqual(self.project.administrator,user)
        self.assertEqual(user.profile.project,self.project)
        self.assertEqual(user.profile.role,Profile.Roles.ADMIN)
        self.assertFalse(user.is_superuser or user.is_staff)

    def test_client_reject_requires_a_reason_and_preserves_waiting_stage(self):
        reviewer=self.person('reason_required_client',Profile.Roles.CLIENT,self.project)
        self.submit()
        self.review()
        payload={'decision':'rejected','reference':'','expected_updated_at':self.survey.updated_at.isoformat(),'expected_review_token':self.survey.client_review_token}
        self.assertEqual(self.decision(reviewer,payload=payload).status_code,400)
        self.assertEqual(self.survey.client_approval,{})
        self.assertEqual(self.task.status,WorkAssignment.Status.CLIENT_REVIEW)
        self.assertIsNone(self.task.completed_at)


    def test_admin_and_super_cannot_sign_engineer_submission_through_any_alias(self):
        self.survey.answer_data={'custom':{'condition':'Engineer evidence','power_notes':'Power evidence'}}
        self.survey.save()
        routes=[('custom_checklist_submit',[self.survey.pk]),('checklist_submit',[self.survey.pk]),('engineer_checklist_submit',['EngineerStage',self.survey.pk])]
        for actor in [self.admin,self.super,self.lead]:
            self.client.force_login(actor)
            for name,args in routes:
                with self.subTest(actor=actor.username,route=name):
                    self.assertEqual(self.client.post(reverse(name,args=args)).status_code,403)
            page=self.client.get(reverse('custom_checklist',args=[self.survey.pk]))
            if actor.is_superuser:
                self.assertEqual(page.status_code,403)
            else:
                self.assertFalse(page.context['can_submit'])
        self.survey.refresh_from_db()
        self.task.refresh_from_db()
        self.assertEqual(self.survey.status,Checklist.Status.DRAFT)
        self.assertEqual(self.task.status,WorkAssignment.Status.PENDING)
        self.assertIsNone(self.task.submitted_at)
        # Assigning an Admin as the record owner must not turn their signature into an Engineer's.
        self.survey.user=self.admin
        self.survey.save()
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse('custom_checklist_submit',args=[self.survey.pk])).status_code,403)

    def test_admin_super_and_engineer_cannot_sign_team_lead_review_through_aliases(self):
        self.person('stage_client',Profile.Roles.CLIENT,self.project)
        self.submit()
        before=deepcopy(self.survey.review_history)
        for actor in [self.admin,self.super,self.engineer]:
            self.client.force_login(actor)
            for name,payload in [('custom_checklist_review',{'action':'approve'}),('checklist_review_update',{'status':'FINAL','comment':'Attempted override'})]:
                with self.subTest(actor=actor.username,route=name):
                    self.assertEqual(self.client.post(reverse(name,args=[self.survey.pk]),payload).status_code,403)
            page=self.client.get(reverse('custom_checklist',args=[self.survey.pk]))
            if actor.is_superuser:
                self.assertEqual(page.status_code,403)
            else:
                self.assertFalse(page.context['can_review'])
        self.survey.refresh_from_db()
        self.task.refresh_from_db()
        self.assertEqual(self.survey.status,Checklist.Status.SUBMITTED)
        self.assertEqual(self.survey.section_approvals,{})
        self.assertEqual(self.survey.review_history,before)
        self.assertEqual(self.task.status,WorkAssignment.Status.SUBMITTED)
        self.review()
        self.assertEqual(self.task.status,WorkAssignment.Status.CLIENT_REVIEW)
        self.assertTrue(self.survey.client_review_required)
        self.assertIsNone(self.task.completed_at)

    def test_assigned_engineer_and_team_lead_can_use_legacy_signatures_without_bypassing_client(self):
        reviewer=self.person('legacy_stage_client',Profile.Roles.CLIENT,self.project)
        self.engineer.profile.path='EngStage'
        self.engineer.profile.save()
        self.survey.answer_data={'custom':{'condition':'Engineer evidence','power_notes':'Power evidence'}}
        self.survey.save()
        self.client.force_login(self.engineer)
        page=self.client.get(reverse('custom_checklist',args=[self.survey.pk]))
        self.assertTrue(page.context['can_submit'])
        self.assertFalse(page.context['can_review'])
        response=self.client.post(reverse('engineer_checklist_submit',args=['EngStage',self.survey.pk]))
        self.assertEqual(response.status_code,302)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.status,Checklist.Status.SUBMITTED)
        from .quality_workflow import review_quality
        review_quality(self.quality,self.survey,'approve','Synthetic Quality Control',self.survey.updated_at.isoformat())
        self.survey.refresh_from_db()
        self.client.force_login(self.lead)
        page=self.client.get(reverse('custom_checklist',args=[self.survey.pk]))
        self.assertTrue(page.context['can_review'])
        self.assertFalse(page.context['can_submit'])
        response=self.client.post(reverse('checklist_review_update',args=[self.survey.pk]),{'status':'FINAL','comment':'Actual Team Lead review'})
        self.assertEqual(response.status_code,302)
        self.survey.refresh_from_db()
        self.task.refresh_from_db()
        self.assertEqual(self.survey.status,Checklist.Status.FINAL)
        self.assertEqual(self.task.status,WorkAssignment.Status.CLIENT_REVIEW)
        self.assertIsNone(self.task.completed_at)
        self.assertEqual(self.decision(reviewer).status_code,302)
        self.assertEqual(self.task.status,WorkAssignment.Status.COMPLETED)


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False)
class HistoricalReviewMigrationTests(TransactionTestCase):
    def test_routing_migration_preserves_historical_completed_activity(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        previous=[('core','0018_client_role')]
        current=[('core','0019_client_review_routing')]
        executor=MigrationExecutor(connection)
        executor.migrate(previous)
        try:
            old=executor.loader.project_state(previous).apps
            OldUser=old.get_model('auth','User')
            OldProject=old.get_model('core','Project')
            OldTemplate=old.get_model('core','ChecklistTemplate')
            OldChecklist=old.get_model('core','Checklist')
            OldWork=old.get_model('core','WorkAssignment')
            engineer=OldUser.objects.create(username='historical_engineer')
            lead=OldUser.objects.create(username='historical_lead')
            schema={'title':'Historical immutable checklist','sections':[{'id':'general','title':'General','fields':[{'id':'condition','label':'Condition','type':'text'}]}]}
            template=OldTemplate.objects.create(name='Historical template',definition=schema,published=True)
            project=OldProject.objects.create(name='Historical project',checklist_template_id=template.pk)
            survey=OldChecklist.objects.create(user_id=engineer.pk,project_id=project.pk,site_id='HISTORICAL-COMPLETED',status='FINAL',checklist_template_id=template.pk,schema_snapshot=schema,answer_data={'custom':{'condition':'Historical approved value'}},section_approvals={'general':{'by':lead.pk}},client_approval={'decision':'approved','reference':'Historical evidence'},review_history=[{'action':'approve','by':lead.pk}])
            completed=timezone.now()-timedelta(days=2)
            work=OldWork.objects.create(project_id=project.pk,assigned_to_id=engineer.pk,assigned_by_id=lead.pk,checklist_id=survey.pk,site_id=survey.site_id,latitude=24,longitude=46,description='Historical completed activity',status='COMPLETED',completed_at=completed)
            executor=MigrationExecutor(connection)
            executor.migrate(current)
            new=executor.loader.project_state(current).apps
            migrated=new.get_model('core','Checklist').objects.get(pk=survey.pk)
            activity=new.get_model('core','WorkAssignment').objects.get(pk=work.pk)
            self.assertEqual(activity.status,'COMPLETED')
            self.assertEqual(activity.completed_at,completed)
            self.assertEqual(migrated.status,'FINAL')
            self.assertIsNone(migrated.client_review_required)
            self.assertIsNone(migrated.client_review_routed_at)
            self.assertIsNone(migrated.client_review_completed_at)
            self.assertEqual(migrated.schema_snapshot,schema)
            self.assertEqual(migrated.answer_data,{'custom':{'condition':'Historical approved value'}})
            self.assertEqual(migrated.section_approvals,{'general':{'by':lead.pk}})
            self.assertEqual(migrated.client_approval,{'decision':'approved','reference':'Historical evidence'})
            self.assertEqual(migrated.review_history,[{'action':'approve','by':lead.pk}])
            self.assertIsNone(new.get_model('core','Project').objects.get(pk=project.pk).administrator_id)
        finally:
            latest=MigrationExecutor(connection)
            latest.migrate(latest.loader.graph.leaf_nodes())
