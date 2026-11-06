"""Independent AppSec probes using isolated saved records and HTTP clients."""
import uuid
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from .models import Company, Project, Profile, IndustryCatalog, CompanyApplication


class SuperadminIndependentSecurityTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_superuser('security-owner','owner@example.test','fixture-only')
        self.company=Company.objects.create(name='<img src=x onerror=alert(123)>')
        self.foreign=Company.objects.create(name='Foreign')
        self.project=Project.objects.create(name='Foreign project',company=self.foreign)
        self.client.force_login(self.owner)

    def test_all_customer_roles_cannot_read_desk_or_post_modal_actions(self):
        for role in Profile.Roles.values:
            if role=='SUPER_ADMIN':continue
            user=User.objects.create_user('probe-'+role)
            user.profile.role=role;user.profile.company=self.company;user.profile.save()
            self.client.force_login(user)
            for view in ('companies','system'):
                with self.subTest(role=role,view=view):
                    self.assertEqual(self.client.get(reverse('governance_home'),{'view':view,'desk_company':self.foreign.pk}).status_code,404)
            self.assertEqual(self.client.get(reverse('company_onboarding_apply'),{'desk_modal':'1'}).status_code,403)
            self.assertEqual(self.client.post(reverse('company_onboarding_apply'),{'desk_return':'companies'}).status_code,403)
        self.assertEqual(CompanyApplication.objects.count(),0)

    def test_owner_cannot_mix_foreign_hierarchy_or_use_malformed_ids(self):
        for query in ({'desk_company':self.company.pk,'desk_project':self.project.pk},
                      {'desk_company':'-1'},{'desk_company':'1e2'},{'desk_company':'9'*100},
                      {'desk_project':self.project.pk},{'desk_company':'１２'}):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(reverse('governance_home'),{'view':'companies',**query}).status_code,404)

    def test_company_name_is_escaped_in_table_and_context(self):
        response=self.client.get(reverse('governance_home'),{'view':'companies'})
        self.assertContains(response,'&lt;img src=x onerror=alert(123)&gt;')
        self.assertNotContains(response,'<img src=x onerror=alert(123)>')
        response=self.client.get(reverse('governance_home'),{'view':'companies','desk_company':self.company.pk})
        self.assertNotContains(response,'<img src=x onerror=alert(123)>')

    def test_real_csrf_middleware_rejects_modal_post_without_token(self):
        protected=Client(enforce_csrf_checks=True);protected.force_login(self.owner)
        response=protected.post(reverse('company_onboarding_apply'),{'desk_return':'companies','name':'CSRF probe','email':'probe@example.test','request_key':uuid.uuid4(),'industry':IndustryCatalog.objects.first().pk})
        self.assertEqual(response.status_code,403)
        self.assertEqual(CompanyApplication.objects.count(),0)

    def test_modal_return_cannot_redirect_or_set_authority(self):
        for payload in ({'desk_return':'//evil.example'}, {'desk_return':'companies','company':self.foreign.pk}, {'desk_return':'companies','is_superuser':'1'}):
            with self.subTest(payload=payload):
                response=self.client.post(reverse('company_onboarding_apply'),payload)
                self.assertEqual(response.status_code,400)
                self.assertNotIn('Location',response)
        self.assertEqual(CompanyApplication.objects.count(),0)
