"""Industry edits preserve identity, scope, technical family and frozen history."""
from contextlib import nullcontext
from copy import deepcopy
import json
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from .models import IndustryCatalog,Company,Project,Profile,ClientOrganization,Checklist,SubmissionRevision,GovernanceAudit
from .industry_service import update_industry,create_industry,industry_family
from .governance_forms import IndustryForm

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndustryEditingTests(TestCase):
    def setUp(self):
        self.super=User.objects.create_user('industry_super',is_superuser=True)
        self.super.profile.role=Profile.Roles.SUPER_ADMIN;self.super.profile.save()
        self.industry=IndustryCatalog.objects.get(code='telecom')
        self.company=Company.objects.create(name='Synthetic industry tenant')
        self.admin=User.objects.create_user('industry_admin')
        self.admin.profile.role=Profile.Roles.ADMIN;self.admin.profile.company=self.company;self.admin.profile.admin_industry=self.industry;self.admin.profile.save()
        self.project=Project.objects.create(name='Preserved industry project',company=self.company,industry=self.industry.code,administrator=self.admin)
        self.admin.profile.project=self.project;self.admin.profile.save()
        self.org=ClientOrganization.objects.create(name='Preserved client',company=self.company,industry=self.industry,created_by=self.admin)
        self.engineer=User.objects.create_user('industry_engineer');self.engineer.profile.role=Profile.Roles.ENGINEER;self.engineer.profile.project=self.project;self.engineer.profile.company=self.company;self.engineer.profile.save()
        self.checklist=Checklist.objects.create(project=self.project,user=self.engineer,site_id='SYN-INDUSTRY',schema_snapshot={'sections':[{'id':'s','title':'Preserved','fields':[{'id':'f','label':'Observation','type':'text'}]}]},answer_data={'custom':{'f':'Human observation'}},review_history=[{'action':'Preserved human review'}])
    def update(self,**overrides):
        values={'code':'communications','name':'Communications systems','description':'Telecommunication infrastructure scope.','is_active':True,'expected_token':self.industry.edit_token}
        values.update(overrides);return update_industry(self.super,self.industry,**values)
    def test_atomic_rename_keeps_pk_foreign_keys_and_frozen_data(self):
        revision=SubmissionRevision.objects.create(checklist=self.checklist,number=1,snapshot={'schema':deepcopy(self.checklist.schema_snapshot),'project_context':{'industry':'telecom'},'answers':deepcopy(self.checklist.answer_data)},digest='a'*64,submitted_by=self.engineer,l2_reviewer=self.admin,l3_approver=self.super)
        before=deepcopy((self.checklist.schema_snapshot,self.checklist.answer_data,self.checklist.review_history,revision.snapshot))
        pk=self.industry.pk;updated=self.update()
        self.assertEqual(updated.pk,pk);self.project.refresh_from_db();self.admin.profile.refresh_from_db();self.org.refresh_from_db();self.checklist.refresh_from_db();revision.refresh_from_db()
        self.assertEqual(self.project.industry,'communications');self.assertEqual(industry_family(self.project),'telecom')
        self.assertEqual(self.admin.profile.admin_industry_id,pk);self.assertEqual(self.org.industry_id,pk)
        self.assertEqual((self.checklist.schema_snapshot,self.checklist.answer_data,self.checklist.review_history,revision.snapshot),before)
        event=GovernanceAudit.objects.filter(action='industry_updated').latest('pk')
        self.assertEqual(event.details['previous']['code'],'telecom');self.assertEqual(event.details['affected_project_ids'],[self.project.pk])
    def test_stale_collision_and_non_super_edits_leave_references_unchanged(self):
        with self.assertRaises(ValidationError):self.update(expected_token='0'*64)
        with self.assertRaises(ValidationError):self.update(expected_token='?'*64)
        with self.assertRaises(ValidationError):self.update(code='construction')
        with self.assertRaises(PermissionDenied):update_industry(self.admin,self.industry,'forged','Forged','',True,self.industry.edit_token)
        self.project.refresh_from_db();self.assertEqual(self.project.industry,'telecom')
    def test_fixed_family_and_direct_model_rename_are_protected(self):
        with self.assertRaises(ValidationError):self.update(workflow_family='construction')
        self.industry.code='unsafe_direct'
        with self.assertRaises(ValidationError):self.industry.save()
        self.industry.refresh_from_db();self.industry.workflow_family='other'
        with self.assertRaises(ValidationError):self.industry.save()
        self.industry.refresh_from_db();form=IndustryForm({'code':'telecom','name':'Telecom','workflow_family':'construction','is_active':'on','expected_token':self.industry.edit_token},instance=self.industry)
        self.assertTrue(form.is_valid(),form.errors);self.assertEqual(form.cleaned_data['workflow_family'],'telecom')
    def test_new_family_is_selectable_once_and_locked_super_denied(self):
        custom=create_industry(self.super,'civil','Civil works','Construction-family project scope.',workflow_family='construction')
        self.assertEqual(industry_family(custom),'construction');self.assertEqual(industry_family('unknown'),'other')
        self.super.profile.is_locked=True;self.super.profile.save()
        with self.assertRaises(PermissionDenied):create_industry(self.super,'forged','Forbidden')
    def test_local_description_is_proposal_only_and_has_no_images(self):
        self.client.force_login(self.super);before=(self.industry.name,self.industry.description)
        with patch('core.local_ai.inference_lease',return_value=nullcontext(lambda:None)),patch('core.local_ai.installed_models',return_value=['synthetic-model']),patch('core.local_ai.ollama',return_value={'message':{'content':json.dumps({'description':'Telecommunications covers networks and the infrastructure supporting communication services.'})}}) as model,override_settings(OLLAMA_MODEL='synthetic-model'):
            response=self.client.post(reverse('industry_description'),json.dumps({'name':'Telecommunications','code':'telecom','industry_id':self.industry.pk,'workflow_family':'construction'}),content_type='application/json')
        self.assertEqual(response.status_code,200,response.content);self.assertFalse(response.json()['saved'])
        payload=model.call_args.args[1];self.assertFalse(any('images' in message for message in payload['messages']));self.assertFalse(payload['think'])
        self.assertIn('"workflow_family": "telecom"',payload['messages'][1]['content'])
        self.industry.refresh_from_db();self.assertEqual((self.industry.name,self.industry.description),before)
    def test_description_permission_csrf_validation_and_provider_errors(self):
        url=reverse('industry_description');strict=Client(enforce_csrf_checks=True);strict.force_login(self.super)
        self.assertEqual(strict.post(url,{'name':'Telecom','code':'telecom'}).status_code,403)
        self.client.force_login(self.admin);self.assertEqual(self.client.post(url,{'name':'Telecom','code':'telecom'}).status_code,403)
        self.client.force_login(self.super);self.assertEqual(self.client.post(url,json.dumps({'name':'x'*101}),content_type='application/json').status_code,400)
        with patch('core.local_ai.inference_lease',return_value=nullcontext(lambda:None)),patch('core.local_ai.installed_models',side_effect=OSError('Local unavailable')):
            response=self.client.post(url,json.dumps({'name':'Telecom','code':'telecom'}),content_type='application/json')
        self.assertEqual(response.status_code,503);self.assertTrue(response.json()['retryable'])

    def test_creation_compatibility_and_description_content_type_bounds(self):
        form=IndustryForm({'code':'custom','name':'Custom industry','is_active':'on'})
        self.assertTrue(form.is_valid(),form.errors);self.assertEqual(form.cleaned_data['workflow_family'],'other')
        self.client.force_login(self.super);url=reverse('industry_description')
        self.assertEqual(self.client.post(url,{'name':'Telecom','code':'telecom'}).status_code,415)
        for identifier in [True,'1'*20,'-1','1.0']:
            response=self.client.post(url,json.dumps({'name':'Telecom','code':'telecom','industry_id':identifier}),content_type='application/json')
            self.assertEqual(response.status_code,400)
        self.assertEqual(self.client.post(url,json.dumps({'name':'Telecom','hints':'x'*17000}),content_type='application/json').status_code,400)
