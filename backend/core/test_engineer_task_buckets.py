from django.contrib.auth.models import User
from django.test import TestCase,override_settings
from django.urls import reverse
from .models import Checklist,Profile,Project,WorkAssignment


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EngineerTaskBucketTests(TestCase):
    def setUp(self):
        self.project=Project.objects.create(name='Task grouping fixture')
        self.engineer=User.objects.create_user('task_bucket_engineer')
        profile=self.engineer.profile;profile.role=Profile.Roles.ENGINEER;profile.project=self.project;profile.save()
        self.other=User.objects.create_user('task_bucket_other')
        for status in Checklist.Status.values:
            Checklist.objects.create(project=self.project,user=self.engineer,site_id='BUCKET-'+status,status=status,schema_snapshot={'sections':[]})
        Checklist.objects.create(project=self.project,user=self.other,site_id='FOREIGN-REJECTED',status=Checklist.Status.REJECTED,schema_snapshot={'sections':[]})
        WorkAssignment.objects.create(project=self.project,assigned_to=self.engineer,assigned_by=self.engineer,site_id='UNSTARTED',latitude=0,longitude=0,description='Pending assignment')
        self.client.force_login(self.engineer)

    def test_buckets_match_saved_status_without_leaking_other_engineer(self):
        expected={'pending':{'BUCKET-DRAFT','UNSTARTED'},'submitted':{'BUCKET-SUBMITTED','BUCKET-REVIEW','BUCKET-PARTIAL'},
                  'returned':{'BUCKET-REJECTED'},'completed':{'BUCKET-FINAL'}}
        for bucket,sites in expected.items():
            with self.subTest(bucket=bucket):
                response=self.client.get(reverse('task_explorer'),{'work':bucket,'project':self.project.pk})
                self.assertEqual(response.status_code,200)
                self.assertEqual({row['task_site'] for row in response.context['page_obj']},sites)
                self.assertNotContains(response,'FOREIGN-REJECTED')
                self.assertEqual(len(response.context['engineer_task_buckets']),5)
                self.assertIn('work='+bucket,response.context['export_query'])

    def test_returned_export_and_links_preserve_scope_and_filters(self):
        response=self.client.get(reverse('task_explorer'),{'work':'returned','q':'BUCKET'})
        row=list(response.context['page_obj'])[0]
        self.assertIn('return_to=',row['url'])
        self.assertIn('work%3Dreturned',row['url'])
        exported=self.client.get(reverse('task_explorer'),{'work':'returned','export':'csv'})
        self.assertContains(exported,'BUCKET-REJECTED')
        self.assertNotContains(exported,'BUCKET-DRAFT')
        self.assertNotContains(exported,'FOREIGN-REJECTED')
        invalid=self.client.get(reverse('task_explorer'),{'work':'invented'})
        self.assertEqual(invalid.context['total'],0)
        self.assertIn('work',invalid.context['form'].errors)

    def test_ai_intake_is_visible_without_manufacturing_qa_submission(self):
        from .survey_processing_models import SurveyProcessingRevision,SurveyProcessingJob
        checklist=Checklist.objects.get(site_id='BUCKET-DRAFT')
        revision=SurveyProcessingRevision.objects.create(checklist=checklist,number=1,digest='a'*64,snapshot={},submitted_by=self.engineer)
        job=SurveyProcessingJob.objects.create(revision=revision,model='synthetic',status='queued')
        response=self.client.get(reverse('task_explorer'),{'work':'pending'})
        row=next(row for row in response.context['page_obj'] if row['task_site']=='BUCKET-DRAFT')
        self.assertEqual(row['ai_status_label'],'AI Analysis queued')
        self.assertEqual(row['task_status'],Checklist.Status.DRAFT)
        job.status='ready_for_review';job.save(update_fields=['status'])
        response=self.client.get(reverse('task_explorer'),{'work':'pending'})
        row=next(row for row in response.context['page_obj'] if row['task_site']=='BUCKET-DRAFT')
        self.assertIn('Engineer review next',row['ai_status_label'])
        checklist.refresh_from_db();self.assertEqual(checklist.status,Checklist.Status.DRAFT)

    def test_legacy_photo_submission_is_visible_without_changing_route(self):
        from .models import PhotoJob
        checklist=Checklist.objects.get(site_id='BUCKET-DRAFT')
        PhotoJob.objects.create(checklist=checklist,requested_by=self.engineer,model='synthetic',schema={},status='queued')
        response=self.client.get(reverse('task_explorer'),{'work':'pending'})
        row=next(row for row in response.context['page_obj'] if row['task_site']=='BUCKET-DRAFT')
        self.assertEqual(row['ai_status_label'],'Photo AI Analysis queued')
        self.assertEqual(row['task_status'],Checklist.Status.DRAFT)
