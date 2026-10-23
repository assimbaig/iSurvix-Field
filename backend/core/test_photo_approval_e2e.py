"""Isolated HTTP acceptance from original photo intake through final closure."""
import hashlib,json,tempfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from PIL import Image
from .models import Company,Project,Profile,ChecklistTemplate,Checklist,WorkAssignment
from .field_photo_service import schema_digest
from .independent_workflow import configure_policy
from .roadmap_service import qualify_template

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PhotoApprovalEndToEndTests(TestCase):
    def setUp(self):
        folder=Path(__file__).resolve().parents[2]/'.local/tmp';folder.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(dir=folder,prefix='photo-approval-e2e-');self.addCleanup(temporary.cleanup)
        storage=override_settings(MEDIA_ROOT=temporary.name);storage.enable();self.addCleanup(storage.disable)
        company=Company.objects.create(name='Synthetic end to end company')
        template=ChecklistTemplate.objects.create(name='Synthetic photo approval',published=True,definition={'title':'Photo approval','sections':[{'id':'general','title':'Site evidence','fields':[{'id':'condition','label':'Observed condition','type':'text','required':True},{'id':'overview','label':'Site overview','type':'photo','required':True}]}]})
        self.project=Project.objects.create(name='Synthetic photo approval',company=company,checklist_template=template)
        def person(name,role):
            user=User.objects.create_user(name,password='Synthetic-end-to-end-917!')
            user.profile.role=role;user.profile.project=self.project;user.profile.company=company;user.profile.save();return user
        self.engineer=person('e2e_engineer',Profile.Roles.ENGINEER)
        self.quality=person('e2e_quality',Profile.Roles.QUALITY_ENGINEER)
        self.lead=person('e2e_lead',Profile.Roles.TEAM_LEAD)
        self.admin=person('e2e_admin',Profile.Roles.ADMIN)
        self.customer=None
        self.browser=Client(enforce_csrf_checks=True)
    def actor(self,user):
        self.browser.force_login(user);self.browser.get('/governance/')
    def post(self,name,args,data,json_body=False):
        csrf=self.browser.cookies['csrftoken'].value
        if json_body:return self.browser.post(reverse(name,args=args),json.dumps(data),content_type='application/json',HTTP_X_CSRFTOKEN=csrf)
        return self.browser.post(reverse(name,args=args),{**data,'csrfmiddlewaretoken':csrf})
    def activity(self,independent=False,client_required=False):
        if client_required:
            self.customer=User.objects.create_user('e2e_customer',email='e2e_client@example.test')
            self.customer.profile.role=Profile.Roles.CLIENT;self.customer.profile.project=self.project;self.customer.profile.company=self.project.company;self.customer.profile.save()
        self.c=Checklist.objects.create(user=self.engineer,project=self.project,site_id='SYNTHETIC-PHOTO-E2E',quality_reviewer=self.quality,coordinate_reference={'source':'Synthetic fixture','crs':'Synthetic fixture'})
        self.task=WorkAssignment.objects.create(project=self.project,assigned_to=self.engineer,assigned_by=self.lead,site_id=self.c.site_id,latitude=24,longitude=46,description='Synthetic test only',checklist=self.c)
        if independent:
            qualify_template(self.lead,self.project,self.c.workflow_type,'Synthetic criteria','Synthetic method','Synthetic applicability')
            configure_policy(self.admin,self.c,self.quality,self.lead,'Synthetic explicit review stages',customer_reviewer=self.customer,customer_required=client_required)
            self.c.refresh_from_db()
        self.independent=independent
    def upload(self,color='green'):
        data=BytesIO();Image.new('RGB',(80,60),color).save(data,format='PNG');raw=data.getvalue()
        response=self.post('photo_upload',[self.c.pk],{'group':'Civil','files':[SimpleUploadedFile('synthetic-evidence.png',raw,content_type='image/png')]})
        self.assertEqual(response.status_code,201,response.content)
        return response.json()['photos'][0]['id'],raw
    def capture_and_submit(self):
        self.actor(self.engineer)
        self.assertEqual(self.post('custom_checklist_save',[self.c.pk],{'answers':{'condition':'Recorded synthetic visual observation'}},True).status_code,200)
        self.post('custom_checklist_submit',[self.c.pk],{})
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.DRAFT)
        self.photo_id,self.original=self.upload()
        self.post('custom_checklist_submit',[self.c.pk],{})
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.DRAFT)
        # Preserve this pre-category historical fixture through its real
        # mapping service. Current Engineer HTTP matching is deliberately denied.
        from .field_photo_service import review_mappings
        denied=self.post('photo_mapping',[self.c.pk],{'decisions':[{'photo_id':self.photo_id,'field_id':'overview','action':'manual'}],'expected_schema_digest':schema_digest(self.c)},True)
        self.assertEqual(denied.status_code,403,denied.content)
        review_mappings(SimpleNamespace(user=self.engineer),self.c.pk,
            [{'photo_id':self.photo_id,'field_id':'overview','action':'manual'}],schema_digest(self.c))
        self.assertEqual(self.post('custom_checklist_submit',[self.c.pk],{}).status_code,302)
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.SUBMITTED)
        self.assertEqual(self.post('photo_upload',[self.c.pk],{'group':'Civil','files':[SimpleUploadedFile('blocked.png',self.original,content_type='image/png')]}).status_code,403)
    def qc(self,decision='approve'):
        self.c.refresh_from_db();self.actor(self.quality)
        if self.independent:
            revision=self.c.review_policy.current_revision
            result=self.post('roadmap_revision_review',[self.c.pk,revision.pk],{'action':'validate' if decision=='approve' else 'return','reason':'Recorded synthetic quality decision'})
        else:result=self.post('quality_review',[self.c.pk],{'decision':decision,'reason':'Recorded synthetic quality decision','expected_updated_at':self.c.updated_at.isoformat()})
        self.assertEqual(result.status_code,302,result.content);self.c.refresh_from_db()
    def approve_lead(self):
        self.actor(self.lead)
        if self.independent:
            result=self.post('roadmap_revision_review',[self.c.pk,self.c.review_policy.current_revision_id],{'action':'approve','reason':'Recorded synthetic Team Lead approval'})
        else:result=self.post('custom_checklist_review',[self.c.pk],{'action':'approve'})
        self.assertEqual(result.status_code,302,result.content);self.c.refresh_from_db();self.task.refresh_from_db()
    def close(self,client_required):
        self.qc();self.approve_lead();self.assertEqual(self.c.status,Checklist.Status.FINAL)
        if client_required:
            self.assertEqual(self.task.status,WorkAssignment.Status.CLIENT_REVIEW);self.assertIsNone(self.task.completed_at)
            self.actor(self.customer)
            result=self.post('governance_client_approval',[self.c.pk],{'decision':'approved','reference':'Synthetic acceptance','expected_updated_at':self.c.updated_at.isoformat(),'expected_review_token':self.c.client_review_token})
            self.assertEqual(result.status_code,302,result.content)
            self.task.refresh_from_db()
        self.assertEqual(self.task.status,WorkAssignment.Status.COMPLETED);self.assertIsNotNone(self.task.completed_at)
        self.actor(self.customer or self.engineer)
        args=[self.c.pk,self.c.review_policy.current_revision_id,self.photo_id] if self.independent and self.customer else [self.c.pk,self.photo_id,'original']
        response=self.browser.get(reverse('roadmap_revision_source' if self.independent and self.customer else 'photo_evidence',args=args))
        self.assertEqual(response.status_code,200)
        exported=b''.join(response.streaming_content);response.close()
        self.assertEqual(hashlib.sha256(exported).hexdigest(),hashlib.sha256(self.original).hexdigest())
    def test_legacy_photo_to_client_closure(self):
        self.activity(client_required=True);self.capture_and_submit();self.close(True)
    def test_legacy_photo_closes_without_client(self):
        self.activity();self.capture_and_submit();self.close(False)
    def test_independent_photo_to_client_closure(self):
        self.activity(independent=True,client_required=True);self.capture_and_submit();self.close(True)
    def test_independent_photo_closes_without_client(self):
        self.activity(independent=True);self.capture_and_submit();self.close(False)
    def test_qc_reject_then_resubmit_repeats_full_photo_approval_chain(self):
        self.activity(client_required=True);self.capture_and_submit();self.qc('reject')
        self.assertEqual(self.c.status,Checklist.Status.REJECTED)
        self.actor(self.engineer);self.assertEqual(self.post('custom_checklist_submit',[self.c.pk],{}).status_code,302)
        self.c.refresh_from_db();self.assertEqual(self.c.quality_approval,{})
        self.close(True)
    def test_new_photo_after_qc_blocks_team_lead_until_quality_rechecks(self):
        self.activity();self.capture_and_submit();self.qc()
        self.actor(self.admin);self.upload('blue')
        self.approve_lead();self.assertNotEqual(self.c.status,Checklist.Status.FINAL)
        self.close(False)
