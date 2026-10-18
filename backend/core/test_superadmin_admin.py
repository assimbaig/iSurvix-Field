"""Defense in depth if Django admin is ever mounted alongside the local console."""
from types import SimpleNamespace
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import path,reverse
from .models import Checklist,ChecklistTemplate,GeoLocation,WorkAssignment,ChecklistSection,ChecklistImage,DCPowerSystemData,TowerEquipment,ElectricalData,Project,Profile

urlpatterns=[path('admin/',admin.site.urls)]

@override_settings(ROOT_URLCONF=__name__,ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False)
class SuperAdminDjangoAdminTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('synthetic_admin_boundary',is_staff=True,is_superuser=True)
        self.client.force_login(self.user)
    def test_operational_models_deny_all_modeladmin_permissions_and_urls(self):
        request=SimpleNamespace(user=self.user)
        for model in [Checklist,ChecklistTemplate,GeoLocation,WorkAssignment,ChecklistSection,ChecklistImage,DCPowerSystemData,TowerEquipment,ElectricalData]:
            modeladmin=admin.site._registry[model]
            with self.subTest(model=model.__name__):
                for hook in ['has_module_permission','has_view_permission','has_add_permission','has_change_permission','has_delete_permission']:
                    self.assertFalse(getattr(modeladmin,hook)(request))
                prefix='admin:core_'+model._meta.model_name
                self.assertEqual(self.client.get(reverse(prefix+'_changelist')).status_code,403)
                self.assertEqual(self.client.get(reverse(prefix+'_add')).status_code,403)
                self.assertEqual(self.client.post(reverse(prefix+'_add'),{}).status_code,403)
        self.assertFalse(Checklist.objects.exists())
        self.assertFalse(WorkAssignment.objects.exists())
    def test_administrative_models_keep_super_permissions(self):
        request=SimpleNamespace(user=self.user)
        for model in [User,Profile,Project]:
            modeladmin=admin.site._registry[model]
            for hook in ['has_module_permission','has_view_permission','has_add_permission','has_change_permission']:
                with self.subTest(model=model.__name__,hook=hook):self.assertTrue(getattr(modeladmin,hook)(request))
        response=self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,reverse('admin:core_checklist_changelist'))
        self.assertContains(response,reverse('admin:core_project_changelist'))

    def test_existing_operational_change_delete_and_history_denied(self):
        project=Project.objects.create(name='Synthetic admin boundary project')
        record=Checklist.objects.create(user=self.user,project=project,site_id='SYNTHETIC-ADMIN')
        for action in ['change','delete','history']:
            url=reverse('admin:core_checklist_'+action,args=[record.pk])
            self.assertEqual(self.client.get(url).status_code,403)
            self.assertEqual(self.client.post(url,{'status':'FINAL','post':'yes'}).status_code,403)
        record.refresh_from_db()
        self.assertEqual(record.status,Checklist.Status.DRAFT)
