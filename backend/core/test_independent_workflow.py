"""Security regressions for explicit review-policy grants and immutable records."""
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from .models import Checklist, Project, Profile
from .independent_workflow import configure_policy
from .revision_models import SubmissionRevision

class IndependentPolicyTests(TestCase):
    def setUp(self):
        self.project=Project.objects.create(name='Synthetic governed project')
        self.engineer=self.person('rev_engineer',Profile.Roles.ENGINEER)
        self.quality=self.person('rev_quality',Profile.Roles.QUALITY_ENGINEER)
        self.lead=self.person('rev_lead',Profile.Roles.TEAM_LEAD)
        self.admin=self.person('rev_admin',Profile.Roles.ADMIN)
        self.checklist=Checklist.objects.create(user=self.engineer,project=self.project,site_id='SYNTHETIC-REV')
    def person(self,name,role):
        user=User.objects.create_user(name)
        user.profile.role=role
        user.profile.project=self.project
        user.profile.save()
        return user
    def configure(self,actor):
        return configure_policy(actor,self.checklist,self.quality,self.lead,'Explicit synthetic reviewers',customer_required=False)
    def test_unassigned_lead_and_pm_cannot_self_grant(self):
        for actor in [self.quality,self.lead]:
            with self.assertRaises(PermissionDenied):self.configure(actor)
        from .revision_models import ChecklistReviewPolicy
        self.assertFalse(ChecklistReviewPolicy.objects.filter(checklist=self.checklist).exists())
    def test_creating_lead_can_configure_only_initial_policy(self):
        self.checklist.intake_metadata={'created_by':self.lead.pk}
        self.checklist.save()
        self.configure(self.lead)
        with self.assertRaises(PermissionDenied):self.configure(self.lead)
        self.configure(self.admin)
    def test_existing_primary_key_cannot_overwrite_frozen_snapshot(self):
        revision=SubmissionRevision.objects.create(checklist=self.checklist,number=1,snapshot={'answers':{'a':'original'}},digest='a'*64,submitted_by=self.engineer,l2_reviewer=self.quality,l3_approver=self.lead)
        replacement=SubmissionRevision(pk=revision.pk,checklist=self.checklist,number=1,snapshot={'answers':{'a':'changed'}},digest='b'*64,submitted_by=self.engineer,l2_reviewer=self.quality,l3_approver=self.lead)
        with self.assertRaises(ValidationError):replacement.save()
        with self.assertRaises(ValidationError):SubmissionRevision.objects.filter(pk=revision.pk).update(snapshot={})
        with self.assertRaises(ValidationError):revision.delete()
        revision.refresh_from_db()
        self.assertEqual(revision.snapshot['answers']['a'],'original')

    def prepared_revision(self,customer=None):
        from .models import ChecklistTemplate, WorkflowTemplateQualification
        from .roadmap_service import definition_digest
        from .independent_workflow import submit_revision
        schema={'sections':[{'id':'general','title':'General','fields':[{'id':'condition','label':'Condition','type':'text','required':True}]}]}
        template=ChecklistTemplate.objects.create(name='Synthetic qualified revision',definition=schema,published=True)
        self.checklist.checklist_template=template
        self.checklist.schema_snapshot=schema
        self.checklist.answer_data={'custom':{'condition':'Recorded observation'}}
        self.checklist.coordinate_reference={'source':'Synthetic surveyed fixture','crs':'EPSG:4326'}
        self.checklist.save()
        if customer:
            configure_policy(self.admin,self.checklist,self.quality,self.lead,"Explicit named customer",customer_reviewer=customer,customer_required=True)
        else:
            self.configure(self.admin)
        self.checklist.refresh_from_db()
        WorkflowTemplateQualification.objects.create(project=self.project,template=template,workflow_type=self.checklist.workflow_type,definition_digest=definition_digest(schema),criteria_reference='Synthetic acceptance criteria',inspection_method='Visual fixture inspection',reviewed_by=self.lead,reason='Explicit synthetic qualification')
        return submit_revision(self.engineer,self.checklist)
    def test_frozen_inputs_require_return_and_linked_correction(self):
        from .independent_workflow import review_revision, submit_revision
        revision=self.prepared_revision()
        original=revision.snapshot
        Checklist.objects.filter(pk=self.checklist.pk).update(answer_data={'custom':{'condition':'Changed after submission'}})
        with self.assertRaises(ValidationError):review_revision(self.quality,self.checklist,revision.pk,'validate')
        with self.assertRaises(PermissionDenied):review_revision(self.lead,self.checklist,revision.pk,'return','Premature stage')
        review_revision(self.quality,self.checklist,revision.pk,'return','Inputs changed; resubmit correction')
        correction=submit_revision(self.engineer,self.checklist)
        self.assertEqual(correction.parent_id,revision.pk)
        self.assertEqual(correction.number,2)
        revision.refresh_from_db()
        self.assertEqual(revision.snapshot,original)
        self.assertEqual(revision.snapshot['answers']['custom']['condition'],'Recorded observation')
    def test_only_assigned_ordered_technical_signatures_close(self):
        from .independent_workflow import review_revision
        revision=self.prepared_revision()
        for actor in [self.admin,self.lead]:
            with self.assertRaises(PermissionDenied):review_revision(actor,self.checklist,revision.pk,'approve')
        review_revision(self.quality,self.checklist,revision.pk,'validate')
        with self.assertRaises(PermissionDenied):review_revision(self.quality,self.checklist,revision.pk,'return','Stage already passed')
        review_revision(self.lead,self.checklist,revision.pk,'approve')
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status,Checklist.Status.FINAL)
        self.assertIs(self.checklist.client_review_required,False)
        self.assertEqual(list(revision.decisions.values_list('level',flat=True)),['L1','L2','L3'])

    def test_ai_selector_respects_explicit_site_reviewers(self):
        from types import SimpleNamespace
        from .local_ai import allowed_surveys
        self.checklist.schema_snapshot={'sections':[]}
        self.checklist.save()
        self.configure(self.admin)
        legacy=Checklist.objects.create(user=self.engineer,project=self.project,site_id='SYNTHETIC-LEGACY',schema_snapshot={'sections':[]})
        other_lead=self.person('rev_other_lead',Profile.Roles.TEAM_LEAD)
        other_pm=self.person('rev_other_pm',Profile.Roles.PROJECT_MANAGER)
        client=self.person('rev_client',Profile.Roles.CLIENT)
        self.assertEqual(set(allowed_surveys(SimpleNamespace(user=self.quality)).values_list('pk',flat=True)),{self.checklist.pk})
        self.assertEqual(set(allowed_surveys(SimpleNamespace(user=other_lead)).values_list('pk',flat=True)),{legacy.pk})
        self.assertEqual(set(allowed_surveys(SimpleNamespace(user=self.lead)).values_list('pk',flat=True)),{legacy.pk,self.checklist.pk})
        self.assertFalse(allowed_surveys(SimpleNamespace(user=other_pm)).exists())
        Checklist.objects.filter(pk__in=[legacy.pk,self.checklist.pk]).update(status=Checklist.Status.FINAL)
        self.assertEqual(set(allowed_surveys(SimpleNamespace(user=client)).values_list('pk',flat=True)),{legacy.pk})
        from .revision_models import ChecklistReviewPolicy
        ChecklistReviewPolicy.objects.filter(checklist=self.checklist).update(customer_required=True,customer_reviewer=client)
        self.assertEqual(set(allowed_surveys(SimpleNamespace(user=client)).values_list('pk',flat=True)),{legacy.pk,self.checklist.pk})

    def test_customer_return_creates_linked_correction_and_keeps_old_approval(self):
        from .independent_workflow import review_revision, record_customer_decision, revision_state, submit_revision, accessible_revision
        customer=self.person('rev_named_customer',Profile.Roles.CLIENT)
        revision=self.prepared_revision(customer)
        review_revision(self.quality,self.checklist,revision.pk,'validate')
        review_revision(self.lead,self.checklist,revision.pk,'approve')
        self.checklist.refresh_from_db()
        self.checklist.client_approval={'decision':'rejected','reason':'Correct evidence'}
        record_customer_decision(customer,self.checklist,'rejected','Correct evidence')
        self.assertEqual(self.checklist.client_approval['reason'],'Correct evidence')
        self.assertEqual(self.checklist.status,Checklist.Status.REJECTED)
        self.assertEqual(revision_state(revision),'customer_rejected')
        self.assertEqual(accessible_revision(customer,revision.pk).pk,revision.pk)
        self.assertTrue(revision.decisions.filter(action='approve',level='L3').exists())
        correction=submit_revision(self.engineer,self.checklist)
        self.assertEqual(correction.parent_id,revision.pk)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.client_approval,{})
        self.assertEqual(accessible_revision(customer,revision.pk).pk,revision.pk)
        with self.assertRaises(ValidationError):record_customer_decision(customer,self.checklist,'approved')
    def test_customer_approval_rejects_tampered_content_but_return_recovers(self):
        from .independent_workflow import review_revision,record_customer_decision
        customer=self.person('rev_stale_customer',Profile.Roles.CLIENT)
        revision=self.prepared_revision(customer)
        review_revision(self.quality,self.checklist,revision.pk,'validate')
        review_revision(self.lead,self.checklist,revision.pk,'approve')
        Checklist.objects.filter(pk=self.checklist.pk).update(answer_data={'custom':{'condition':'Out-of-band change'}})
        with self.assertRaises(ValidationError):record_customer_decision(customer,self.checklist,'approved')
        self.assertFalse(revision.decisions.filter(level='C1').exists())
        record_customer_decision(customer,self.checklist,'rejected','Evidence changed')
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status,Checklist.Status.REJECTED)
