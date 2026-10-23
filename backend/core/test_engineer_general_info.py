"""Saved-data General Info intake; no inference, operational users or media."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

from django.db import DatabaseError
from django.test import Client,TestCase,override_settings
from django.urls import reverse

from . import test_survey_processing as fixtures,survey_processing as pipeline
from .models import (Checklist,ChecklistTemplate,ClientOrganization,GovernanceAudit,
    IndustryCatalog,PhotoJob,Profile,WorkAssignment)
from .survey_processing_models import SurveyProcessingJob


@override_settings(SECRET_KEY='isolated-engineer-general-info',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EngineerGeneralInfoTests(TestCase):
    person=fixtures.SurveyProcessingTests.person
    add_photo=fixtures.SurveyProcessingTests.add_photo

    def setUp(self):
        fixtures.SurveyProcessingTests.setUp(self)
        self.engineer.first_name='Synthetic';self.engineer.last_name='Surveyor';self.engineer.email='synthetic-surveyor@example.test'
        self.engineer.save(update_fields=['first_name','last_name','email'])
        industry,_=IndustryCatalog.objects.get_or_create(code='telecom',defaults={'name':'Synthetic telecom','workflow_family':'telecom'})
        self.customer_org=ClientOrganization.objects.create(name='Synthetic assigned client',company=self.company,
            industry=industry,created_by=self.admin)
        self.project.client_organization=self.customer_org;self.project.save(update_fields=['client_organization'])
        self.schema={'sections':[
            {'id':'civil','title':'Civil inspection','fields':[{'id':'civil_note','label':'Civil note','type':'text'}]},
            {'id':'site_info','title':'Site information','fields':[
                {'id':'fixed_site','label':'Site ID','type':'text','system':'site_id'},
                {'id':'surveyor_name','label':'Surveyor Name','type':'text'},
                {'id':'surveyor_email','label':'Surveyor Email ID','type':'text'},
                {'id':'surveyor_phone','label':'Surveyor Mobile Number','type':'text'},
                {'id':'organization','label':'Surveyor Organization Name','type':'text'},
                {'id':'project_name','label':'Project Name','type':'text'},
                {'id':'contact','label':'On-site contact','type':'text','required':True},
                {'id':'reference_note','label':'Reference','type':'text'},
                {'id':'equipment_count','label':'Equipment count','type':'number'},
                {'id':'survey_date','label':'Site Survey Date','type':'date'},
                {'id':'site_type','label':'Site type','type':'select','options':['Existing','New']},
                {'id':'site_notes','label':'Site notes','type':'textarea'},
                {'id':'latitude','label':'Latitude','type':'number'},
                {'id':'longitude','label':'Longitude','type':'number'},
                {'id':'inspection','label':'Engineering decision','type':'inspection'},
                {'id':'photo','label':'General photo','type':'photo'}]},
            {'id':'onsite_visit','title':'Recorded visit','purpose':'general_info','fields':[
                {'id':'weather','label':'Weather observed','type':'text'}]}]}
        self.template=ChecklistTemplate.objects.create(name='Synthetic General Info template',definition=self.schema,
            published=True,checklist_required=True)
        self.checklist.checklist_template=self.template;self.checklist.schema_snapshot=deepcopy(self.schema)
        self.checklist.answer_data={'custom':{'reference_note':'Preloaded assignment fact'}}
        self.checklist.intake_metadata={'source':'synthetic_assignment','site_information':{
            'site_name':'Synthetic Site A','address':'Recorded address','city':'Recorded city','region':'Recorded region'}}
        self.checklist.save(update_fields=['checklist_template','schema_snapshot','answer_data','intake_metadata'])
        self.client.force_login(self.engineer)

    def state(self,actor=None):
        if actor is not None:self.client.force_login(actor)
        response=self.client.get(reverse('photo_capture_general_information',args=[self.checklist.pk]))
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response['Cache-Control'],'private, no-store')
        return response.json()

    def rows(self,state):return {(row['scope'],row['id']):row for row in state['general_information']['fields']}

    def save_info(self,answers=None,basics=None,*,state=None,**extra):
        state=state or self.state()
        return self.client.post(reverse('photo_capture_general_information',args=[self.checklist.pk]),json.dumps({
            'expected_digest':state['digest'],'expected_general_digest':state['general_information']['digest'],
            'general_info':answers or {},'site_information':basics or {},**extra}),content_type='application/json')

    def test_get_is_read_only_prefills_known_facts_and_excludes_non_general_or_non_scalar_points(self):
        before=deepcopy((self.checklist.answer_data,self.checklist.intake_metadata,self.checklist.updated_at))
        audits=GovernanceAudit.objects.count()
        with patch('core.local_ai.ollama') as native:
            state=self.state();self.state();native.assert_not_called()
        rows=self.rows(state)
        self.assertNotIn(('general','civil_note'),rows)
        self.assertNotIn(('general','inspection'),rows);self.assertNotIn(('general','photo'),rows)
        self.assertIn(('general','weather'),rows)
        self.assertEqual(rows['general','surveyor_name']['value'],'Synthetic Surveyor')
        self.assertTrue(rows['general','surveyor_name']['editable'])
        self.assertEqual(rows['general','surveyor_email']['value'],self.engineer.email)
        self.assertEqual(rows['general','organization']['value'],self.company.name)
        self.assertEqual(rows['general','reference_note']['value'],'Preloaded assignment fact')
        self.assertEqual(rows['general','surveyor_phone']['value'],'')
        self.assertFalse(rows['general','surveyor_phone']['prefilled'])
        self.assertEqual(rows['general','survey_date']['value'],'')
        self.assertTrue(rows['general','fixed_site']['locked'])
        context={row['id']:row['value'] for row in state['general_information']['context']}
        self.assertEqual(context['client'],self.customer_org.name)
        self.checklist.refresh_from_db()
        self.assertEqual((self.checklist.answer_data,self.checklist.intake_metadata,self.checklist.updated_at),before)
        self.assertEqual(GovernanceAudit.objects.count(),audits)
        self.assertEqual(PhotoJob.objects.count(),0);self.assertEqual(SurveyProcessingJob.objects.count(),0)

    def test_save_persists_zero_explicit_blanks_manual_aliases_site_basics_and_audit(self):
        result=self.save_info({'surveyor_name':'Recorded manual development value','equipment_count':0,
            'site_type':'New','survey_date':'2026-09-01','site_notes':''}, {'site_name':'Updated site','city':''})
        self.assertEqual(result.status_code,200,result.content)
        rows=self.rows(self.state())
        self.assertEqual(rows['general','equipment_count']['value'],'0')
        self.assertEqual(rows['general','site_notes']['value'],'')
        self.assertEqual(rows['site','city']['value'],'')
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.answer_data['custom']['surveyor_name'],'Recorded manual development value')
        self.assertEqual(self.checklist.answer_data['custom']['surveyor_email'],self.engineer.email)
        self.assertEqual(self.checklist.intake_metadata['site_information']['city'],'')
        self.assertEqual(self.checklist.intake_metadata['site_information']['address'],'Recorded address')
        self.assertTrue(GovernanceAudit.objects.filter(action='engineer_general_information_saved',actor=self.engineer,project=self.project).exists())
        context={row['id']:row['value'] for row in result.json()['general_information']['context']}
        self.assertEqual(context['engineer'],'Synthetic Surveyor')
        self.assertEqual(self.checklist.status,Checklist.Status.DRAFT)
        self.assertEqual(SurveyProcessingJob.objects.count(),0)

    def test_saved_blank_is_never_replaced_by_account_or_photo_prefill(self):
        result=self.save_info({'surveyor_name':'','equipment_count':'0','survey_date':''})
        self.assertEqual(result.status_code,200,result.content)
        self.photo.metadata={'captured_at':'2026:09:01 08:30:00'};self.photo.save(update_fields=['metadata'])
        rows=self.rows(self.state())
        self.assertEqual(rows['general','surveyor_name']['value'],'')
        self.assertEqual(rows['general','equipment_count']['value'],'0')
        self.assertEqual(rows['general','survey_date']['value'],'')
        self.assertFalse(rows['general','survey_date']['prefilled'])

    def test_unambiguous_exif_prefills_but_conflicting_dates_and_gps_are_not_invented(self):
        for photo in [self.photo,self.photo2]:
            photo.metadata={'captured_at':'2026:09:01 08:30:00','gps':{'latitude':24.5,'longitude':46.5}}
            photo.save(update_fields=['metadata'])
        rows=self.rows(self.state())
        self.assertEqual(rows['general','survey_date']['value'],'2026-09-01')
        self.assertEqual(rows['general','latitude']['value'],'24.5')
        self.photo2.metadata={'captured_at':'2026:09:02 08:30:00','gps':{'latitude':25.5,'longitude':47.5}}
        self.photo2.save(update_fields=['metadata'])
        rows=self.rows(self.state())
        for field in ['survey_date','latitude','longitude']:
            self.assertEqual(rows['general',field]['value'],'')
            self.assertTrue(rows['general',field]['suggestion_conflict'])

    def test_global_and_general_digests_protect_unsaved_edits_independently(self):
        old=self.state()
        self.photo.group='Tower';self.photo.save(update_fields=['group'])
        refreshed=self.state()
        self.assertEqual(refreshed['general_information']['digest'],old['general_information']['digest'])
        stale=self.save_info({'contact':'Stale save'},state=old)
        self.assertEqual(stale.status_code,409,stale.content)
        accepted=self.save_info({'contact':'Current recorded contact'},state=refreshed)
        self.assertEqual(accepted.status_code,200,accepted.content)
        stale_field=self.save_info({'contact':'Old form overwrite'},state=accepted.json(),
            expected_general_digest=old['general_information']['digest'])
        self.assertEqual(stale_field.status_code,409,stale_field.content)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.answer_data['custom']['contact'],'Current recorded contact')

    def test_invalid_scalars_unknown_and_system_fields_fail_atomically(self):
        before=deepcopy((self.checklist.answer_data,self.checklist.intake_metadata))
        for values in [{'civil_note':'Not a General Info field'},{'fixed_site':'Forged site'},
            {'equipment_count':True},{'equipment_count':float('nan')},{'site_notes':{}},
            {'site_notes':[]},{'site_type':'Unapproved option'},{'survey_date':'01/09/2026'}]:
            with self.subTest(values=values):
                response=self.save_info(values,{'site_name':'Must not be partially saved'})
                self.assertEqual(response.status_code,409,response.content)
                self.checklist.refresh_from_db()
                self.assertEqual((self.checklist.answer_data,self.checklist.intake_metadata),before)
        forged=self.save_info({'contact':'Valid data'},system_context={'site_id':'Forged site'})
        self.assertEqual(forged.status_code,409,forged.content)

    def test_only_assigned_engineer_can_save_and_system_and_approval_locks_hold(self):
        original=self.state()
        peer=self.person('general_info_peer',Profile.Roles.ENGINEER)
        for actor in [self.admin,self.lead,self.quality,self.customer,peer]:
            self.client.force_login(actor)
            denied=self.save_info({'contact':'Unauthorized'},state=original)
            self.assertIn(denied.status_code,(403,404),denied.content)
        self.client.force_login(self.engineer)
        self.checklist.section_approvals={'site_info':{'by':self.lead.pk}}
        self.checklist.save(update_fields=['section_approvals'])
        denied=self.save_info({'contact':'Approved field overwrite'})
        self.assertEqual(denied.status_code,409,denied.content)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.engineer)
        self.assertEqual(strict.post(reverse('photo_capture_general_information',args=[self.checklist.pk]),'{}',content_type='application/json').status_code,403)

    def test_submit_materializes_prefills_queues_without_qa_open_and_freezes_profile_context(self):
        assignment=WorkAssignment.objects.create(project=self.project,assigned_to=self.engineer,assigned_by=self.lead,
            checklist=self.checklist,site_id=self.checklist.site_id,latitude=24.5,longitude=46.5,description='Synthetic assigned site')
        original_files={photo.pk:Path(photo.original.path).read_bytes() for photo in [self.photo,self.photo2]}
        first=self.state()
        submitted=self.client.post(reverse('photo_capture_submit',args=[self.checklist.pk]),json.dumps({
            'uploads_finished':True,'expected_digest':first['digest']}),content_type='application/json')
        self.assertEqual(submitted.status_code,201,submitted.content)
        revision=self.checklist.processing_revisions.get();snapshot=deepcopy(revision.snapshot)
        self.assertEqual(revision.processing_job.status,'queued')
        self.assertEqual(revision.snapshot['answers']['custom']['surveyor_name'],'Synthetic Surveyor')
        self.assertEqual(revision.snapshot['intake']['general_information_sources']['surveyor_name']['source'],'assigned_account')
        self.assertNotIn('contact',revision.snapshot['answers']['custom'],'No full checklist completion gate or invented contact')
        self.assertEqual(revision.processing_events.filter(action='capture_submitted').count(),1)
        frozen=self.state()['general_information']
        self.assertTrue(frozen['frozen']);self.assertTrue(frozen['read_only'])
        qa=Client();qa.force_login(self.quality)
        qa_state=qa.get(reverse('photo_capture_review_state',args=[self.checklist.pk]))
        self.assertEqual(qa_state.status_code,200,qa_state.content)
        submitted_info=qa_state.json()['general_information']
        self.assertEqual(submitted_info['context'],frozen['context'])
        self.assertTrue(submitted_info['read_only'])
        self.assertFalse(any(row['editable'] for row in submitted_info['fields']))
        self.engineer.first_name='Changed';self.engineer.email='changed@example.test';self.engineer.save(update_fields=['first_name','email'])
        self.company.name='Renamed company';self.company.save(update_fields=['name'])
        self.project.name='Renamed project';self.project.save(update_fields=['name'])
        self.customer_org.name='Renamed client';self.customer_org.save(update_fields=['name'])
        assignment.latitude=25.5;assignment.save(update_fields=['latitude'])
        after=self.state()['general_information']
        self.assertEqual(after['context'],frozen['context'])
        self.assertTrue(pipeline.current(revision))
        self.assertEqual(self.save_info({'contact':'Post submission edit'}).status_code,403)
        revision.refresh_from_db();self.assertEqual(revision.snapshot,snapshot)
        for photo in [self.photo,self.photo2]:self.assertEqual(Path(photo.original.path).read_bytes(),original_files[photo.pk])

    def test_absent_general_section_never_falls_back_to_first_technical_section(self):
        self.checklist.schema_snapshot={'sections':[self.schema['sections'][0]]}
        self.checklist.save(update_fields=['schema_snapshot'])
        state=self.state()
        self.assertEqual([row['scope'] for row in state['general_information']['fields']],['site']*4)
        denied=self.save_info({'civil_note':'Fallback must not happen'})
        self.assertEqual(denied.status_code,409,denied.content)

    def test_database_failure_returns_retryable_error_and_rolls_back_all_site_changes(self):
        before=deepcopy((self.checklist.answer_data,self.checklist.intake_metadata,self.checklist.review_history))
        original_files={photo.pk:Path(photo.original.path).read_bytes() for photo in [self.photo,self.photo2]}
        with patch('core.governance_views.audit',side_effect=DatabaseError('Synthetic audit persistence failure')):
            failed=self.save_info({'contact':'Must roll back'}, {'site_name':'Must also roll back'})
        self.assertEqual(failed.status_code,503,failed.content)
        self.assertIn('retry',failed.json()['error'].lower())
        self.checklist.refresh_from_db()
        self.assertEqual((self.checklist.answer_data,self.checklist.intake_metadata,self.checklist.review_history),before)
        self.assertFalse(GovernanceAudit.objects.filter(action='engineer_general_information_saved').exists())
        self.assertEqual(SurveyProcessingJob.objects.count(),0)
        for photo in [self.photo,self.photo2]:self.assertEqual(Path(photo.original.path).read_bytes(),original_files[photo.pk])
