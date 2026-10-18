"""Retired Django admin cannot bypass Client ownership if mounted later."""
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory,TestCase
from .models import Company,Project,Profile,IndustryCatalog,ClientOrganization,Checklist

class ClientAdminFormTests(TestCase):
    def setUp(self):
        self.company=Company.objects.create(name='Client form employer')
        self.a=Project.objects.create(name='Client form A',company=self.company)
        self.b=Project.objects.create(name='Client form B',company=self.company)
        self.super=User.objects.create_user('client_form_super',is_superuser=True,is_staff=True)
        self.engineer=User.objects.create_user('client_form_engineer')
        self.engineer.profile.role=Profile.Roles.ENGINEER;self.engineer.profile.project=self.a;self.engineer.profile.company=self.company;self.engineer.profile.save()
        self.reviewer=User.objects.create_user('client_form_reviewer')
        self.reviewer.profile.role=Profile.Roles.CLIENT;self.reviewer.profile.project=self.a;self.reviewer.profile.company=self.company;self.reviewer.profile.save()
        self.request=RequestFactory().get('/admin/');self.request.user=self.super
    def form(self,profile,project):
        cls=admin.site._registry[Profile].get_form(self.request,profile,fields=['role','project','company'])
        return cls({'role':Profile.Roles.CLIENT,'project':project.pk,'company':self.company.pk},instance=profile)
    def test_super_cannot_convert_engineer_or_assign_client_primary_project(self):
        self.assertFalse(self.form(self.engineer.profile,self.a).is_valid())
        self.assertFalse(self.form(self.reviewer.profile,self.b).is_valid())
        self.reviewer.profile.refresh_from_db();self.assertEqual(self.reviewer.profile.project_id,self.a.pk)
    def test_existing_client_profile_maintenance_is_allowed_without_new_assignment(self):
        self.assertTrue(self.form(self.reviewer.profile,self.a).is_valid())
    def test_project_client_is_read_only_in_django_admin(self):
        self.assertIn('client_organization',admin.site._registry[Project].get_readonly_fields(self.request,self.a))

    def test_new_client_context_changes_digest_without_rewriting_original_snapshot(self):
        from .independent_workflow import content_snapshot,snapshot_digest
        survey=Checklist.objects.create(user=self.engineer,project=self.a,schema_snapshot={'sections':[]})
        original=content_snapshot(survey)
        self.assertNotIn('client_organization',original['project_context'])
        organization=ClientOrganization.objects.create(name='Synthetic reviewed client',company=self.company,industry=IndustryCatalog.objects.get(code='telecom'),created_by=self.engineer)
        self.a.client_organization=organization;self.a.save(update_fields=['client_organization'])
        survey.refresh_from_db()
        updated=content_snapshot(survey)
        self.assertEqual(updated['project_context']['client_organization']['id'],organization.pk)
        self.assertNotEqual(snapshot_digest(original),snapshot_digest(updated))
        self.assertNotIn('client_organization',original['project_context'])
