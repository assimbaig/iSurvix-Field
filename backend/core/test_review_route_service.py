"""Frozen reviewer routes and repeated one-step clarification cycles."""
from copy import deepcopy
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from django.test import TestCase,override_settings
from .models import Company,Project,Profile,ProjectMembership,ChecklistTemplate,Checklist,WorkflowTemplateQualification
from .roadmap_service import definition_digest
from .independent_workflow import configure_policy,submit_revision,review_revision,is_frozen,content_snapshot
from .review_route_service import route_for,route_context,act_on_route
from .review_route_models import ReviewRouteEvent
from .workflow_service import workflow_stage,closed_activity

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ReviewRouteServiceTests(TestCase):
    def setUp(self):
        self.company=Company.objects.create(name='Synthetic route tenant')
        self.project=Project.objects.create(name='Synthetic routed project',company=self.company,review_layers=4)
        self.schema={'sections':[{'id':'general','title':'General','fields':[{'id':'fact','label':'Observed fact','type':'text','required':True}]}]}
        self.template=ChecklistTemplate.objects.create(name='Synthetic route template',definition=self.schema,published=True)
        self.project.checklist_template=self.template;self.project.save()
        self.engineer=self.person('route_engineer',Profile.Roles.ENGINEER)
        self.quality=self.person('route_quality',Profile.Roles.QUALITY_ENGINEER)
        self.lead=self.person('route_lead',Profile.Roles.TEAM_LEAD)
        self.customer=self.person('route_client',Profile.Roles.CLIENT)
        self.admin=self.person('route_admin',Profile.Roles.ADMIN)
        self.project.administrator=self.admin;self.project.save()
        WorkflowTemplateQualification.objects.create(project=self.project,template=self.template,workflow_type='telecom_survey',definition_digest=definition_digest(self.schema),criteria_reference='Synthetic approved criteria',inspection_method='Synthetic method',reviewed_by=self.lead,reason='Explicit qualification fixture')
        self.checklist=Checklist.objects.create(project=self.project,user=self.engineer,site_id='SYNTHETIC-ROUTE',coordinate_reference={'source':'Synthetic surveyed fixture','crs':'EPSG:4326'},answer_data={'custom':{'fact':'Original observed fact'}},intake_metadata={'created_by':self.lead.pk})
    def person(self,name,role):
        actor=User.objects.create_user(name,email=name+'@example.test')
        actor.profile.role=role;actor.profile.company=self.company;actor.profile.project=self.project;actor.profile.save()
        ProjectMembership.objects.create(user=actor,project=self.project,is_active=True,is_primary=True)
        return actor
    def configure(self,layers=4,enable=True):
        self.project.review_layers=layers;self.project.save()
        self.checklist.project=self.project
        if layers!=(self.checklist.intake_metadata or {}).get('project_review_layers') and enable:
            self.checklist=Checklist.objects.create(project=self.project,user=self.engineer,site_id='SYNTHETIC-ROUTE-'+str(layers),coordinate_reference={'source':'Synthetic surveyed fixture','crs':'EPSG:4326'},answer_data={'custom':{'fact':'Original observed fact'}},intake_metadata={'created_by':self.lead.pk})
        configure_policy(self.admin,self.checklist,self.quality,self.lead,'Named synthetic reviewer route',customer_required=layers==4,customer_reviewer=self.customer if layers==4 else None,enable_route=enable)
        self.checklist.refresh_from_db()
    def act(self,actor,action,reason='Recorded clarification or decision'):
        self.checklist.refresh_from_db();token=route_context(actor,self.checklist)['token']
        event=act_on_route(actor,self.checklist,action,reason,token)
        self.checklist.refresh_from_db();return event
    def submit(self):return submit_revision(self.engineer,self.checklist)
    def test_four_layers_and_client_return_moves_one_stage_then_clarifies(self):
        self.configure();revision=self.submit();frozen=deepcopy(revision.snapshot)
        self.assertEqual(workflow_stage(self.checklist),'quality_engineer')
        self.act(self.quality,'approve');self.act(self.lead,'approve')
        self.assertEqual(route_for(self.checklist).stage,'client');self.assertFalse(closed_activity(self.checklist))
        self.act(self.customer,'reject','Explain the handover record')
        route=route_for(self.checklist);self.assertEqual((route.stage,route.mode),('team_lead','clarification'));self.assertTrue(is_frozen(self.checklist))
        self.act(self.lead,'clarify','The approved report page 4 explains this observation')
        self.assertEqual(route_for(self.checklist).stage,'client')
        self.act(self.customer,'approve')
        self.assertTrue(closed_activity(self.checklist));revision.refresh_from_db();self.assertEqual(revision.snapshot,frozen)
    def test_one_step_forwarding_to_engineer_creates_new_linked_revision(self):
        self.configure();old=self.submit();self.act(self.quality,'approve');self.act(self.lead,'approve');self.act(self.customer,'reject','Review source observation')
        self.act(self.lead,'return','Quality Engineer must check report')
        self.assertEqual(route_for(self.checklist).stage,'quality_engineer')
        self.act(self.quality,'return','Engineer must capture a correction')
        self.assertEqual(route_for(self.checklist).stage,'engineer');self.assertFalse(is_frozen(self.checklist))
        self.checklist.answer_data={'custom':{'fact':'Corrected human observation'}};self.checklist.save()
        new=self.submit();self.assertEqual(new.parent_id,old.pk);self.assertEqual(new.number,2)
        old.refresh_from_db();self.assertEqual(old.snapshot['answers']['custom']['fact'],'Original observed fact')
        self.assertEqual(route_for(self.checklist).stage,'quality_engineer')
        self.checklist.refresh_from_db();self.assertFalse(self.checklist.client_approval)
    def test_repeated_cycles_append_events_without_overwriting_signatures(self):
        self.configure();revision=self.submit();self.act(self.quality,'approve')
        for _ in range(2):
            self.act(self.lead,'reject','Please explain this source')
            self.act(self.quality,'clarify','Explanation bound to the same unchanged source')
        self.act(self.lead,'approve')
        self.assertEqual(revision.decisions.filter(action='validate').count(),1)
        self.assertEqual(route_for(self.checklist).events.filter(action='reject').count(),2)
        event=route_for(self.checklist).events.first()
        with self.assertRaises(ValidationError):ReviewRouteEvent.objects.filter(pk=event.pk).update(reason='rewrite')
    def test_wrong_actor_stale_token_revocation_and_historical_endpoint_blocked(self):
        self.configure();revision=self.submit();self.checklist.refresh_from_db()
        token=route_context(self.quality,self.checklist)['token']
        for actor in [self.admin,self.lead,self.engineer]:
            with self.assertRaises(PermissionDenied):act_on_route(actor,self.checklist,'approve','',token)
        self.act(self.quality,'approve')
        with self.assertRaises(ValidationError):act_on_route(self.lead,self.checklist,'approve','',token)
        ProjectMembership.objects.filter(user=self.lead,project=self.project).update(is_active=False)
        with self.assertRaises(PermissionDenied):self.act(self.lead,'approve')
        with self.assertRaises(ValidationError):review_revision(self.quality,self.checklist,revision.pk,'validate')
    def test_three_layer_route_closes_at_lead_and_freezes_project_configuration(self):
        self.configure(3);self.submit();self.project.review_layers=4;self.project.save()
        self.act(self.quality,'approve');self.act(self.lead,'approve')
        self.assertEqual(route_for(self.checklist).layer_count,3);self.assertTrue(closed_activity(self.checklist))
        self.assertFalse(self.checklist.client_review_required)
        with self.assertRaises(PermissionDenied):self.act(self.customer,'reject')
    def test_old_policy_does_not_opt_in_and_layer_mismatch_rolls_back(self):
        self.project.review_layers=None;self.project.save()
        self.checklist=Checklist.objects.create(project=self.project,user=self.engineer,site_id='SYNTHETIC-OLD',intake_metadata={'created_by':self.lead.pk})
        self.configure(enable=False);self.assertIsNone(route_for(self.checklist))
        with self.assertRaises(ValidationError):configure_policy(self.admin,self.checklist,self.quality,self.lead,'Invalid three-layer client override',customer_required=False,enable_route=True)
        self.assertIsNone(route_for(self.checklist))
    def test_changed_frozen_inputs_cannot_be_clarified_upstream_but_can_return_downstream(self):
        self.configure();self.submit();self.act(self.quality,'approve');self.act(self.lead,'reject','Clarify the evidence')
        Checklist.objects.filter(pk=self.checklist.pk).update(answer_data={'custom':{'fact':'Tampered'}})
        with self.assertRaises(ValidationError):self.act(self.quality,'clarify','Pretend unchanged')
        self.act(self.quality,'return','Inputs differ; Engineer must correct')
        self.assertEqual(route_for(self.checklist).stage,'engineer')

    def test_client_cannot_read_unshared_corrections_but_can_read_prior_shared_revision(self):
        from django.http import Http404
        from .independent_workflow import assigned_site_access,accessible_revision
        self.configure();old=self.submit();self.act(self.quality,'approve');self.act(self.lead,'approve')
        self.assertTrue(assigned_site_access(self.customer,self.checklist))
        self.act(self.customer,'reject','Correct original source');self.act(self.lead,'return','Check source');self.act(self.quality,'return','Engineer correction required')
        self.assertFalse(assigned_site_access(self.customer,self.checklist))
        self.assertEqual(accessible_revision(self.customer,old.pk).pk,old.pk)
        new=self.submit()
        self.assertFalse(assigned_site_access(self.customer,self.checklist))
        with self.assertRaises(Http404):accessible_revision(self.customer,new.pk)
        self.assertEqual(accessible_revision(self.customer,old.pk).pk,old.pk)

    def test_frozen_layers_and_reviewer_ids_cannot_be_edited(self):
        self.configure();route=route_for(self.checklist)
        route.layer_count=3
        with self.assertRaises(ValidationError):route.save()
        with self.assertRaises(ValidationError):type(route).objects.filter(pk=route.pk).update(reviewers={})

    def test_creation_marker_enables_route_without_flag_and_survives_project_change(self):
        self.assertEqual(self.checklist.intake_metadata['project_review_layers'],4)
        self.project.review_layers=3;self.project.save()
        configure_policy(self.admin,self.checklist,self.quality,self.lead,'Creation snapshot remains authoritative',customer_required=True,customer_reviewer=self.customer)
        route=route_for(self.checklist);self.assertEqual(route.layer_count,4)
        revision=self.submit()
        self.assertEqual(revision.snapshot['review_route_policy']['layers'],4)
        self.assertEqual(revision.snapshot['review_route_policy']['reviewers']['client'],self.customer.pk)
