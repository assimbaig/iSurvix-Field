"""Isolated task entry, durable bulk preview, preloads and frozen review routes."""
import json
from copy import deepcopy
from django.contrib.auth.models import User
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from .models import (Company,Project,Profile,IndustryCatalog,ProjectMembership,ChecklistTemplate,
                     Checklist,WorkAssignment,AssignmentIntakeBatch,WorkflowTemplateQualification)


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TaskCreationTests(TestCase):
    def setUp(self):
        self.company=Company.objects.create(name='Synthetic task company')
        self.admin=self.person('task_admin',Profile.Roles.ADMIN)
        self.admin.profile.admin_industry=IndustryCatalog.objects.get(code='telecom');self.admin.profile.save()
        self.template=ChecklistTemplate.objects.create(name='Synthetic task checklist',published=True,created_by=self.admin,
            definition={'title':'Site task','sections':[{'id':'general','title':'Site information','fields':[
                {'id':'site_id','label':'Site ID','type':'text','system':'site_id'},
                {'id':'site_name','label':'Site name','type':'text'}, {'id':'address','label':'Site address','type':'text'},
                {'id':'region','label':'Region','type':'text'}, {'id':'lat','label':'Latitude','type':'number'},
                {'id':'lon','label':'Longitude','type':'number'}, {'id':'condition','label':'Recorded observation','type':'text'}]}]})
        self.project=Project.objects.create(name='Synthetic 3 layer project',company=self.company,industry='telecom',
            administrator=self.admin,review_layers=3,checklist_template=self.template)
        self.lead=self.person('task_lead',Profile.Roles.TEAM_LEAD)
        self.engineer=self.person('task_engineer',Profile.Roles.ENGINEER)
        self.quality=self.person('task_qa',Profile.Roles.QUALITY_ENGINEER)
        self.customer=self.person('task_client',Profile.Roles.CLIENT)
        self.super=self.person('task_super',Profile.Roles.SUPER_ADMIN)
        for actor in (self.admin,self.lead,self.engineer,self.quality,self.customer):
            actor.profile.project=self.project;actor.profile.save()
            ProjectMembership.objects.create(user=actor,project=self.project,is_primary=True,is_active=True)
        self.client.force_login(self.admin)

    def person(self,name,role):
        actor=User.objects.create_user(name);actor.profile.role=role;actor.profile.company=self.company;actor.profile.save();return actor

    def values(self,**extra):
        return {'action':'create','mode':'single','project':self.project.pk,'engineer':self.engineer.pk,
            'l2_reviewer':self.quality.pk,'l3_approver':self.lead.pk,'site_id':'SYN-TASK-01','latitude':'24.1','longitude':'46.2',
            'site_name':'Synthetic station','address':'Recorded station address','region':'Recorded region',
            'coordinate_source':'Synthetic site register','coordinate_crs':'EPSG:4326',**extra}

    def post(self,**extra):return self.client.post(reverse('task_create'),self.values(**extra))

    def test_create_button_is_on_admin_and_lead_home_tasks_and_project_pages(self):
        for actor in (self.admin,self.lead):
            self.client.force_login(actor)
            for route,query in [('governance_home',{}),('governance_home',{'view':'projects'}),('task_explorer',{})]:
                page=self.client.get(reverse(route),query)
                self.assertEqual(page.status_code,200)
                self.assertContains(page,reverse('task_create'))
            page=self.client.get(reverse('task_create'),{'project':self.project.pk})
            self.assertEqual(page.context['task_form'].initial['engineer'],self.engineer.pk)
            self.assertContains(page,'Create task');self.assertContains(page,'Bulk sites')

    def test_single_site_maps_recorded_information_and_follows_project_workflow(self):
        result=self.post();self.assertEqual(result.status_code,302,result.content)
        c=Checklist.objects.get(site_id='SYN-TASK-01');route=c.review_route_record
        self.assertEqual((route.layer_count,route.stage),(3,'engineer'))
        self.assertEqual(route.reviewers,{'engineer':self.engineer.pk,'quality_engineer':self.quality.pk,'team_lead':self.lead.pk})
        self.assertEqual(c.answer_data['custom']['site_name'],'Synthetic station')
        self.assertEqual(c.answer_data['custom']['lat'],'24.1');self.assertEqual(c.answer_data['custom']['address'],'Recorded station address')
        self.assertEqual(c.intake_metadata['site_information']['region'],'Recorded region')
        self.assertEqual(c.status,Checklist.Status.DRAFT);self.assertEqual(c.section_approvals,{})
        page=self.client.get(reverse('task_explorer'));self.assertContains(page,'Saved task workflow');self.assertContains(page,'Synthetic station')
        self.assertEqual([step['key'] for step in page.context['page_obj'][0]['workflow_steps']],['engineer','quality_engineer','team_lead','closed'])
        self.assertEqual(self.post().status_code,400);self.assertEqual(Checklist.objects.count(),1)

    def test_four_layer_project_requires_client_and_rejects_route_override(self):
        self.project.review_layers=4;self.project.save()
        self.assertEqual(self.post().status_code,400)
        self.assertEqual(self.post(customer_reviewer=self.customer.pk,client_review_required='not_required').status_code,400)
        self.assertEqual(Checklist.objects.count(),0)
        self.assertEqual(self.post(customer_reviewer=self.customer.pk).status_code,302)
        route=Checklist.objects.get().review_route_record
        self.assertEqual(route.layer_count,4);self.assertEqual(route.reviewers['client'],self.customer.pk)

    def test_bulk_preview_commit_replay_and_per_site_information(self):
        rows=[{'site_id':'BULK-A','site_name':'Station A','latitude':'24','longitude':'46','address':'Address A'},
              {'site_id':'BULK-B','site_name':'Station B','latitude':'25','longitude':'47','region':'Region B'}]
        response=self.post(action='preview',mode='bulk',site_id='',site_rows=json.dumps(rows))
        self.assertEqual(response.status_code,200,response.content)
        batch=response.context['batch'];self.assertIsNotNone(batch);self.assertEqual(batch.errors,[])
        self.assertEqual(Checklist.objects.count(),0)
        commit={'action':'commit','mode':'bulk','project':self.project.pk,'batch_id':batch.pk}
        for _ in range(2):self.assertEqual(self.client.post(reverse('task_create'),commit).status_code,302)
        self.assertEqual(WorkAssignment.objects.count(),2)
        for row in rows:
            c=Checklist.objects.get(site_id=row['site_id']);self.assertEqual(c.answer_data['custom']['site_name'],row['site_name'])
            self.assertEqual(c.review_route_record.layer_count,3)
            self.assertEqual(c.intake_metadata['source']['kind'],'bulk_sites')
        self.assertEqual(Checklist.objects.get(site_id='BULK-B').answer_data['custom']['region'],'Region B')

    def test_invalid_bulk_rows_do_not_partially_create_or_allow_hidden_overrides(self):
        for rows in [[{'site_id':'DUP','latitude':'24','longitude':'46'},{'site_id':'DUP','latitude':'24','longitude':'46'}],
                     [{'site_id':'OK','latitude':'24','longitude':'46'},{'site_id':'BAD','latitude':'240','longitude':'46'}],
                     [{'site_id':'BAD','latitude':'24','longitude':'46','project':999}]]:
            self.assertEqual(self.post(action='preview',mode='bulk',site_id='',site_rows=json.dumps(rows)).status_code,400)
        self.assertEqual(Checklist.objects.count(),0);self.assertEqual(WorkAssignment.objects.count(),0)

    def test_permission_project_membership_and_csrf_controls(self):
        for actor in (self.engineer,self.quality,self.customer,self.super):
            self.client.force_login(actor)
            self.assertEqual(self.client.get(reverse('task_create')).status_code,403)
            self.assertEqual(self.post().status_code,403)
        self.client.force_login(self.lead)
        foreign=Project.objects.create(name='Foreign project')
        self.assertEqual(self.client.get(reverse('task_create'),{'project':foreign.pk}).status_code,404)
        self.assertEqual(self.post(project=foreign.pk).status_code,404)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.lead)
        self.assertEqual(strict.post(reverse('task_create'),self.values()).status_code,403)

    def test_bulk_commit_rechecks_membership_schema_and_preview_owner(self):
        response=self.post(action='preview',mode='bulk',site_id='',site_rows=json.dumps([{'site_id':'BATCH','latitude':'24','longitude':'46'}]))
        batch=response.context['batch'];commit={'action':'commit','mode':'bulk','project':self.project.pk,'batch_id':batch.pk}
        self.client.force_login(self.lead)
        self.assertEqual(self.client.post(reverse('task_create'),commit).status_code,403)
        self.client.force_login(self.admin)
        ProjectMembership.objects.filter(user=self.engineer).update(is_active=False)
        self.assertEqual(self.client.post(reverse('task_create'),commit).status_code,409)
        self.assertEqual(Checklist.objects.count(),0)

    def test_explicit_general_answers_are_not_overwritten_and_history_is_preserved(self):
        before=deepcopy(self.template.definition)
        self.assertEqual(self.post(general__region='Explicit checklist region').status_code,302)
        c=Checklist.objects.get();self.assertEqual(c.answer_data['custom']['region'],'Explicit checklist region')
        self.template.refresh_from_db();self.assertEqual(self.template.definition,before)
        self.assertEqual(c.schema_snapshot,before)
        page=self.client.get(reverse('task_create'),{'return_to':'https://example.test/foreign'})
        self.assertEqual(page.context['return_to'],reverse('task_explorer'))

    def test_tasks_created_from_new_screen_submit_review_reject_and_close_on_saved_route(self):
        from .roadmap_service import definition_digest
        from .review_route_service import route_context
        WorkflowTemplateQualification.objects.create(project=self.project,template=self.template,workflow_type='telecom_survey',
            definition_digest=definition_digest(self.template.definition),criteria_reference='Synthetic project criteria',
            inspection_method='Synthetic recorded observation',reviewed_by=self.lead,reason='Isolated workflow test')
        for layers in (3,4):
            self.project.review_layers=layers;self.project.save();self.client.force_login(self.admin)
            self.assertEqual(self.post(site_id='ROUTE-'+str(layers),customer_reviewer=self.customer.pk if layers==4 else '').status_code,302)
            c=Checklist.objects.get(site_id='ROUTE-'+str(layers));original=deepcopy(c.answer_data)
            self.client.force_login(self.engineer)
            self.assertEqual(self.client.post(reverse('custom_checklist_submit',args=[c.pk])).status_code,302)
            c.refresh_from_db();self.assertEqual(c.review_route_record.stage,'quality_engineer')
            def act(actor,action):
                c.refresh_from_db();self.client.force_login(actor);token=route_context(actor,c)['token']
                result=self.client.post(reverse('review_route_action',args=[c.pk]),{'action':action,'reason':'Recorded test review','expected_token':token})
                self.assertEqual(result.status_code,302,result.content)
            for actor in (self.quality,self.lead):act(actor,'approve')
            c.refresh_from_db();self.assertEqual(c.review_route_record.stage,'client' if layers==4 else 'closed')
            if layers==4:
                act(self.customer,'reject');c.refresh_from_db();self.assertEqual(c.review_route_record.stage,'team_lead')
                act(self.lead,'clarify');act(self.customer,'approve')
            c.refresh_from_db();self.assertEqual(c.review_route_record.stage,'closed')
            self.assertEqual(c.work_assignment.status,WorkAssignment.Status.COMPLETED)
            self.assertEqual(c.answer_data,original)

    def test_activity_defaults_to_assigned_inspection_checklist_without_changing_its_flow(self):
        definition=deepcopy(self.template.definition)
        definition['wizard_context']={'version':1,'industry':'telecom','workflow_type':'telecom_inspection'}
        inspection=ChecklistTemplate.objects.create(name='Synthetic inspection',published=True,definition=definition,created_by=self.admin)
        self.project.checklist_template=inspection;self.project.save()
        page=self.client.get(reverse('task_create'),{'project':self.project.pk})
        self.assertEqual(page.context['task_form'].initial['workflow_type'],'telecom_inspection')
        self.assertEqual(self.post(asset_reference='Recorded equipment zone').status_code,302)
        c=Checklist.objects.get();self.assertEqual(c.workflow_type,'telecom_inspection')
        self.assertEqual(c.review_route_record.layer_count,3)

    def test_csv_basic_columns_and_download_retain_required_review_columns(self):
        from .field_intake_service import preview_csv,commit_batch
        from django.core.files.uploadedfile import SimpleUploadedFile
        body=f'project,engineer,site_id,site_name,address,latitude,longitude,description,l2_reviewer,l3_approver,coordinate_source,coordinate_crs\n{self.project.pk},{self.engineer.username},CSV-SITE,CSV Station,Recorded CSV address,24,46,Visit,{self.quality.username},{self.lead.username},CSV register,EPSG:4326\n'
        batch=preview_csv(self.admin,SimpleUploadedFile('sites.csv',body.encode()))
        self.assertEqual(batch.errors,[]);commit_batch(self.admin,batch)
        c=Checklist.objects.get();self.assertEqual(c.answer_data['custom']['site_name'],'CSV Station')
        sample=self.client.get(reverse('governance_bulk_sample'),{'project':self.project.pk}).content.decode()
        for column in ('site_name','address','l2_reviewer','l3_approver','customer_reviewer'):
            self.assertIn(column,sample)

    def test_bad_row_payload_and_unready_project_have_honest_errors(self):
        for value in ('{}','"invalid"','[]','not-json'):
            result=self.post(action='preview',mode='bulk',site_rows=value)
            self.assertEqual(result.status_code,400)
            self.assertEqual(result.context['entered_sites'],[])
        self.project.checklist_template=None;self.project.save()
        page=self.client.get(reverse('task_create'),{'project':self.project.pk})
        self.assertFalse(page.context['ready']);self.assertContains(page,'enabled, published checklist')
        self.assertEqual(self.post().status_code,400);self.assertEqual(Checklist.objects.count(),0)
