"""Qualification, failed-inspection release gates and industry compatibility."""
from django.test import TestCase,override_settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from .models import Project,Checklist,ChecklistTemplate,Profile,WorkflowTemplateQualification,FindingEvent
from .roadmap_service import qualify_template,record_finding,finding_action
from .independent_workflow import configure_policy,submit_revision,review_revision
from .governance_forms import AssignmentForm
from django.core.files.uploadedfile import SimpleUploadedFile
from .field_intake_service import preview_csv,commit_batch


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False)
class RoadmapControlTests(TestCase):
    def setUp(self):
        self.template=ChecklistTemplate.objects.create(name='Synthetic reviewed inspection',definition={'title':'Synthetic criteria','sections':[{'id':'inspection','title':'Inspection','fields':[{'id':'observation','label':'Observation','type':'text','required':False}]}]},published=True)
        self.project=Project.objects.create(name='Synthetic construction project',industry='construction',checklist_template=self.template)
        self.engineer=self.person('controls_engineer',Profile.Roles.ENGINEER)
        self.lead=self.person('controls_lead',Profile.Roles.QUALITY_ENGINEER)
        self.pm=self.person('controls_pm',Profile.Roles.TEAM_LEAD)
        self.admin=self.person('controls_admin',Profile.Roles.ADMIN)
        self.checklist=Checklist.objects.create(user=self.engineer,project=self.project,site_id='SYNTHETIC-CONTROLS',workflow_type='construction_inspection',asset_reference='Synthetic foundation',coordinate_reference={'source':'Synthetic test measurement','crs':'Synthetic test datum'})
        configure_policy(self.admin,self.checklist,self.lead,self.pm,'Separate synthetic review identities',customer_required=False)
        self.checklist.refresh_from_db()
    def person(self,name,role):
        user=User.objects.create_user(name)
        user.profile.role=role
        user.profile.project=self.project
        user.profile.save()
        return user
    def qualify(self):
        return qualify_template(self.pm,self.project,'construction_inspection','Synthetic project requirement, revision1','Synthetic independent observation and test method','Synthetic applicability only')
    def test_unqualified_or_unknown_coordinate_source_blocks_independent_submission(self):
        with self.assertRaises(ValidationError):submit_revision(self.engineer,self.checklist)
        self.qualify()
        self.checklist.coordinate_reference={}
        self.checklist.save()
        with self.assertRaises(ValidationError):submit_revision(self.engineer,self.checklist)
        self.assertFalse(self.checklist.submission_revisions.exists())
    def test_qualification_is_technical_and_immutable(self):
        with self.assertRaises(PermissionDenied):qualify_template(self.admin,self.project,'construction_inspection','criteria','method','reason')
        record=self.qualify()
        with self.assertRaises(ValidationError):WorkflowTemplateQualification.objects.filter(pk=record.pk).update(reason='rewrite')
        with self.assertRaises(ValidationError):record.delete()
    def test_blocking_finding_needs_return_remedy_and_independent_retest(self):
        self.qualify()
        finding=record_finding(self.engineer,self.checklist,'Synthetic critical defect','critical',blocking=False)
        self.assertTrue(finding.blocking)
        self.assertEqual(finding.owner_id,self.engineer.pk)
        revision=submit_revision(self.engineer,self.checklist)
        with self.assertRaises(ValidationError):review_revision(self.lead,self.checklist,revision.pk,'validate')
        with self.assertRaises(ValidationError):finding_action(self.engineer,finding,'remedy','Cannot change a frozen source')
        review_revision(self.lead,self.checklist,revision.pk,'return','Correct the synthetic defect')
        finding_action(self.engineer,finding,'remedy','Synthetic physical remedy and source evidence verified')
        with self.assertRaises(PermissionDenied):finding_action(self.engineer,finding,'retest','Self retest refused')
        with self.assertRaises(PermissionDenied):finding_action(self.admin,finding,'retest','Administrative closure refused')
        finding_action(self.lead,finding,'retest','Synthetic independent test meets recorded criteria')
        finding.refresh_from_db()
        self.assertEqual(finding.status,'closed')
        replacement=submit_revision(self.engineer,self.checklist)
        self.assertEqual(replacement.parent_id,revision.pk)
        review_revision(self.lead,self.checklist,replacement.pk,'validate')
        review_revision(self.pm,self.checklist,replacement.pk,'approve')
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status,Checklist.Status.FINAL)
        self.assertEqual(list(finding.events.values_list('action',flat=True)),['opened','remedy','retest'])
        with self.assertRaises(ValidationError):FindingEvent.objects.filter(finding=finding).delete()
    def test_construction_workflow_requires_matching_industry_and_independent_review(self):
        values={'project':self.project.pk,'engineer':self.engineer.pk,'site_id':'SYNTHETIC-NEW','latitude':1,'longitude':1,'description':'Synthetic activity','workflow_type':'telecom_survey'}
        form=AssignmentForm(values,actor=self.admin)
        self.assertFalse(form.is_valid())
        self.assertIn('workflow_type',form.errors)
        values.update(workflow_type='construction_inspection',asset_reference='Synthetic work location',governance_mode='legacy')
        form=AssignmentForm(values,actor=self.admin)
        self.assertFalse(form.is_valid())
        self.assertIn('governance_mode',form.errors)
    def test_navigation_filters_and_admin_denial(self):
        self.client.force_login(self.engineer)
        response=self.client.get('/governance/?view=projects&industry=construction&project=all')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,self.project.name)
        self.assertEqual(self.client.get('/governance/?view=administration').status_code,403)
        self.assertEqual(self.client.get('/governance/?industry=invalid').status_code,404)
    def test_bulk_preview_commit_preserves_explicit_workflow_reviewers_and_coordinate_source(self):
        import csv
        from io import StringIO
        from .models import WorkAssignment
        output=StringIO()
        writer=csv.writer(output)
        writer.writerow(['project','engineer','site_id','latitude','longitude','description','workflow_type','governance_mode','asset_reference','coordinate_source','coordinate_crs','l2_reviewer','l3_approver','client_review_required','review_reason'])
        writer.writerow([self.project.pk,self.engineer.username,'SYNTHETIC-BULK-INSPECTION','1','1','Synthetic inspection','construction_inspection','independent','Synthetic foundation','Synthetic measurement','Synthetic datum',self.lead.username,self.pm.username,'not_required','Synthetic explicit independent review'])
        batch=preview_csv(self.admin,SimpleUploadedFile('synthetic.csv',output.getvalue().encode()))
        self.assertEqual(batch.errors,[])
        ids=commit_batch(self.admin,batch)
        checklist=WorkAssignment.objects.get(pk=ids[0]).checklist
        self.assertEqual(checklist.workflow_type,'construction_inspection')
        self.assertEqual(checklist.governance_mode,'independent')
        self.assertEqual(checklist.coordinate_reference['source'],'Synthetic measurement')
        self.assertEqual(checklist.review_policy.l2_reviewer_id,self.lead.pk)
        self.assertEqual(checklist.review_policy.l3_approver_id,self.pm.pk)
    def test_expired_grant_denies_primary_fallback_review_export_and_original_scope(self):
        from django.utils import timezone
        from datetime import timedelta
        from .models import ProjectMembership
        from .access import can_access_project,users_for_project
        self.qualify()
        revision=submit_revision(self.engineer,self.checklist)
        ProjectMembership.objects.create(user=self.lead,project=self.project,is_active=True,is_primary=True,expires_at=timezone.now()-timedelta(seconds=1))
        self.assertFalse(can_access_project(self.lead,self.project))
        self.assertFalse(users_for_project(self.project).filter(pk=self.lead.pk).exists())
        self.client.force_login(self.lead)
        self.assertEqual(self.client.get(f'/governance/activities/{self.checklist.pk}/').status_code,404)
        self.assertEqual(self.client.get(f'/governance/activities/{self.checklist.pk}/revisions/{revision.pk}/export/').status_code,404)
        with self.assertRaises(PermissionDenied):review_revision(self.lead,self.checklist,revision.pk,'validate')
    def test_admin_can_grant_pm_an_expiry_without_assigning_a_technical_stage(self):
        from datetime import timedelta
        from django.utils import timezone
        from .company_service import grant_membership
        expiry=timezone.now()+timedelta(hours=1)
        grant=grant_membership(self.admin,self.pm,self.project,expires_at=expiry)
        self.assertEqual(grant.expires_at,expiry)
        self.assertTrue(grant.is_effective)
        with self.assertRaises(ValidationError):grant_membership(self.admin,self.pm,self.project,expires_at=timezone.now()-timedelta(seconds=1))
