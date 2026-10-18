"""Isolated administrative catalog and console HTTP acceptance tests."""

import re
from django.contrib.auth.models import User
from django.test import Client,TestCase,override_settings
from django.urls import reverse
from .models import IndustryCatalog,ClientOrganization,Company,Project,Profile,Checklist,WorkAssignment

@override_settings(SECRET_KEY='synthetic-console-only',ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False)
class SuperAdminConsoleTests(TestCase):
    def setUp(self):
        self.super=User.objects.create_user('console_super',is_superuser=True)
        self.super.profile.role=Profile.Roles.SUPER_ADMIN;self.super.profile.save()
        self.company=Company.objects.create(name='Console synthetic client')
        self.project=Project.objects.create(name='Console synthetic project',company=self.company)
        self.admin=User.objects.create_user('console_admin')
        self.admin.profile.role=Profile.Roles.ADMIN;self.admin.profile.project=self.project;self.admin.profile.save()
        self.engineer=User.objects.create_user('console_engineer')
        self.engineer.profile.role=Profile.Roles.ENGINEER;self.engineer.profile.project=self.project;self.engineer.profile.save()
        self.survey=Checklist.objects.create(user=self.engineer,project=self.project,site_id='CONSOLE-TEST',schema_snapshot={'sections':[]},answer_data={'private':'PRIVATE ENGINEERING ANSWER'})
        self.assignment=WorkAssignment.objects.create(project=self.project,assigned_to=self.engineer,assigned_by=self.admin,site_id='CONSOLE-TEST',latitude=1,longitude=2,description='Synthetic administrative site',checklist=self.survey)
        self.client.force_login(self.super)
    def industry(self,**data):
        return self.client.post(reverse('governance_industry'),{'code':'energy','name':'Energy','is_active':'on',**data})
    def test_seed_catalog_and_dynamic_third_industry_project_creation(self):
        seeds=dict(IndustryCatalog.objects.filter(code__in=['telecom','construction']).values_list('code','pk'))
        self.assertEqual(set(seeds),{'telecom','construction'})
        self.assertEqual(self.industry().status_code,302)
        response=self.client.post(reverse('governance_projects'),{'name':'Energy project','company':self.company.pk,'industry':'energy'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(Project.objects.get(name='Energy project').industry,'energy')
        self.assertEqual(dict(IndustryCatalog.objects.filter(code__in=seeds).values_list('code','pk')),seeds)
    def test_deactivation_preserves_history_and_code_cannot_change_or_delete(self):
        self.assertEqual(self.industry().status_code,302)
        catalog=IndustryCatalog.objects.get(code='energy')
        project=Project.objects.create(name='Historic energy project',company=self.company,industry='energy')
        self.assertEqual(self.industry(industry_id=catalog.pk,code='renamed').status_code,409)
        self.assertEqual(self.industry(industry_id=catalog.pk,action='delete').status_code,409)
        self.assertEqual(self.industry(industry_id=catalog.pk,name='Energy renamed',is_active='').status_code,302)
        catalog.refresh_from_db();project.refresh_from_db()
        self.assertFalse(catalog.is_active);self.assertEqual(catalog.code,'energy');self.assertEqual(project.industry,'energy')
        self.assertEqual(self.client.post(reverse('governance_projects'),{'name':'Inactive rejected','industry':'energy'}).status_code,400)
        self.assertFalse(Project.objects.filter(name='Inactive rejected').exists())
        response=self.client.get(reverse('governance_home'),{'view':'projects','industry':'energy'})
        self.assertContains(response,'Historic energy project')
    def test_industry_mutations_require_super_and_csrf(self):
        for role in [Profile.Roles.ADMIN,Profile.Roles.ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.CLIENT,Profile.Roles.PROJECT_MANAGER]:
            self.admin.profile.role=role;self.admin.profile.save()
            self.client.force_login(self.admin)
            self.assertEqual(self.industry().status_code,403)
        anonymous=Client();self.assertEqual(anonymous.post(reverse('governance_industry'),{}).status_code,302)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.super)
        self.assertEqual(strict.post(reverse('governance_industry'),{'code':'energy','name':'Energy'}).status_code,403)
        self.assertFalse(IndustryCatalog.objects.filter(code='energy').exists())
    def test_five_views_global_counts_and_no_operational_payload(self):
        for view in ['dashboard','industries','clients','projects','sites']:
            response=self.client.get(reverse('governance_home'),{'view':view})
            self.assertEqual(response.status_code,200)
            nav=re.search(r'<nav class="platform-nav"[^>]*>(.*?)</nav>',response.content.decode(),re.S).group(1)
            self.assertEqual(re.findall(r'<a[^>]*>(.*?)</a>',nav,re.S),['Dashboard','Industries','Clients','Projects','Sites'])
            self.assertEqual(response.context['active_view'],view)
            self.assertFalse(response.context['can_assign'])
            for key in ['surveys','assignments','review_queue','reports']:self.assertFalse(response.context[key])
            self.assertNotContains(response,'PRIVATE ENGINEERING ANSWER')
            self.assertEqual(response.context['counts']['projects'],Project.objects.count())
            self.assertEqual(response.context['counts']['sites'],WorkAssignment.objects.count())
            self.assertEqual(response.context['counts']['clients'],ClientOrganization.objects.count())
        response=self.client.get(reverse('governance_home'),{'view':'sites'})
        self.assertEqual([x.pk for x in response.context['sites']],[self.assignment.pk])
        self.assertContains(response,'CONSOLE-TEST')
        for alias in ['my_work','administration','reviews','reports']:
            response=self.client.get(reverse('governance_home'),{'view':alias})
            self.assertEqual(response.context['active_view'],'dashboard')
        self.assertEqual(self.client.get(reverse('governance_home'),{'view':'engineering'}).status_code,404)
