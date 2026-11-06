"""Company overview behaviour; synthetic records and isolated test storage only."""
import hashlib
import json
import os
import statistics
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .models import (
    Checklist, ClientOrganization, Company, GovernanceAudit, IndustryCatalog,
    PhotoEvidence, PhotoPlacement, Profile, Project, ProjectMembership,
    ReviewRoute, WorkAssignment,
)


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False, NOTIFICATION_EMAIL_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AdminDashboardTests(TestCase):
    def setUp(self):
        self.industry=IndustryCatalog.objects.get(code='telecom')
        self.company=Company.objects.create(name='Overview fixture company')
        self.foreign_company=Company.objects.create(name='Outside overview company')
        self.admin=self.person('overview-admin',Profile.Roles.ADMIN)
        self.other_admin=self.person('overview-other-admin',Profile.Roles.ADMIN)
        self.foreign_admin=self.person('overview-foreign-admin',Profile.Roles.ADMIN,company=self.foreign_company)
        self.p1=self.project('Overview project one',self.admin)
        self.p2=self.project('Overview project two',self.admin)
        self.hidden=self.project('Other owner private project',self.other_admin)
        self.foreign=self.project('Foreign company private project',self.foreign_admin,company=self.foreign_company)
        self.engineer=self.person('overview-engineer',Profile.Roles.ENGINEER,self.p1)
        self.grant(self.engineer,self.p2)
        self.lead=self.person('overview-lead',Profile.Roles.TEAM_LEAD,self.p1)
        self.qa=self.person('overview-quality',Profile.Roles.QUALITY_ENGINEER,self.p1)
        self.expired=self.person('overview-expired',Profile.Roles.ENGINEER,self.p2)
        ProjectMembership.objects.filter(user=self.expired).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.locked=self.person('overview-locked',Profile.Roles.ENGINEER,self.p1)
        self.locked.profile.is_locked=True;self.locked.profile.save()
        self.inactive=self.person('overview-inactive',Profile.Roles.ENGINEER,self.p1)
        self.inactive.is_active=False;self.inactive.save()
        self.client_org=ClientOrganization.objects.create(name='Overview client',company=self.company,
            industry=self.industry,created_by=self.admin)
        self.unassigned_client=ClientOrganization.objects.create(name='Overview unassigned client',company=self.company,
            industry=self.industry,created_by=self.admin)
        ClientOrganization.objects.create(name='Foreign client',company=self.foreign_company,
            industry=self.industry,created_by=self.foreign_admin)
        self.p1.client_organization=self.client_org;self.p1.save()
        self.c1=self.checklist(self.p1,'OV-S1',Checklist.Status.SUBMITTED,'quality_engineer')
        self.c2=self.checklist(self.p1,'OV-S1',Checklist.Status.REVIEW,'team_lead')
        self.c3=self.checklist(self.p2,'OV-S1',Checklist.Status.FINAL,'client')
        self.historical=self.checklist(self.p1,'OV-S3',Checklist.Status.REVIEW)
        self.work(self.p1,'OV-S1',checklist=self.c1)
        self.pending=self.work(self.p1,'OV-S2')
        self.photo1=self.photo(self.c1,'one')
        self.photo(self.c2,'two');self.photo(self.c3,'three')
        for field in ('first','second'):
            PhotoPlacement.objects.create(photo=self.photo1,field_id=field,section_id='general',
                status='confirmed',schema_digest='f'*64)
        hidden_check=self.checklist(self.hidden,'HIDDEN',Checklist.Status.REVIEW,'quality_engineer')
        foreign_check=self.checklist(self.foreign,'FOREIGN',Checklist.Status.REVIEW,'client')
        self.photo(hidden_check,'hidden');self.photo(foreign_check,'foreign')
        GovernanceAudit.objects.create(actor=self.admin,actor_name=self.admin.username,
            action='project_created',project=self.p1,details={'secret':'MUST-NOT-BE-RENDERED'})
        GovernanceAudit.objects.create(actor=self.foreign_admin,actor_name=self.foreign_admin.username,
            action='foreign_private_event',project=self.foreign,details={})
        self.client.force_login(self.admin)

    def grant(self,user,project):
        return ProjectMembership.objects.get_or_create(user=user,project=project,
            defaults={'is_active':True,'granted_by':self.admin if hasattr(self,'admin') else user})[0]

    def person(self,name,role,project=None,company=None):
        user=User.objects.create_user(name,email=name+'@example.test',password='Fixture-overview-294!')
        user.profile.role=role;user.profile.company=company or self.company
        user.profile.project=project
        if role==Profile.Roles.ADMIN:user.profile.admin_industry=self.industry
        user.profile.save()
        if project:self.grant(user,project)
        return user

    def project(self,name,admin,company=None):
        project=Project.objects.create(name=name,company=company or self.company,
            administrator=admin,industry=self.industry.code)
        self.grant(admin,project)
        return project

    def checklist(self,project,site,status,stage=None):
        checklist=Checklist.objects.create(user=self.engineer,project=project,site_id=site,status=status)
        if stage:ReviewRoute.objects.create(checklist=checklist,layer_count=4,stage=stage)
        return checklist

    def work(self,project,site,checklist=None):
        return WorkAssignment.objects.create(project=project,site_id=site,latitude=0,longitude=0,
            assigned_to=self.engineer,assigned_by=self.admin,description='Synthetic work',checklist=checklist)

    def photo(self,checklist,key):
        return PhotoEvidence.objects.create(checklist=checklist,uploaded_by=self.engineer,
            filename=key+'.jpg',sha256=hashlib.sha256(key.encode()).hexdigest(),
            original='synthetic/'+key+'.jpg',preview='synthetic/'+key+'-preview.jpg',
            analysis_metadata={'large_private_payload':'x'*4096})

    def dashboard(self,query=None):
        response=self.client.get(reverse('governance_home'),query or {})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['active_view'],'dashboard')
        self.assertIn('admin_dashboard',response.context)
        return response,response.context['admin_dashboard']

    def test_admin_home_uses_real_summary_without_linked_work_or_photo_link_double_count(self):
        response,data=self.dashboard()
        self.assertEqual(data['summary'],{'sites':4,'photos':3,'activities':5,'projects':2,'clients':2,'people':4})
        self.assertEqual(data['company_name'],self.company.name)
        self.assertNotContains(response,'MUST-NOT-BE-RENDERED')
        self.assertNotContains(response,'Foreign company private project')
        self.assertNotContains(response,'Other owner private project')
        self.assertTrue({'private','no-store'}.issubset(
            {part.strip() for part in response['Cache-Control'].split(',')}))

    def test_project_scope_search_and_pagination_preserve_permitted_context(self):
        _,data=self.dashboard({'view':'dashboard','project':self.p2.pk,'industry':'telecom','admin_project_q':'two'})
        self.assertEqual(data['summary'],{'sites':1,'photos':1,'activities':1,'projects':1,'clients':0,'people':2})
        self.assertEqual([row['id'] for row in data['projects']],[self.p2.pk])
        self.assertEqual(data['search'],'two')
        _,empty=self.dashboard({'view':'dashboard','admin_project_q':'no matching project'})
        self.assertEqual(empty['projects'],[])
        self.assertEqual(empty['summary']['projects'],2)
        for project in (self.hidden,self.foreign):
            self.assertEqual(self.client.get(reverse('governance_home'),{'view':'dashboard','project':project.pk}).status_code,404)

    def test_stage_counts_are_authoritative_and_unknown_legacy_stage_is_explicit(self):
        _,data=self.dashboard()
        self.assertEqual(data['review_counts'],{'quality_engineer':1,'team_lead':1,'client':1,'unknown':1})
        by_id={row['id']:row for row in data['projects']}
        self.assertEqual(by_id[self.p1.pk]['activity_count'],4)
        self.assertEqual(by_id[self.p1.pk]['photo_count'],2)
        self.assertEqual(by_id[self.p1.pk]['site_count'],3)
        self.assertEqual(by_id[self.p1.pk]['review_count'],3)

    def test_scoped_people_are_distinct_and_expired_locked_inactive_users_are_excluded(self):
        _,data=self.dashboard()
        by_role={row['role']:row['count'] for row in data['people_by_role']}
        self.assertEqual(by_role[Profile.Roles.ENGINEER],1)
        self.assertEqual(sum(by_role.values()),4)

    def test_other_roles_cannot_request_admin_dashboard_and_keep_their_existing_home(self):
        for actor in (self.engineer,self.lead,self.qa):
            self.client.force_login(actor)
            self.assertEqual(self.client.get(reverse('governance_home'),{'view':'dashboard'}).status_code,404)
        self.client.force_login(self.engineer)
        response=self.client.get(reverse('governance_home'))
        self.assertEqual(response.context['active_view'],'my_work')
        self.client.force_login(self.qa)
        self.assertRedirects(self.client.get(reverse('governance_home')),reverse('task_explorer'),fetch_redirect_response=False)

    def test_dashboard_forms_have_unique_labels_and_preserve_errors(self):
        _,data=self.dashboard()
        response=self.client.post(reverse('governance_projects'),{'return_view':'dashboard','name':'','review_layers':3,
            'dashboard_project':self.p1.pk,'dashboard_industry':'telecom'})
        self.assertEqual(response.status_code,400)
        self.assertEqual(response.context['active_view'],'dashboard')
        self.assertEqual(response.context['admin_dashboard_open_dialog'],'project')
        self.assertTrue(response.context['project_form'].is_bound)
        self.assertEqual(response.context['selected_project_id'],str(self.p1.pk))
        ids=[response.context[key]['name' if key!='invite_form' else 'email'].id_for_label
            for key in ('project_form','clientorg_form','invite_form')]
        self.assertEqual(len(ids),len(set(ids)))

    def test_client_and_invitation_actions_return_to_dashboard_with_existing_permissions(self):
        response=self.client.post(reverse('governance_company'),{'return_view':'dashboard','name':'New overview client',
            'dashboard_project':self.p1.pk,'dashboard_industry':'telecom'})
        self.assertEqual(response.status_code,302)
        query=parse_qs(urlsplit(response.url).query)
        self.assertEqual(query.get('view'),['dashboard'])
        self.assertEqual(query.get('project'),[str(self.p1.pk)])
        response=self.client.post(reverse('governance_invite'),{'return_view':'dashboard','project':self.p1.pk,
            'email':'new-overview@example.test','role':Profile.Roles.ENGINEER})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['active_view'],'dashboard')
        self.assertEqual(response.context['admin_dashboard_open_dialog'],'invite')
        self.assertTrue(response.context['invite_url'])

    def test_external_return_values_never_redirect_outside_application_or_expand_scope(self):
        response=self.client.post(reverse('governance_company'),{'return_view':'https://evil.example.test/',
            'name':'Safe return client'})
        self.assertEqual(response.status_code,302)
        self.assertFalse(urlsplit(response.url).netloc)
        response=self.client.post(reverse('governance_projects'),{'return_view':'dashboard','name':'','review_layers':3,
            'dashboard_project':self.foreign.pk,'dashboard_industry':'telecom'})
        self.assertEqual(response.status_code,400)
        self.assertEqual(response.context['admin_dashboard']['summary']['projects'],2)

    def test_dashboard_aggregates_do_not_select_photo_analysis_or_grow_per_project(self):
        from .admin_dashboard import build_admin_dashboard
        from django.test import RequestFactory
        request=RequestFactory().get('/governance/',{'view':'dashboard'});request.user=self.admin
        with CaptureQueriesContext(connection) as before:
            build_admin_dashboard(request,Project.objects.filter(pk__in=[self.p1.pk,self.p2.pk]))
        for index in range(28):self.project('Scale overview '+str(index),self.admin)
        with CaptureQueriesContext(connection) as after:
            data=build_admin_dashboard(request,Project.objects.filter(administrator=self.admin))
        self.assertEqual(data['summary']['projects'],30)
        self.assertLessEqual(len(data['projects']),25)
        self.assertLessEqual(len(after),len(before)+2)
        for field in ('analysis_metadata','snapshot','answer_data','quality_approval','review_history'):
            self.assertFalse(any('"'+field+'"' in row['sql'] for row in after.captured_queries),field)
        self.assertTrue(data['projects_pagination']['next_url'])
        if os.environ.get('IFIELD_ADMIN_DASHBOARD_MEASURE')=='after':
            path=Path(__file__).resolve().parents[2]/'.local/admin-dashboard-implementation-20261106/backend-query-scaling.json'
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps({'projects_before':2,'projects_after':30,'queries_before':len(before),
                'queries_after':len(after),'visible_project_rows':len(data['projects']),
                'full_evidence_or_revision_json_selected':False},indent=2)+'\n',encoding='utf-8')

    def test_helper_cannot_broaden_a_foreign_queryset_or_serve_non_admin(self):
        from .admin_dashboard import build_admin_dashboard
        from django.core.exceptions import PermissionDenied
        from django.test import RequestFactory
        request=RequestFactory().get('/governance/');request.user=self.admin
        data=build_admin_dashboard(request,Project.objects.filter(pk__in=[self.hidden.pk,self.foreign.pk]))
        self.assertEqual(data['summary']['projects'],0)
        self.assertEqual(data['summary']['photos'],0)
        self.assertEqual(data['summary']['activities'],0)
        request.user=self.engineer
        with self.assertRaises(PermissionDenied):
            build_admin_dashboard(request,Project.objects.all())

    def test_blank_site_identity_remains_an_activity_without_inventing_a_site(self):
        self.checklist(self.p1,'   ',Checklist.Status.DRAFT)
        _,data=self.dashboard()
        self.assertEqual(data['summary']['sites'],4)
        self.assertEqual(data['summary']['activities'],6)

    def test_immutable_revision_decisions_control_unrouted_independent_stage(self):
        from .admin_dashboard import _review_counts
        from .models import ChecklistReviewPolicy,SubmissionRevision,RevisionDecision
        checklist=Checklist.objects.create(user=self.engineer,project=self.p1,site_id='INDEPENDENT',
            governance_mode=Checklist.GovernanceMode.INDEPENDENT,status=Checklist.Status.SUBMITTED)
        revision=SubmissionRevision.objects.create(checklist=checklist,number=1,workflow_version=2,
            digest='a'*64,submitted_by=self.engineer,l2_reviewer=self.qa,l3_approver=self.lead)
        ChecklistReviewPolicy.objects.create(checklist=checklist,workflow_version=2,current_revision=revision,
            l2_reviewer=self.qa,l3_approver=self.lead,configured_by=self.admin,reason='Synthetic fixture')
        query=Checklist.objects.filter(pk=checklist.pk)
        self.assertEqual(_review_counts(query)[0],{'quality_engineer':1,'team_lead':0,'client':0,'unknown':0})
        RevisionDecision.objects.create(revision=revision,action='validate',level='L2',actor=self.qa)
        self.assertEqual(_review_counts(query)[0],{'quality_engineer':0,'team_lead':1,'client':0,'unknown':0})
        RevisionDecision.objects.create(revision=revision,action='return',level='L3',actor=self.lead)
        self.assertEqual(_review_counts(query)[0],{'quality_engineer':0,'team_lead':0,'client':0,'unknown':0})

    def test_project_create_from_dashboard_saves_real_bound_project_and_returns_to_it(self):
        response=self.client.post(reverse('governance_projects'),{'return_view':'dashboard',
            'name':'Created from overview','review_layers':3,'dashboard_project':self.p1.pk})
        self.assertEqual(response.status_code,302)
        created=Project.objects.get(name='Created from overview')
        self.assertEqual((created.company_id,created.administrator_id),(self.company.pk,self.admin.pk))
        self.assertEqual(created.review_layers,3)
        self.assertTrue(ProjectMembership.objects.filter(user=self.admin,project=created,is_active=True).exists())
        self.assertEqual(parse_qs(urlsplit(response.url).query).get('view'),['dashboard'])
        self.assertEqual(parse_qs(urlsplit(response.url).query).get('project'),[str(created.pk)])

    def test_representative_request_measurement(self):
        # Same saved-record fixture is measured before/after; not a throughput claim.
        for index in range(36):self.checklist(self.p1 if index%2 else self.p2,'BENCH-'+str(index),Checklist.Status.DRAFT)
        photos=[PhotoEvidence(checklist=self.c1,uploaded_by=self.engineer,filename='bench-'+str(i)+'.jpg',
            sha256=hashlib.sha256(('bench'+str(i)).encode()).hexdigest(),original='synthetic/bench.jpg',
            preview='synthetic/bench-preview.jpg',analysis_metadata={'notes':'x'*4096}) for i in range(460)]
        PhotoEvidence.objects.bulk_create(photos)
        with CaptureQueriesContext(connection) as first_queries:
            first_start=time.perf_counter()
            first_response=self.client.get(reverse('governance_home'))
            first_elapsed=time.perf_counter()-first_start
        first_sample={'milliseconds':round(first_elapsed*1000,2),'queries':len(first_queries),
            'response_bytes':len(first_response.content)}
        samples=[]
        for _ in range(3):
            with CaptureQueriesContext(connection) as queries:
                start=time.perf_counter();response=self.client.get(reverse('governance_home'));elapsed=time.perf_counter()-start
            self.assertEqual(response.status_code,200)
            samples.append({'milliseconds':round(elapsed*1000,2),'queries':len(queries),'response_bytes':len(response.content)})
        phase=os.environ.get('IFIELD_ADMIN_DASHBOARD_MEASURE')
        if phase=='notice':
            notice=first_response.context['release_notice']
            acknowledgement=self.client.post(reverse('release_notice_acknowledge'),json.dumps({
                'release_id':notice['release_id'],'session_nonce':notice['cache_nonce'],
                'suppress_current':True}),content_type='application/json')
            self.assertEqual(acknowledgement.status_code,200)
            acknowledged=[]
            for _ in range(3):
                with CaptureQueriesContext(connection) as queries:
                    start=time.perf_counter();response=self.client.get(reverse('governance_home'));elapsed=time.perf_counter()-start
                self.assertEqual(response.status_code,200)
                self.assertIsNone(response.context['release_notice'])
                acknowledged.append({'milliseconds':round(elapsed*1000,2),'queries':len(queries),
                    'response_bytes':len(response.content)})
            root=Path(__file__).resolve().parents[2]/'.local/admin-dashboard-implementation-20261106'
            root.mkdir(parents=True,exist_ok=True)
            (root/'backend-performance-with-notices.json').write_text(json.dumps({
                'phase':'final_source_with_release_notices',
                'fixture':'2 authorized projects;40 checklists;1 unlinked assignment;463 authorized photos',
                'first_unseen_release':first_sample,'warm_unseen_release':samples,
                'warm_unseen_median_milliseconds':statistics.median(row['milliseconds'] for row in samples),
                'acknowledged_same_session':acknowledged,
                'acknowledged_median_milliseconds':statistics.median(row['milliseconds'] for row in acknowledged),
                'baseline_and_admin_only_measurements_preserved':True},indent=2)+'\n',encoding='utf-8')
        if phase in {'before','after'}:
            root=Path(__file__).resolve().parents[2]/'.local/admin-dashboard-implementation-20261106'
            root.mkdir(parents=True,exist_ok=True)
            (root/('backend-performance-'+phase+'.json')).write_text(json.dumps({'phase':phase,
                'fixture':'2 authorized projects;40 checklists;1 unlinked assignment;463 authorized photos',
                'samples':samples,'median_milliseconds':statistics.median(row['milliseconds'] for row in samples)},indent=2)+'\n',encoding='utf-8')
