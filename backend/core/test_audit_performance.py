"""Regression budgets for real, permission-scoped pages rather than mock querysets."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase,SimpleTestCase,override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .models import Company, IndustryCatalog, Project, Profile, ProjectMembership, Checklist, WorkProfile,WorkAssignment
from .review_route_models import ReviewRoute
from types import SimpleNamespace


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AuditPerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name='Synthetic performance company')
        cls.industry = IndustryCatalog.objects.get(code='telecom')
        cls.project = Project.objects.create(name='Synthetic performance project', company=cls.company)
        cls.admin = cls.person('perf_admin', Profile.Roles.ADMIN)
        cls.client_user = cls.person('perf_client', Profile.Roles.CLIENT)
        cls.staff = [cls.person(f'perf_staff_{i:03}', Profile.Roles.ENGINEER) for i in range(61)]
        WorkProfile.objects.bulk_create([
            WorkProfile(user=user, display_name=f'Synthetic Engineer {i:03}', published=True)
            for i, user in enumerate(cls.staff)
        ])

    @classmethod
    def person(cls, name, role):
        user = User.objects.create_user(name)
        profile = user.profile
        profile.company = cls.company
        profile.project = cls.project
        profile.role = role
        if role == Profile.Roles.ADMIN:
            profile.admin_industry = cls.industry
        profile.save()
        ProjectMembership.objects.create(user=user, project=cls.project, is_active=True, is_primary=True)
        return user

    def test_published_directory_scopes_before_paging_with_bounded_queries(self):
        self.client.force_login(self.client_user)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('work_profile_directory'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].paginator.count, 61)
        self.assertEqual(len(response.context['page_obj']), 24)
        self.assertLessEqual(len(queries), 65, 'A displayed page must not authorize every off-page profile individually.')
        self.assertEqual(
            {row['profile'].user_id for row in response.context['page_obj']},
            {user.pk for user in self.staff[:24]},
        )
        membership = ProjectMembership.objects.get(user=self.staff[0], project=self.project)
        membership.expires_at = timezone.now() - timedelta(seconds=1)
        membership.save()
        refreshed = self.client.get(reverse('work_profile_directory'))
        self.assertEqual(refreshed.context['page_obj'].paginator.count, 60)
        self.assertNotContains(refreshed, 'Synthetic Engineer 000')

    def test_admin_home_avoids_building_offscreen_people_forms(self):
        self.client.force_login(self.admin)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('governance_home'))
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 90, 'The home view must not build all member grants/forms.')
        self.assertEqual(len(response.context['members']), 0)

    def test_admin_roster_paginates_without_losing_reachable_accounts(self):
        self.client.force_login(self.admin)
        with CaptureQueriesContext(connection) as queries:
            first = self.client.get(reverse('governance_home'), {'view': 'administration'})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(len(first.context['members']), 24)
        self.assertEqual(first.context['members_page'].paginator.count, 63)
        self.assertLessEqual(len(queries), 110, 'Only one page of members and batched grants should be materialized.')
        self.assertContains(first, 'aria-label="Team member pages"')
        identities = {user.pk for user in first.context['members']}
        for page in (2, 3):
            response = self.client.get(reverse('governance_home'), {'view': 'administration', 'people_page': page})
            current = {user.pk for user in response.context['members']}
            self.assertFalse(identities & current)
            identities |= current
        self.assertEqual(identities, {self.admin.pk, self.client_user.pk, *(user.pk for user in self.staff)})

    def test_roster_search_can_find_an_account_beyond_the_first_page(self):
        self.client.force_login(self.admin)
        response=self.client.get(reverse('governance_home'),{'view':'administration','people_q':'perf_staff_060'})
        self.assertEqual(response.status_code,200)
        self.assertEqual([member.pk for member in response.context['members']],[self.staff[60].pk])
        self.assertContains(response,'Search all team accounts')

    def test_platform_owner_roster_is_paged_but_project_selector_is_not(self):
        owner=self.person('perf_owner',Profile.Roles.SUPER_ADMIN)
        User.objects.filter(pk=owner.pk).update(is_superuser=True)
        self.client.force_login(owner)
        response=self.client.get(reverse('governance_home'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['members']),24)
        self.assertEqual(response.context['members_page'].paginator.count,63)
        # List pagination must not truncate the authority scope or form choices.
        for number in range(30):Project.objects.create(name=f'Synthetic additional project {number}',company=self.company)
        response=self.client.get(reverse('governance_home'),{'view':'projects','project_page':2})
        self.assertEqual(len(response.context['projects']),6)
        self.assertEqual(len(response.context['scope_projects']),31)
        self.assertContains(response,'Project pages')

    def test_owner_site_register_is_paged_with_all_identifiers_reachable(self):
        owner=self.person('perf_site_owner',Profile.Roles.SUPER_ADMIN)
        User.objects.filter(pk=owner.pk).update(is_superuser=True)
        WorkAssignment.objects.bulk_create([
            WorkAssignment(project=self.project,assigned_to=self.staff[0],assigned_by=self.admin,
                site_id=f'SYN-ADMIN-SITE-{index:03}',latitude=1,longitude=1,description='Synthetic administrative site')
            for index in range(55)])
        self.client.force_login(owner)
        response=self.client.get(reverse('governance_home'),{'view':'sites','project':'all'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['sites']),25)
        self.assertEqual(response.context['sites_page'].paginator.count,55)
        self.assertContains(response,'Administrative site pages')
        identifiers=set(response.context['sites'].values_list('site_id',flat=True))
        for page in (2,3):
            following=self.client.get(reverse('governance_home'),{'view':'sites','project':'all','site_page':page})
            identifiers.update(following.context['sites'].values_list('site_id',flat=True))
        self.assertEqual(identifiers,{f'SYN-ADMIN-SITE-{index:03}' for index in range(55)})

    def test_error_page_pagination_and_search_return_to_the_get_workspace(self):
        owner=self.person('perf_error_owner',Profile.Roles.SUPER_ADMIN)
        User.objects.filter(pk=owner.pk).update(is_superuser=True)
        self.client.force_login(owner)
        error=self.client.post(reverse('governance_invite'),{'email':'invalid','role':Profile.Roles.ADMIN,
            'project':self.project.pk,'admin_industry':self.industry.pk})
        self.assertEqual(error.status_code,400)
        next_url=error.context['members_pagination']['next_url']
        self.assertTrue(next_url.startswith(reverse('governance_home')+'?'),next_url)
        self.assertIn('view=dashboard',next_url)
        self.assertEqual(self.client.get(next_url).status_code,200)
        self.assertContains(error,'action="'+reverse('governance_home')+'"',status_code=400)
        self.assertContains(error,'name="view" value="dashboard"',status_code=400)

    def test_display_snapshot_does_not_replace_fresh_workflow_authority(self):
        from .workflow_service import workflow_stage
        task=Checklist.objects.create(project=self.project,user=self.staff[0],site_id='SYN-DISPLAY-AUTH')
        route=ReviewRoute.objects.create(checklist=task,layer_count=3,reviewers={},stage='engineer')
        loaded=Checklist.objects.select_related('review_route_record').get(pk=task.pk)
        self.assertEqual(loaded.review_route_record.stage,'engineer')
        ReviewRoute.objects.filter(pk=route.pk).update(stage='team_lead')
        self.assertEqual(workflow_stage(loaded),'team_lead')

    def test_task_counters_and_loaded_route_display_have_bounded_queries(self):
        self.client.force_login(self.staff[0])
        tasks = Checklist.objects.bulk_create([
            Checklist(project=self.project, user=self.staff[0], site_id=f'SYN-PERF-{i:03}',
                      schema_snapshot={'sections': []}, status=Checklist.Status.DRAFT)
            for i in range(28)
        ])
        ReviewRoute.objects.bulk_create([
            ReviewRoute(checklist=task, layer_count=3, reviewers={}, stage='engineer') for task in tasks
        ])
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('task_explorer'), {'project': 'all'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total'], 28)
        self.assertEqual(response.context['engineer_task_buckets'][0]['count'], 28)
        self.assertEqual(response.context['engineer_task_buckets'][1]['count'], 28)
        self.assertEqual(len(response.context['page_obj']), 25)
        self.assertTrue(all(row['stage'] == 'Awaiting Engineer' for row in response.context['page_obj']))
        self.assertLessEqual(len(queries), 35, 'Task counts and route labels must not query once per counter or row.')

    def test_recent_project_task_page_avoids_temporary_database_sort(self):
        """Both halves of the actual UNION must use their persisted ordering."""
        from .task_explorer import scopes,filtered_rows
        Checklist.objects.create(project=self.project,user=self.staff[0],site_id='SYN-INDEX-C')
        WorkAssignment.objects.create(project=self.project,assigned_to=self.staff[0],assigned_by=self.admin,
            site_id='SYN-INDEX-A',latitude=1,longitude=1,description='Synthetic index coverage')
        projects,checklists,assignments=scopes(self.admin)
        rows=filtered_rows(checklists,assignments,{'project':self.project,'sort':'updated'})
        plan=rows[:25].explain()
        self.assertNotIn('USE TEMP B-TREE',plan,'A recent project page should not sort all matching task records.')
        self.assertEqual({row['task_site'] for row in rows},{'SYN-INDEX-C','SYN-INDEX-A'})

    def test_aggregate_badges_agree_with_filtered_mixed_model_rows(self):
        from django.db.models import Q
        from .task_explorer import scopes,filtered_rows,scoped_counts
        for index,status in enumerate([Checklist.Status.DRAFT,Checklist.Status.SUBMITTED,Checklist.Status.REJECTED,Checklist.Status.FINAL]):
            Checklist.objects.create(project=self.project,user=self.staff[0],site_id=f'SYN-COUNTS-{index}',status=status,
                workflow_type=Checklist.WorkflowType.TELECOM_INSPECTION if index==2 else Checklist.WorkflowType.TELECOM_SURVEY)
        WorkAssignment.objects.create(project=self.project,assigned_to=self.staff[0],assigned_by=self.admin,
            site_id='SYN-COUNTS-WORK',latitude=1,longitude=1,description='Mixed count fixture')
        projects,checklists,assignments=scopes(self.staff[0])
        conditions={'draft':Q(task_status='DRAFT'),'survey':Q(task_module='telecom_survey'),
                    'unclassified':Q(task_module='')}
        cases=[{}, {'work':'pending'}, {'status':'REJECTED'}, {'status':'SUBMITTED','work':'pending'},
               {'module':'unclassified'}, {'module':'telecom_survey','work':'pending'}, {'q':'COUNTS-2'}]
        for filters in cases:
            with self.subTest(filters=filters):
                rows=list(filtered_rows(checklists,assignments,filters))
                self.assertEqual(scoped_counts(checklists,assignments,filters,conditions),{
                    'total':len(rows),'draft':sum(row['task_status']=='DRAFT' for row in rows),
                    'survey':sum(row['task_module']=='telecom_survey' for row in rows),
                    'unclassified':sum(row['task_module']=='' for row in rows)})

    def test_batched_industry_modules_match_the_existing_family_resolver(self):
        from .industry_service import industry_family
        from .task_explorer import TaskFilters
        unknown=Project.objects.create(name='Synthetic unknown industry project',company=self.company,industry='legacy-unknown')
        custom=IndustryCatalog.objects.create(code='audit-custom',name='Synthetic custom family',workflow_family='construction')
        construction=Project.objects.create(name='Synthetic custom construction project',company=self.company,industry=custom.code)
        for projects in [Project.objects.filter(pk=unknown.pk),Project.objects.filter(pk__in=[self.project.pk,construction.pk,unknown.pk])]:
            form=TaskFilters(projects=projects,checklists=Checklist.objects.none(),assignments=WorkAssignment.objects.none())
            families={industry_family(code) for code in projects.values_list('industry',flat=True)}
            expected=[('', 'All modules'),*[choice for choice in Checklist.WorkflowType.choices if
                choice[0].startswith('telecom') and 'telecom' in families or
                choice[0].startswith('construction') and 'construction' in families],('unclassified','Unclassified assignment')]
            self.assertEqual(form.fields['module'].choices,expected)


class DisplayWorkflowUnitTests(SimpleTestCase):
    def test_loaded_route_labels_are_display_only_and_do_not_query(self):
        from .workflow_service import display_workflow
        for stage,label in [('engineer','Engineer'),('quality_engineer','Quality Engineer'),('team_lead','Team Lead'),('client','Client')]:
            for mode in ['review','clarification']:
                route=SimpleNamespace(stage=stage,mode=mode)
                checklist=SimpleNamespace(_state=SimpleNamespace(fields_cache={'review_route_record':route}))
                with self.subTest(stage=stage,mode=mode):
                    self.assertEqual(display_workflow(checklist),(stage,'Awaiting '+label if mode=='review' else label+' clarification required'))
        closed=SimpleNamespace(_state=SimpleNamespace(fields_cache={'review_route_record':SimpleNamespace(stage='closed',mode='review')}))
        self.assertEqual(display_workflow(closed),('closed','Activity closed'))
