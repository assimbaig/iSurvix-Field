"""Super Admin's administration role cannot access operational evidence or tasks."""
from types import SimpleNamespace
from io import BytesIO
from django.test import TestCase,override_settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from .models import Project,Profile,Checklist,WorkAssignment,AssignmentIntakeBatch

@override_settings(SECRET_KEY='synthetic-boundary-tests-only',ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False)
class SuperAdminBoundaryTests(TestCase):
    def setUp(self):
        self.super=User.objects.create_user('boundary_super',is_superuser=True)
        self.super.profile.role=Profile.Roles.SUPER_ADMIN
        self.super.profile.save()
        self.project=Project.objects.create(name='Synthetic boundary project')
        self.engineer=User.objects.create_user('boundary_engineer')
        self.engineer.profile.role=Profile.Roles.ENGINEER
        self.engineer.profile.project=self.project
        self.engineer.profile.save()
        self.survey=Checklist.objects.create(user=self.engineer,project=self.project,site_id='SYNTHETIC-BOUNDARY',schema_snapshot={'sections':[]})
        self.client.force_login(self.super)
    def test_direct_content_and_mutation_urls_denied(self):
        for name in ['custom_checklist','custom_checklist_download','photo_workspace','photo_state','photo_report','checklist_ai_review','checklist_ai_state','roadmap_activity']:
            with self.subTest(route=name):self.assertEqual(self.client.get(reverse(name,args=[self.survey.pk])).status_code,403)
        for name in ['custom_checklist_save','custom_checklist_submit','custom_checklist_review','photo_upload','photo_enqueue','checklist_ai_request']:
            with self.subTest(route=name):self.assertEqual(self.client.post(reverse(name,args=[self.survey.pk]),{},content_type='application/json' if name in {'custom_checklist_save','photo_enqueue'} else 'application/x-www-form-urlencoded').status_code,403)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.status,Checklist.Status.DRAFT)
        self.assertEqual(self.survey.answer_data,{})
        self.assertFalse(self.survey.photo_evidence.exists())
        self.assertFalse(WorkAssignment.objects.exists())
    def test_selector_and_authoritative_intake_services_deny_super(self):
        from .local_ai import allowed_surveys
        from .field_intake_service import create_assignment,preview_csv,commit_batch
        from .field_intake_views import assign_guard
        self.assertFalse(allowed_surveys(SimpleNamespace(user=self.super)).exists())
        for call in [lambda:assign_guard(self.super),lambda:create_assignment(self.super,{},{}),lambda:preview_csv(self.super,BytesIO(b'')),lambda:commit_batch(self.super,None)]:
            with self.assertRaises(PermissionDenied):call()
        self.assertFalse(AssignmentIntakeBatch.objects.exists())

    def test_templates_reviewer_configuration_and_legacy_aliases_denied(self):
        from .template_views import is_template_admin,template_scope
        from .independent_workflow import configure_policy
        self.assertFalse(is_template_admin(SimpleNamespace(user=self.super)))
        self.assertFalse(template_scope(self.super).exists())
        with self.assertRaises(PermissionDenied):configure_policy(self.super,self.survey,self.engineer,self.engineer,'Attempted administrative reviewer assignment',customer_required=False)
        for name in ['checklist_detail','checklist_data_api','checklist_download_zip']:
            with self.subTest(route=name):self.assertEqual(self.client.get(reverse(name,args=[self.survey.pk])).status_code,403)
        for name in ['checklist_submit','checklist_autosave_api','checklist_upload_image','assign_work']:
            args=[] if name=='assign_work' else [self.survey.pk]
            with self.subTest(route=name):self.assertEqual(self.client.post(reverse(name,args=args),{}).status_code,403)
        session=self.client.session
        session['is_dev_admin']=True
        session.save()
        self.assertEqual(self.client.post(reverse('assign_work'),{}).status_code,403)
        self.assertFalse(WorkAssignment.objects.exists())
