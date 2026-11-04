"""List-page rendering keeps complete scopes without per-project/row reads."""
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase,SimpleTestCase,RequestFactory,override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Company,Project,Profile,ProjectMembership,Checklist,IndustryCatalog
from .review_route_models import ReviewRoute
from .revision_models import ChecklistReviewPolicy


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class WorkspaceContextPerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company=Company.objects.create(name='Synthetic context performance company')
        cls.project=Project.objects.create(name='Synthetic context primary project',company=cls.company)
        cls.admin=cls.person('context_admin',Profile.Roles.ADMIN)
        cls.engineer=cls.person('context_engineer',Profile.Roles.ENGINEER)
        cls.qa=cls.person('context_qa',Profile.Roles.QUALITY_ENGINEER)
        cls.lead=cls.person('context_lead',Profile.Roles.TEAM_LEAD)
        cls.owner=User.objects.create_user('context_owner',is_superuser=True)
        Profile.objects.filter(user=cls.owner).update(role=Profile.Roles.SUPER_ADMIN)

    @classmethod
    def person(cls,name,role):
        user=User.objects.create_user(name)
        profile=user.profile;profile.role=role;profile.company=cls.company;profile.project=cls.project;profile.save()
        ProjectMembership.objects.create(user=user,project=cls.project,is_primary=True)
        return user

    def test_owner_page_keeps_all_thousand_projects_without_family_n_plus_one(self):
        Project.objects.bulk_create([Project(name=f'Synthetic complete selector {i:04}',company=self.company)
                                    for i in range(999)])
        self.client.force_login(self.owner)
        with CaptureQueriesContext(connection) as queries:
            response=self.client.get(reverse('governance_home'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['shell_projects']),1000)
        self.assertEqual(len(response.context['invite_form'].fields['project'].queryset),1000)
        self.assertEqual(response.context['shell_modules'],[])
        self.assertLessEqual(len(queries),60,'The shared shell must not query a family once per project.')

    def test_shell_family_batch_preserves_unknown_and_custom_family_scope(self):
        from .industry_service import industry_family
        from .local_ai import local_context
        catalog=IndustryCatalog.objects.create(code='context-construction',name='Synthetic context building',workflow_family='construction')
        own=Project.objects.create(name='Synthetic context custom family',company=self.company,industry=catalog.code)
        unknown=Project.objects.create(name='Synthetic context unknown family',company=self.company,industry='missing-context')
        ProjectMembership.objects.bulk_create([ProjectMembership(user=self.engineer,project=project) for project in [own,unknown]])
        foreign_company=Company.objects.create(name='Synthetic foreign context company')
        foreign=Project.objects.create(name='Synthetic foreign context project',company=foreign_company)
        ProjectMembership.objects.create(user=self.engineer,project=foreign)
        request=RequestFactory().get('/governance/');request.user=self.engineer
        with CaptureQueriesContext(connection) as queries:
            context=local_context(request)
        self.assertEqual({project.pk for project in context['shell_projects']},{self.project.pk,own.pk,unknown.pk})
        expected={industry_family(project) for project in context['shell_projects']}
        self.assertEqual({module['industry'] for module in context['shell_modules']},expected-{'other'})
        family_reads=[query for query in queries if 'FROM "core_industrycatalog"' in query['sql'] and 'workflow_family' in query['sql']]
        self.assertLessEqual(len(family_reads),1,'Repeated codes and unknown families need one bounded catalogue read.')

    def test_admin_home_renders_loaded_workflow_snapshots_without_row_queries(self):
        tasks=Checklist.objects.bulk_create([
            Checklist(project=self.project,user=self.engineer,site_id=f'SYN-CONTEXT-{index:03}',
                governance_mode='independent',schema_snapshot={'sections':[]}) for index in range(25)])
        ChecklistReviewPolicy.objects.bulk_create([
            ChecklistReviewPolicy(checklist=task,workflow_version=2,l2_reviewer=self.qa,l3_approver=self.lead,
                customer_required=False,configured_by=self.admin,reason='Synthetic display policy') for task in tasks])
        ReviewRoute.objects.bulk_create([
            ReviewRoute(checklist=task,layer_count=3,stage='engineer',
                reviewers={'engineer':self.engineer.pk,'quality_engineer':self.qa.pk,'team_lead':self.lead.pk})
            for task in tasks])
        self.client.force_login(self.admin)
        with CaptureQueriesContext(connection) as queries:
            response=self.client.get(reverse('governance_home'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['surveys']),25)
        self.assertContains(response,'Awaiting Engineer')
        self.assertLessEqual(len(queries),50,'Each displayed row must reuse its loaded route/policy for labels.')


class WorkspaceDisplayTagUnitTests(SimpleTestCase):
    def test_explicit_display_values_do_not_eagerly_evaluate_fresh_fallbacks(self):
        from .templatetags.task_workflow import task_display_label,task_display_stage,task_display_version
        class LoadedRow:
            display_workflow_label='Awaiting Engineer'
            display_workflow_stage='engineer'
            display_workflow_version=2
            @property
            def workflow_label(self):raise AssertionError('Fresh fallback was evaluated eagerly')
            @property
            def workflow_stage(self):raise AssertionError('Fresh fallback was evaluated eagerly')
            @property
            def review_policy(self):raise AssertionError('Loaded version was ignored')
        row=LoadedRow()
        self.assertEqual(task_display_label(row),'Awaiting Engineer')
        self.assertEqual(task_display_stage(row),'engineer')
        self.assertEqual(task_display_version(row),2)
        self.assertEqual(task_display_label(None,'Pending'),'Pending')

    def test_detail_without_explicit_display_snapshot_uses_fresh_properties(self):
        from .templatetags.task_workflow import task_display_label,task_display_stage,task_display_version
        class CurrentRow:
            workflow_label='Awaiting Team Lead'
            workflow_stage='team_lead'
            review_policy=None
        self.assertEqual(task_display_label(CurrentRow()),'Awaiting Team Lead')
        self.assertEqual(task_display_stage(CurrentRow()),'team_lead')
        self.assertIsNone(task_display_version(CurrentRow()))
