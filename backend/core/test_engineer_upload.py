"""Real multipart image uploads for a rejected Engineer-owned checklist."""
from io import BytesIO
from pathlib import Path
import tempfile
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from PIL import Image
from .models import Company,Project,Profile,ProjectMembership,ChecklistTemplate,Checklist,PhotoEvidence

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EngineerMultipartUploadTests(TestCase):
    def setUp(self):
        temporary=Path(__file__).resolve().parents[2]/'.local'/'tmp'
        temporary.mkdir(parents=True,exist_ok=True)
        self.media=tempfile.TemporaryDirectory(dir=temporary,prefix='engineer-upload-')
        self.addCleanup(self.media.cleanup)
        settings=override_settings(MEDIA_ROOT=self.media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.company=Company.objects.create(name='Upload test company')
        self.project=Project.objects.create(name='Upload test project',company=self.company)
        self.engineer=User.objects.create_user('upload_engineer',password='Synthetic-fixture-725!')
        profile=self.engineer.profile
        profile.role=Profile.Roles.ENGINEER
        profile.project=self.project
        profile.company=self.company
        profile.save()
        ProjectMembership.objects.create(user=self.engineer,project=self.project,is_active=True,is_primary=True)
        schema={'title':'Upload test','sections':[{'id':'evidence','title':'Evidence','fields':[{'id':'inspection','label':'Visual inspection','type':'inspection','required':True},{'id':'photo','label':'Dedicated photo','type':'photo'}]}]}
        template=ChecklistTemplate.objects.create(name='Upload test',definition=schema,published=True)
        self.project.checklist_template=template
        self.project.save()
        self.survey=Checklist.objects.create(project=self.project,user=self.engineer,site_id='SYNTHETIC-UPLOAD',status=Checklist.Status.REJECTED)
        self.client=Client(enforce_csrf_checks=True)
        self.client.force_login(self.engineer)
        self.client.get(reverse('custom_checklist',args=[self.survey.pk]))
        self.csrf=self.client.cookies['csrftoken'].value

    def image(self):
        image=BytesIO()
        Image.new('RGB',(96,64),'green').save(image,format='PNG')
        return SimpleUploadedFile('synthetic-evidence.png',image.getvalue(),content_type='image/png')

    def test_rejected_owner_uploads_images_to_inspection_and_photo_fields(self):
        for fid in ('inspection','photo'):
            response=self.client.post(reverse('custom_checklist_upload',args=[self.survey.pk,fid]),{'images':[self.image()],'csrfmiddlewaretoken':self.csrf})
            self.assertEqual(response.status_code,200,response.content)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.status,Checklist.Status.REJECTED)
        self.assertEqual(self.survey.section_approvals,{})
        self.assertEqual(self.survey.answer_data,{})
        self.assertEqual(len(self.survey.image_data['inspection']),1)
        self.assertEqual(len(self.survey.image_data['photo']),1)

    def test_rejected_owner_uploads_original_to_photo_workspace(self):
        image=self.image()
        original=image.read()
        image.seek(0)
        response=self.client.post(reverse('photo_upload',args=[self.survey.pk]),{'files':[image],'csrfmiddlewaretoken':self.csrf})
        self.assertEqual(response.status_code,201,response.content)
        photo=PhotoEvidence.objects.get(checklist=self.survey)
        with photo.original.open('rb') as saved:
            self.assertEqual(saved.read(),original)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.status,Checklist.Status.REJECTED)
        self.assertEqual(self.survey.answer_data,{})
        self.assertEqual(self.survey.section_approvals,{})

    def test_uploads_report_missing_files_and_enforce_csrf(self):
        custom=reverse('custom_checklist_upload',args=[self.survey.pk,'inspection'])
        bulk=reverse('photo_upload',args=[self.survey.pk])
        for url,key in ((custom,'images'),(bulk,'files')):
            self.assertEqual(self.client.post(url,{key:[self.image()]}).status_code,403)
            self.assertEqual(self.client.post(url,{'csrfmiddlewaretoken':self.csrf}).status_code,400)

    def test_submitted_or_approved_section_blocks_upload_without_changing_records(self):
        custom=reverse('custom_checklist_upload',args=[self.survey.pk,'inspection'])
        bulk=reverse('photo_upload',args=[self.survey.pk])
        self.survey.status=Checklist.Status.SUBMITTED
        self.survey.save()
        self.assertEqual(self.client.post(custom,{'images':[self.image()],'csrfmiddlewaretoken':self.csrf}).status_code,400)
        self.assertEqual(self.client.post(bulk,{'files':[self.image()],'csrfmiddlewaretoken':self.csrf}).status_code,409)
        self.survey.status=Checklist.Status.PARTIAL
        self.survey.section_approvals={'evidence':{'by':'synthetic reviewer'}}
        self.survey.save()
        self.assertEqual(self.client.post(custom,{'images':[self.image()],'csrfmiddlewaretoken':self.csrf}).status_code,400)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.image_data,{})
        self.assertEqual(PhotoEvidence.objects.count(),0)
