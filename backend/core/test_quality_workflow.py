"""Quality Control signatures, freshness, scoped roles and historical preservation."""
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from django.test import TestCase,override_settings
from django.urls import reverse
from .models import Checklist,Project,Profile
from .quality_workflow import review_quality,assign_quality_reviewer,quality_is_current
from .independent_workflow import configure_policy,submit_revision,review_revision,revision_state,content_snapshot,snapshot_digest
from .revision_models import SubmissionRevision,RevisionDecision,ChecklistReviewPolicy

@override_settings(SECRET_KEY='qc-synthetic-tests',ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False)
class QualityWorkflowTests(TestCase):
    def setUp(self):
        self.project=Project.objects.create(name='Synthetic QC project')
        self.foreign=Project.objects.create(name='Foreign QC project')
        self.engineer=self.person('qc_engineer',Profile.Roles.ENGINEER)
        self.quality=self.person('qc_quality',Profile.Roles.QUALITY_ENGINEER)
        self.lead=self.person('qc_lead',Profile.Roles.TEAM_LEAD)
        self.pm=self.person('qc_pm',Profile.Roles.PROJECT_MANAGER)
        self.admin=self.person('qc_admin',Profile.Roles.ADMIN)
        self.other=self.person('qc_other',Profile.Roles.QUALITY_ENGINEER)
        self.c=Checklist.objects.create(user=self.engineer,project=self.project,site_id='QC-TEST',schema_snapshot={'sections':[{'id':'s','title':'Section','fields':[{'id':'a','label':'Observation','type':'text'}]}]},answer_data={'custom':{'a':'Original observation'}},quality_reviewer=self.quality)
    def person(self,name,role):
        u=User.objects.create_user(name);u.profile.role=role;u.profile.project=self.project;u.profile.save();return u
    def submitted(self):
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.post(reverse('custom_checklist_submit',args=[self.c.pk])).status_code,302)
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.SUBMITTED)
    def approve_quality(self):
        self.c.refresh_from_db()
        return review_quality(self.quality,self.c,'approve','Inspected',self.c.updated_at.isoformat())
    def test_legacy_requires_explicit_qc_before_tl_and_qc_cannot_write(self):
        self.submitted()
        self.client.force_login(self.lead)
        self.client.post(reverse('custom_checklist_review',args=[self.c.pk]),{'action':'approve'})
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.SUBMITTED)
        self.client.force_login(self.quality)
        self.assertEqual(self.client.get(reverse('custom_checklist',args=[self.c.pk])).status_code,200)
        self.assertEqual(self.client.post(reverse('photo_upload',args=[self.c.pk]),{}).status_code,403)
        self.approve_quality();self.c.refresh_from_db();self.assertTrue(quality_is_current(self.c))
        self.client.force_login(self.lead)
        self.client.post(reverse('custom_checklist_review',args=[self.c.pk]),{'action':'approve'})
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.FINAL)
    def test_qc_rejection_requires_reason_returns_engineer_and_resubmit_clears_gate(self):
        self.submitted()
        with self.assertRaises(ValidationError):review_quality(self.quality,self.c,'reject','',self.c.updated_at.isoformat())
        review_quality(self.quality,self.c,'reject','Missing evidence',self.c.updated_at.isoformat())
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.REJECTED)
        old=list(self.c.review_history)
        self.submitted();self.assertEqual(self.c.quality_approval,{})
        self.assertEqual(self.c.review_history,old)
    def test_current_qc_digest_detects_content_mutation_without_timestamp_change(self):
        self.submitted();self.approve_quality();self.c.refresh_from_db()
        Checklist.objects.filter(pk=self.c.pk).update(answer_data={'custom':{'a':'Changed after QC'}})
        self.c.refresh_from_db();self.assertFalse(quality_is_current(self.c))
        self.client.force_login(self.lead)
        self.client.post(reverse('custom_checklist_review',args=[self.c.pk]),{'action':'approve'})
        self.c.refresh_from_db();self.assertNotEqual(self.c.status,Checklist.Status.FINAL)
    def test_qc_roles_assignment_revocation_and_stale_timestamp(self):
        self.submitted()
        for actor in [self.engineer,self.lead,self.pm,self.admin,self.other]:
            with self.assertRaises(PermissionDenied):review_quality(actor,self.c,'approve','',self.c.updated_at.isoformat())
        with self.assertRaises(ValidationError):review_quality(self.quality,self.c,'approve','','stale')
        self.quality.profile.project=self.foreign;self.quality.profile.save()
        with self.assertRaises(PermissionDenied):review_quality(self.quality,self.c,'approve','',self.c.updated_at.isoformat())
    def test_assigning_existing_submission_keeps_answers_and_no_fabricated_approval(self):
        self.submitted();before=self.c.answer_data
        assign_quality_reviewer(self.admin,self.c,self.other,'Explicit reassignment',self.c.updated_at.isoformat())
        self.c.refresh_from_db();self.assertEqual(self.c.quality_reviewer_id,self.other.pk)
        self.assertEqual(self.c.answer_data,before);self.assertEqual(self.c.quality_approval,{})
        with self.assertRaises(PermissionDenied):assign_quality_reviewer(self.engineer,self.c,self.quality,'Self grant',self.c.updated_at.isoformat())
    def independent(self):
        configure_policy(self.admin,self.c,self.quality,self.lead,'QC then Team Lead',customer_required=False)
        self.c.refresh_from_db()
        with patch('core.roadmap_service.require_qualified_template'):
            return submit_revision(self.engineer,self.c)
    def test_new_independent_chain_is_qc_then_teamlead_never_pm(self):
        revision=self.independent();self.assertEqual(revision.workflow_version,2)
        with self.assertRaises(PermissionDenied):review_revision(self.lead,self.c,revision.pk,'approve')
        with self.assertRaises(PermissionDenied):review_revision(self.pm,self.c,revision.pk,'validate')
        review_revision(self.quality,self.c,revision.pk,'validate')
        review_revision(self.lead,self.c,revision.pk,'approve')
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.FINAL)
        self.assertEqual(list(revision.decisions.values_list('actor_id',flat=True)),[self.engineer.pk,self.quality.pk,self.lead.pk])
    def test_independent_qc_return_requires_correction_and_preserves_original(self):
        old=self.independent();snapshot=old.snapshot
        review_revision(self.quality,self.c,old.pk,'return','Evidence missing')
        self.c.refresh_from_db()
        with patch('core.roadmap_service.require_qualified_template'):new=submit_revision(self.engineer,self.c)
        self.assertEqual(new.parent_id,old.pk);self.assertEqual(new.workflow_version,2)
        old.refresh_from_db();self.assertEqual(old.snapshot,snapshot);self.assertEqual(revision_state(old),'returned')
    def test_historical_frozen_pm_signature_is_preserved_without_fabricated_qc(self):
        self.c.governance_mode='independent';self.c.status=Checklist.Status.SUBMITTED;self.c.save()
        policy=ChecklistReviewPolicy.objects.create(checklist=self.c,l2_reviewer=self.lead,l3_approver=self.pm,configured_by=self.admin,reason='Historical',workflow_version=1)
        snapshot=content_snapshot(self.c)
        rev=SubmissionRevision.objects.create(checklist=self.c,number=1,snapshot=snapshot,digest=snapshot_digest(snapshot),submitted_by=self.engineer,l2_reviewer=self.lead,l3_approver=self.pm)
        policy.current_revision=rev;policy.save()
        RevisionDecision.objects.create(revision=rev,action='submit',level='L1',actor=self.engineer)
        review_revision(self.lead,self.c,rev.pk,'validate');review_revision(self.pm,self.c,rev.pk,'approve')
        self.c.refresh_from_db();rev.refresh_from_db()
        self.assertEqual(rev.workflow_version,1);self.assertEqual(self.c.quality_approval,{})
        self.assertEqual(list(rev.decisions.values_list('actor_id',flat=True)),[self.engineer.pk,self.lead.pk,self.pm.pk])
    def test_http_returned_historical_policy_upgrades_without_rewriting_signatures(self):
        self.c.governance_mode='independent';self.c.status=Checklist.Status.SUBMITTED;self.c.save()
        policy=ChecklistReviewPolicy.objects.create(checklist=self.c,l2_reviewer=self.lead,l3_approver=self.pm,configured_by=self.admin,reason='Historical')
        snapshot=content_snapshot(self.c)
        old=SubmissionRevision.objects.create(checklist=self.c,number=1,snapshot=snapshot,digest=snapshot_digest(snapshot),submitted_by=self.engineer,l2_reviewer=self.lead,l3_approver=self.pm)
        policy.current_revision=old;policy.save()
        RevisionDecision.objects.create(revision=old,action='submit',level='L1',actor=self.engineer)
        review_revision(self.lead,self.c,old.pk,'return','Correction required')
        self.c.refresh_from_db()
        self.client.force_login(self.admin)
        url=reverse('roadmap_policy_assign',args=[self.c.pk])
        payload={'l2_reviewer':self.quality.pk,'l3_approver':self.lead.pk,'reason':'Upgrade to explicit QC','expected_updated_at':self.c.updated_at.isoformat()}
        self.assertEqual(self.client.post(url,{**payload,'expected_updated_at':'stale'}).status_code,409)
        self.assertEqual(self.client.post(url,payload).status_code,302)
        policy.refresh_from_db();old.refresh_from_db();self.c.refresh_from_db()
        self.assertEqual(policy.workflow_version,2);self.assertEqual(old.workflow_version,1)
        self.assertEqual(old.snapshot,snapshot);self.assertEqual(old.digest,snapshot_digest(snapshot))
        self.assertEqual(list(old.decisions.values_list('actor_id',flat=True)),[self.engineer.pk,self.lead.pk])
        with patch('core.roadmap_service.require_qualified_template'):new=submit_revision(self.engineer,self.c)
        self.assertEqual(new.workflow_version,2);self.assertEqual(new.parent_id,old.pk)
        with self.assertRaises(PermissionDenied):review_revision(self.lead,self.c,new.pk,'approve')
        review_revision(self.quality,self.c,new.pk,'validate');review_revision(self.lead,self.c,new.pk,'approve')
    def test_http_policy_configuration_rejects_csrf_foreign_reviewers_and_engineer(self):
        from django.test import Client
        self.client.force_login(self.admin)
        url=reverse('roadmap_policy_assign',args=[self.c.pk])
        payload={'l2_reviewer':self.quality.pk,'l3_approver':self.lead.pk,'reason':'Scoped reviewers','expected_updated_at':self.c.updated_at.isoformat()}
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.admin)
        self.assertEqual(strict.post(url,payload).status_code,403)
        self.quality.profile.project=self.foreign;self.quality.profile.save()
        self.assertEqual(self.client.post(url,payload).status_code,400)
        self.client.force_login(self.engineer);self.assertEqual(self.client.post(url,payload).status_code,403)
        self.assertFalse(ChecklistReviewPolicy.objects.filter(checklist=self.c).exists())
    def test_legacy_assignment_route_cannot_create_without_explicit_quality_engineer(self):
        from .models import ChecklistTemplate,WorkAssignment
        template=ChecklistTemplate.objects.create(name='QC intake schema',published=True,definition=self.c.schema_snapshot)
        self.project.checklist_template=template;self.project.save()
        self.client.force_login(self.admin)
        before=Checklist.objects.count()
        response=self.client.post(reverse('assign_work'),{'project':self.project.pk,'engineer':self.engineer.pk,'site_id':'NO-QC-ASSIGNMENT','latitude':'1','longitude':'2','description':'Synthetic route probe'})
        self.assertEqual(response.status_code,400)
        self.assertEqual(Checklist.objects.count(),before)
        self.assertFalse(WorkAssignment.objects.filter(site_id='NO-QC-ASSIGNMENT').exists())
    def test_historical_pm_frozen_report_and_source_survive_upgrade_but_not_revocation(self):
        import hashlib,tempfile
        from pathlib import Path
        from django.core.files.base import ContentFile
        from .models import PhotoEvidence,ProjectMembership
        with tempfile.TemporaryDirectory(dir=Path('.local').resolve()) as media,override_settings(MEDIA_ROOT=media):
            original=b'synthetic original frozen source'
            photo=PhotoEvidence.objects.create(checklist=self.c,filename='frozen.png',sha256=hashlib.sha256(original).hexdigest(),metadata={'format':'PNG'})
            photo.original.save('frozen.png',ContentFile(original),save=True)
            self.c.governance_mode='independent';self.c.status=Checklist.Status.SUBMITTED;self.c.save()
            policy=ChecklistReviewPolicy.objects.create(checklist=self.c,l2_reviewer=self.lead,l3_approver=self.pm,configured_by=self.admin,reason='Historical')
            snapshot=content_snapshot(self.c)
            old=SubmissionRevision.objects.create(checklist=self.c,number=1,snapshot=snapshot,digest=snapshot_digest(snapshot),submitted_by=self.engineer,l2_reviewer=self.lead,l3_approver=self.pm)
            policy.current_revision=old;policy.save()
            RevisionDecision.objects.create(revision=old,action='submit',level='L1',actor=self.engineer)
            review_revision(self.lead,self.c,old.pk,'return','Correction required')
            self.c.refresh_from_db()
            configure_policy(self.admin,self.c,self.quality,self.lead,'Upgrade current correction',customer_required=False)
            self.client.force_login(self.pm)
            report=reverse('roadmap_revision_report',args=[self.c.pk,old.pk])
            export=reverse('roadmap_revision_export',args=[self.c.pk,old.pk])
            source=reverse('roadmap_revision_source',args=[self.c.pk,old.pk,photo.pk])
            self.assertEqual(self.client.get(report).status_code,200)
            self.assertEqual(self.client.get(export).json()['snapshot'],snapshot)
            response=self.client.get(source);self.assertEqual(response.status_code,200)
            self.assertEqual(b''.join(response.streaming_content),original);response.close()
            self.assertEqual(self.client.get(reverse('custom_checklist',args=[self.c.pk])).status_code,404)
            self.assertEqual(self.client.get(reverse('photo_state',args=[self.c.pk])).status_code,404)
            ProjectMembership.objects.create(user=self.pm,project=self.project,is_active=False)
            for url in [report,export,source]:self.assertEqual(self.client.get(url).status_code,404)
