"""Workspace summary totals describe the authorized scope, not its visible page."""
import re

from django.contrib.auth.models import User
from django.test import TestCase,override_settings
from django.urls import reverse

from .models import Company,Project,Profile,ProjectMembership,Checklist,WorkAssignment,IndustryCatalog


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class WorkspaceScopedTotalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company=Company.objects.create(name='Synthetic summary company')
        cls.admin=User.objects.create_user('summary_admin')
        profile=cls.admin.profile;profile.role=Profile.Roles.ADMIN;profile.company=cls.company
        profile.admin_industry=IndustryCatalog.objects.get(code='telecom');profile.save()
        cls.engineer=User.objects.create_user('summary_engineer')
        profile=cls.engineer.profile;profile.role=Profile.Roles.ENGINEER;profile.company=cls.company;profile.save()
        cls.projects=[Project.objects.create(name=f'Synthetic summary project {index}',company=cls.company,
            administrator=cls.admin) for index in range(3)]
        ProjectMembership.objects.bulk_create([ProjectMembership(user=user,project=project)
            for user in [cls.admin,cls.engineer] for project in cls.projects])
        Checklist.objects.bulk_create([Checklist(project=project,user=cls.engineer,
            site_id=f'SYN-SUMMARY-C-{project.pk}-{index}',schema_snapshot={'sections':[]})
            for project in cls.projects for index in range(25)])
        WorkAssignment.objects.bulk_create([WorkAssignment(project=project,assigned_to=cls.engineer,assigned_by=cls.admin,
            site_id=f'SYN-SUMMARY-A-{project.pk}-{index}',latitude=1,longitude=1,description='Synthetic summary assignment')
            for project in cls.projects for index in range(14)])

    def request(self,actor=None,**query):
        self.client.force_login(actor or self.admin)
        response=self.client.get(reverse('governance_home'),query)
        self.assertEqual(response.status_code,200)
        return response

    def totals(self,response):
        return {label.strip():int(value) for value,label in re.findall(
            r'<div class="gw-stat">\s*<strong>\s*(\d+)\s*</strong>\s*<span>([^<]+)</span>',
            response.content.decode())}

    def test_first_and_later_pages_show_full_scope_but_keep_rows_paged(self):
        expected={'Site assignments':42,'Accessible checklists':75,'Projects in this view':3}
        first=self.request()
        self.assertEqual(self.totals(first),expected)
        self.assertEqual(len(first.context['assignments']),25)
        self.assertEqual(len(first.context['surveys']),25)
        later=self.request(work_page=2,sites_page=2)
        self.assertEqual(self.totals(later),expected)
        self.assertEqual(len(later.context['assignments']),17)
        self.assertEqual(len(later.context['surveys']),25)

    def test_selected_project_and_empty_project_totals_stay_scoped(self):
        selected=self.request(project=self.projects[0].pk)
        self.assertEqual(self.totals(selected),{'Site assignments':14,'Accessible checklists':25,'Projects in this view':1})
        empty=Project.objects.create(name='Synthetic empty summary project',company=self.company,administrator=self.admin)
        ProjectMembership.objects.create(user=self.admin,project=empty)
        response=self.request(project=empty.pk)
        self.assertEqual(self.totals(response),{'Site assignments':0,'Accessible checklists':0,'Projects in this view':1})

    def test_foreign_company_injected_grant_cannot_inflate_totals(self):
        company=Company.objects.create(name='Synthetic foreign summary company')
        project=Project.objects.create(name='Synthetic private foreign project',company=company)
        ProjectMembership.objects.create(user=self.admin,project=project)
        Checklist.objects.create(project=project,user=self.engineer,site_id='PRIVATE-FOREIGN-SUMMARY')
        WorkAssignment.objects.create(project=project,assigned_to=self.engineer,assigned_by=self.admin,
            site_id='PRIVATE-FOREIGN-ASSIGNMENT',latitude=1,longitude=1,description='Foreign company fixture')
        response=self.request()
        self.assertEqual(self.totals(response),{'Site assignments':42,'Accessible checklists':75,'Projects in this view':3})
        self.assertNotContains(response,'PRIVATE-FOREIGN')

    def test_project_count_is_not_capped_on_the_paged_projects_view(self):
        additional=[Project(name=f'Synthetic extra summary project {index}',company=self.company,administrator=self.admin)
                    for index in range(28)]
        Project.objects.bulk_create(additional)
        ProjectMembership.objects.bulk_create([ProjectMembership(user=self.admin,project=project) for project in additional])
        response=self.request(view='projects',project_page=2)
        self.assertEqual(self.totals(response),{'Site assignments':42,'Accessible checklists':75,'Projects in this view':31})
        self.assertEqual(len(response.context['projects']),6)

    def test_industry_filter_limits_all_three_summary_counts(self):
        legacy=User.objects.create_user('summary_legacy_admin')
        profile=legacy.profile;profile.role=Profile.Roles.ADMIN;profile.company=self.company;profile.save()
        telecom=Project.objects.create(name='Synthetic legacy summary telecom',company=self.company,administrator=legacy)
        construction=Project.objects.create(name='Synthetic legacy summary construction',company=self.company,
            industry='construction',administrator=legacy)
        ProjectMembership.objects.bulk_create([ProjectMembership(user=legacy,project=project) for project in [telecom,construction]])
        Checklist.objects.create(project=telecom,user=self.engineer,site_id='SYN-LEGACY-SUM-TELECOM')
        Checklist.objects.bulk_create([Checklist(project=construction,user=self.engineer,site_id=f'SYN-LEGACY-SUM-CON-{i}') for i in range(3)])
        response=self.request(legacy,industry='construction')
        self.assertEqual(self.totals(response),{'Site assignments':0,'Accessible checklists':3,'Projects in this view':1})

    def test_administration_totals_do_not_materialize_hidden_task_collections(self):
        response=self.request(view='administration')
        self.assertEqual(self.totals(response),{'Site assignments':42,'Accessible checklists':75,'Projects in this view':3})
        self.assertIsNone(response.context['surveys']._result_cache)
        self.assertIsNone(response.context['assignments']._result_cache)

    def test_client_counts_visible_final_deliverables_separately_from_pending_review(self):
        from .revision_models import ChecklistReviewPolicy,SubmissionRevision
        from .review_route_models import ReviewRoute,ReviewRouteEvent
        client=User.objects.create_user('summary_client')
        profile=client.profile;profile.role=Profile.Roles.CLIENT;profile.company=self.company;profile.project=self.projects[0];profile.save()
        ProjectMembership.objects.create(user=client,project=self.projects[0])
        reviewers=[]
        for username,role in [('summary_qa',Profile.Roles.QUALITY_ENGINEER),('summary_lead',Profile.Roles.TEAM_LEAD)]:
            reviewer=User.objects.create_user(username)
            profile=reviewer.profile;profile.role=role;profile.company=self.company;profile.project=self.projects[0];profile.save()
            ProjectMembership.objects.create(user=reviewer,project=self.projects[0]);reviewers.append(reviewer)
        qa,lead=reviewers
        Checklist.objects.bulk_create([Checklist(project=self.projects[0],user=self.engineer,
            site_id=f'SYN-SUMMARY-FINAL-{index}',status=Checklist.Status.FINAL) for index in range(33)])
        pending=Checklist.objects.create(project=self.projects[0],user=self.engineer,site_id='SYN-SUMMARY-CLIENT-PENDING',
            status=Checklist.Status.REVIEW,governance_mode='independent')
        revision=SubmissionRevision.objects.create(checklist=pending,number=1,workflow_version=2,snapshot={},digest='a'*64,
            submitted_by=self.engineer,l2_reviewer=qa,l3_approver=lead)
        ChecklistReviewPolicy.objects.create(checklist=pending,workflow_version=2,l2_reviewer=qa,l3_approver=lead,
            customer_reviewer=client,customer_required=True,current_revision=revision,configured_by=self.admin,reason='Synthetic count policy')
        route=ReviewRoute.objects.create(checklist=pending,layer_count=4,stage='client',revision=revision,
            reviewers={'engineer':self.engineer.pk,'quality_engineer':qa.pk,'team_lead':lead.pk,'client':client.pk})
        ReviewRouteEvent.objects.create(route=route,sequence=1,revision=revision,revision_digest=revision.digest,
            from_stage='team_lead',to_stage='client',action='approve',actor=lead)
        response=self.request(client,project=self.projects[0].pk)
        self.assertEqual(self.totals(response),{'Final deliverables':33,'Accessible checklists':34,'Projects in this view':1})
