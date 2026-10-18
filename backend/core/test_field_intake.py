"""Synthetic, isolated bulk-assignment preload and Engineer edit regressions."""
import json
from io import BytesIO
from copy import deepcopy
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from .models import Company,Project,Profile,ProjectMembership,ChecklistTemplate,Checklist,WorkAssignment,AssignmentIntakeBatch
from .field_intake_service import preview_csv,commit_batch

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AssignmentIntakeTests(TestCase):
    def setUp(self):
        self.company=Company.objects.create(name='Intake company')
        self.project=Project.objects.create(name='Intake project',company=self.company)
        self.lead=self.person('intake_lead',Profile.Roles.TEAM_LEAD)
        self.engineer=self.person('intake_engineer',Profile.Roles.ENGINEER)
        self.quality=self.person('intake_quality',Profile.Roles.QUALITY_ENGINEER)
        self.schema={'title':'Intake schema','sections':[{'id':'general','title':'General information','fields':[{'id':'site','label':'Site ID','type':'text','system':'site_id'},{'id':'region','label':'Region','type':'text'},{'id':'height','label':'Confirmed tower height','type':'number'},{'id':'power','label':'Power source','type':'select','options':['Grid','Solar']}]},{'id':'inspection','title':'Inspection','fields':[{'id':'visual','label':'Inspection','type':'inspection'}]}]}
        self.template=ChecklistTemplate.objects.create(name='Intake schema',definition=self.schema,published=True)
        self.project.checklist_template=self.template
        self.project.save()
        self.client.force_login(self.lead)

    def person(self,name,role):
        user=User.objects.create_user(name,email=name+'@example.test',password='Intake-synthetic-421!')
        profile=user.profile
        profile.role=role
        profile.project=self.project
        profile.company=self.company
        profile.save()
        ProjectMembership.objects.create(user=user,project=self.project,is_active=True,is_primary=True)
        return user

    def preview(self,lines=None):
        csv=lines or f'project,engineer,site_id,latitude,longitude,description,field:region,field:height\n{self.project.pk},intake_engineer,SYNTHETIC-INTAKE-1,24.1,46.2,Visit one,Riyadh,20\n{self.project.pk},intake_engineer,SYNTHETIC-INTAKE-2,24.2,46.3,Visit two,Jeddah,30\n'
        import csv as csv_module
        from io import StringIO
        rows=list(csv_module.reader(StringIO(csv)))
        if rows and 'quality_reviewer' not in rows[0]:
            rows[0].append('quality_reviewer')
            for row in rows[1:]:row.append(self.quality.username)
        output=StringIO();csv_module.writer(output).writerows(rows)
        return preview_csv(self.lead,SimpleUploadedFile('synthetic-sites.csv',output.getvalue().encode(),'text/csv'))

    def test_preview_has_no_tasks_then_commit_prefills_editable_snapshot_and_provenance(self):
        batch=self.preview()
        self.assertEqual(batch.errors,[])
        self.assertEqual(WorkAssignment.objects.count(),0)
        with transaction.atomic():
            result=commit_batch(self.lead,batch)
        self.assertEqual(len(result),2)
        survey=Checklist.objects.get(site_id='SYNTHETIC-INTAKE-1')
        self.assertEqual(survey.answer_data,{'custom':{'region':'Riyadh','height':'20'}})
        self.assertEqual(survey.intake_metadata['source']['kind'],'bulk_csv')
        self.assertEqual(survey.intake_metadata['source']['batch_id'],batch.pk)
        self.assertEqual(survey.status,Checklist.Status.DRAFT)
        self.assertEqual(survey.section_approvals,{})
        self.assertEqual(survey.schema_snapshot,self.schema)
        self.assertEqual(commit_batch(self.lead,batch),result)
        self.assertEqual(WorkAssignment.objects.count(),2)

    def test_invalid_row_or_duplicate_prevents_entire_commit(self):
        for body in [f'project,engineer,site_id,latitude,longitude,description\n{self.project.pk},intake_engineer,DUP,24,46,One\n{self.project.pk},intake_engineer,DUP,25,47,Two\n',f'project,engineer,site_id,latitude,longitude,description,field:height\n{self.project.pk},intake_engineer,VALID,24,46,One,20\n{self.project.pk},intake_engineer,INVALID,240,46,Two,not-number\n']:
            batch=self.preview(body)
            self.assertTrue(batch.errors)
            with self.assertRaises(ValidationError):
                commit_batch(self.lead,batch)
        self.assertEqual(WorkAssignment.objects.count(),0)
        self.assertEqual(Checklist.objects.count(),0)

    def test_commit_rechecks_duplicate_site_and_template_change_before_creating_any_row(self):
        batch=self.preview()
        WorkAssignment.objects.create(project=self.project,assigned_to=self.engineer,assigned_by=self.lead,site_id='SYNTHETIC-INTAKE-2',latitude=24,longitude=46,description='Concurrent assignment')
        with self.assertRaises(ValidationError):
            commit_batch(self.lead,batch)
        self.assertEqual(WorkAssignment.objects.count(),1)
        self.assertEqual(Checklist.objects.count(),0)
        WorkAssignment.objects.all().delete()
        replacement=ChecklistTemplate.objects.create(name='Replacement',definition=deepcopy(self.schema),published=True)
        self.project.checklist_template=replacement
        self.project.save()
        with self.assertRaises(ValidationError):
            commit_batch(self.lead,batch)
        self.assertEqual(WorkAssignment.objects.count(),0)

    def test_system_unknown_and_inspection_fields_are_not_silently_prefilled(self):
        for field in ('site','missing','visual'):
            batch=self.preview(f'project,engineer,site_id,latitude,longitude,description,field:{field}\n{self.project.pk},intake_engineer,SYNTHETIC,24,46,Test,Value\n')
            self.assertTrue(batch.errors)
        self.assertEqual(Checklist.objects.count(),0)

    def test_membership_revocation_after_preview_blocks_commit(self):
        batch=self.preview()
        ProjectMembership.objects.filter(user=self.engineer,project=self.project).update(is_active=False)
        with self.assertRaises(ValidationError):
            commit_batch(self.lead,batch)
        self.assertEqual(WorkAssignment.objects.count(),0)

    def test_single_assignment_preload_and_engineer_edit_preserve_site_id_and_locks(self):
        response=self.client.post(reverse('governance_assign'),{'project':self.project.pk,'engineer':self.engineer.pk,'quality_reviewer':self.quality.pk,'site_id':'SYNTHETIC-SINGLE','latitude':'24','longitude':'46','description':'Visit','general_info':json.dumps({'region':'Initial region'})})
        self.assertEqual(response.status_code,302,response.content)
        survey=Checklist.objects.get(site_id='SYNTHETIC-SINGLE')
        self.assertEqual(survey.answer_data['custom']['region'],'Initial region')
        self.client.force_login(self.engineer)
        url=reverse('checklist_site_information',args=[survey.pk])
        state=self.client.get(url).json()
        response=self.client.post(url,json.dumps({'answers':{'region':'Confirmed onsite'},'expected_updated_at':state['updated_at']}),content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        survey.refresh_from_db()
        self.assertEqual(survey.answer_data['custom']['region'],'Confirmed onsite')
        self.assertEqual(survey.intake_metadata['source']['kind'],'single_assignment')
        stale=self.client.post(url,json.dumps({'answers':{'region':'Stale'},'expected_updated_at':state['updated_at']}),content_type='application/json')
        self.assertEqual(stale.status_code,409)
        state=self.client.get(url).json()
        blocked=self.client.post(url,json.dumps({'answers':{'site':'MUTATED'},'expected_updated_at':state['updated_at']}),content_type='application/json')
        self.assertEqual(blocked.status_code,400)
        survey.section_approvals={'general':{'by':self.lead.pk}}
        survey.status=Checklist.Status.PARTIAL
        survey.save()
        locked=self.client.post(url,json.dumps({'answers':{'region':'Locked'},'expected_updated_at':survey.updated_at.isoformat()}),content_type='application/json')
        self.assertEqual(locked.status_code,400)
        survey.refresh_from_db()
        self.assertEqual(survey.site_id,'SYNTHETIC-SINGLE')
        self.assertEqual(survey.answer_data['custom']['region'],'Confirmed onsite')

    def test_bulk_endpoints_require_authority_csrf_and_bind_preview_to_creator(self):
        strict=Client(enforce_csrf_checks=True)
        strict.force_login(self.lead)
        url=reverse('governance_bulk_assign')
        self.assertEqual(strict.post(url,{'action':'preview'}).status_code,403)
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.get(url).status_code,403)
        self.assertEqual(self.client.post(url,{'action':'preview'}).status_code,403)
        batch=self.preview()
        other=self.person('other_intake_lead',Profile.Roles.TEAM_LEAD)
        self.client.force_login(other)
        self.assertEqual(self.client.post(url,{'action':'commit','batch_id':batch.pk}).status_code,403)
        self.assertEqual(WorkAssignment.objects.count(),0)

    def test_csv_answers_json_and_commit_failure_rolls_back_every_assignment(self):
        import csv
        from io import StringIO
        from unittest.mock import patch
        from . import field_intake_service as service
        output=StringIO()
        writer=csv.writer(output)
        writer.writerow(['project','engineer','site_id','latitude','longitude','description','answers_json'])
        writer.writerow([self.project.pk,'intake_engineer','JSON-ONE',24,46,'Visit',json.dumps({'region':'Confirmed region','power':'Grid'})])
        writer.writerow([self.project.pk,'intake_engineer','JSON-TWO',24,46,'Visit',json.dumps({'region':'Second region'})])
        batch=self.preview(output.getvalue())
        self.assertFalse(batch.errors)
        original=service.create_assignment
        count=0
        def fail_second(*args,**kwargs):
            nonlocal count
            count+=1
            if count==2:
                raise RuntimeError('Synthetic failure after first create')
            return original(*args,**kwargs)
        with patch('core.field_intake_service.create_assignment',side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                commit_batch(self.lead,batch)
        self.assertEqual(WorkAssignment.objects.count(),0)
        self.assertEqual(Checklist.objects.count(),0)
        batch.refresh_from_db()
        self.assertEqual(batch.status,'preview')
        self.assertEqual(batch.result_ids,[])
