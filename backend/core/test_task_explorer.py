"""Pagination and mixed stored task data remain read-only."""
from django.contrib.auth.models import User
from django.test import TestCase,override_settings
from django.urls import reverse
from .models import Project,Checklist,Profile,WorkAssignment

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False)
class TaskExplorerTests(TestCase):
    def setUp(self):
        self.project=Project.objects.create(name='Synthetic task explorer project')
        self.engineer=User.objects.create_user('explorer_engineer')
        self.engineer.profile.role=Profile.Roles.ENGINEER
        self.engineer.profile.project=self.project
        self.engineer.profile.save()
        self.client.force_login(self.engineer)
    def test_database_pagination_and_unlinked_assignment_are_visible(self):
        Checklist.objects.bulk_create([Checklist(project=self.project,user=self.engineer,site_id=f'SYNTHETIC-{i:03}',schema_snapshot={'sections':[]}) for i in range(27)])
        work=WorkAssignment.objects.create(project=self.project,assigned_to=self.engineer,assigned_by=self.engineer,site_id='SYNTHETIC-WORK',latitude=1,longitude=1,description='Actual stored assignment')
        response=self.client.get(reverse('task_explorer'),{'project':'all'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['total'],28)
        self.assertEqual(len(response.context['page_obj']),25)
        response=self.client.get(reverse('task_explorer'),{'q':f'A{work.pk}'})
        self.assertEqual(response.context['total'],1)
        self.assertContains(response,'Assignment awaiting checklist')
        self.assertEqual(WorkAssignment.objects.get(pk=work.pk).checklist_id,None)
    def test_selected_export_stays_within_engineer_scope(self):
        own=Checklist.objects.create(project=self.project,user=self.engineer,site_id='=SYNTHETIC',schema_snapshot={'sections':[]})
        other=User.objects.create_user('explorer_foreign_engineer')
        foreign=Checklist.objects.create(project=self.project,user=other,site_id='FOREIGN-PRIVATE',schema_snapshot={'sections':[]})
        response=self.client.get(reverse('task_explorer'),{'export':'csv','selected':f'C{own.pk},C{foreign.pk}'})
        self.assertEqual(response.status_code,200)
        self.assertIn("'=SYNTHETIC",response.content.decode())
        self.assertNotIn('FOREIGN-PRIVATE',response.content.decode())
        self.assertEqual(self.client.get(reverse('task_explorer'),{'export':'csv','selected':'C1);DROP'}).status_code,400)
