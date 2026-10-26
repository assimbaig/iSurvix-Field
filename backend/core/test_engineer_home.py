from urllib.parse import urlsplit,parse_qs

from django.contrib.auth.models import User
from django.test import TestCase,override_settings
from django.urls import reverse

from .models import Checklist,Profile,Project,WorkAssignment


@override_settings(SECRET_KEY='synthetic-engineer-home',ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EngineerHomeTests(TestCase):
    def setUp(self):
        self.project=Project.objects.create(name='Engineer home synthetic project')
        self.engineer=self.person('home_engineer',Profile.Roles.ENGINEER)
        self.lead=self.person('home_lead',Profile.Roles.TEAM_LEAD)
        self.foreign=self.person('home_foreign',Profile.Roles.ENGINEER,Project.objects.create(name='Foreign synthetic project'))
        self.draft=self.survey('HOME-DRAFT',Checklist.Status.DRAFT)
        self.rejected=self.survey('HOME-RETURNED',Checklist.Status.REJECTED)
        self.submitted=self.survey('HOME-SUBMITTED',Checklist.Status.SUBMITTED)
        self.assignment('HOME-LINKED-DRAFT',self.engineer,self.project,self.draft,WorkAssignment.Status.IN_PROGRESS)
        self.assignment('HOME-LINKED-RETURNED',self.engineer,self.project,self.rejected,WorkAssignment.Status.IN_PROGRESS)
        self.assignment('HOME-UNLINKED-PENDING',self.engineer,self.project,None,WorkAssignment.Status.PENDING)
        self.survey('HOME-FOREIGN',Checklist.Status.DRAFT,self.foreign,self.foreign.profile.project)
        self.assignment('HOME-FOREIGN-ASSIGNMENT',self.foreign,self.foreign.profile.project,None,WorkAssignment.Status.PENDING)
        self.client.force_login(self.engineer)

    def person(self,name,role,project=None):
        user=User.objects.create_user(name)
        user.profile.role=role;user.profile.project=project or self.project;user.profile.save()
        return user

    def survey(self,site,status,user=None,project=None):
        return Checklist.objects.create(site_id=site,status=status,user=user or self.engineer,project=project or self.project)

    def assignment(self,site,user,project,checklist,status):
        return WorkAssignment.objects.create(site_id=site,assigned_to=user,assigned_by=self.lead,project=project,
            checklist=checklist,status=status,latitude='24.0000000',longitude='46.0000000',description='Synthetic field task')

    def test_engineer_landing_has_only_three_scoped_summary_metrics_and_actionable_links(self):
        response=self.client.get(reverse('governance_home'))
        self.assertEqual(response.status_code,200)
        metrics=response.context['engineer_home_metrics']
        self.assertEqual([(item['label'],item['count']) for item in metrics],[
            ('Total assigned scope',4),('Pending for submission',2),('Rejected pending for response',1)])
        for item in metrics:
            with self.subTest(metric=item['label']):
                self.assertContains(response,item['label'])
                query=parse_qs(urlsplit(item['url']).query)
                self.assertEqual(query.get('project'),[str(self.project.pk)])
        self.assertEqual(parse_qs(urlsplit(metrics[0]['url']).query).get('work'),None)
        self.assertEqual(parse_qs(urlsplit(metrics[1]['url']).query).get('work'),['pending'])
        self.assertEqual(parse_qs(urlsplit(metrics[2]['url']).query).get('work'),['returned'])
        self.assertNotContains(response,'Accessible checklists')
        self.assertNotContains(response,'My saved checklists')
        self.assertNotContains(response,'Evidence needs a decision')
        self.assertNotContains(response,'Export filtered CSV')

    def test_cards_open_existing_task_lists_without_duplicates_or_scope_leaks(self):
        response=self.client.get(reverse('governance_home'))
        for key,expected in [('assigned',{'HOME-DRAFT','HOME-RETURNED','HOME-SUBMITTED','HOME-UNLINKED-PENDING'}),
                             ('pending',{'HOME-DRAFT','HOME-UNLINKED-PENDING'}),
                             ('returned',{'HOME-RETURNED'})]:
            item=next(row for row in response.context['engineer_home_metrics'] if row['key']==key)
            page=self.client.get(item['url'])
            self.assertEqual(page.status_code,200)
            self.assertEqual({row['task_site'] for row in page.context['page_obj']},expected)
            self.assertNotContains(page,'HOME-FOREIGN')
