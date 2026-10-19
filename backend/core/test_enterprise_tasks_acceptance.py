"""Independent authorization and real-data contract checks for enterprise task discovery."""
import csv
from io import StringIO
from django.contrib.auth.models import User
from django.test import TestCase,override_settings
from django.urls import reverse
from . import test_role_designs as design_fixtures
from .models import Checklist,Project,Profile,WorkAssignment,ChecklistReviewPolicy

@override_settings(SECRET_KEY='synthetic-enterprise-tasks',ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,LOCAL_AI_ENABLED=True)
class EnterpriseTaskAcceptanceTests(TestCase):
    def setUp(self):
        self.f=design_fixtures.RoleDesignTests();self.f.setUp();self.project=self.f.project;self.users=self.f.users
        self.c=self.f.survey;self.c.site_id='ENTERPRISE-OWN';self.c.save()
        peer=User.objects.create_user('enterprise_peer_engineer');peer.profile.role=Profile.Roles.ENGINEER;peer.profile.project=self.project;peer.profile.save()
        otherq=User.objects.create_user('enterprise_other_quality');otherq.profile.role=Profile.Roles.QUALITY_ENGINEER;otherq.profile.project=self.project;otherq.profile.save()
        self.peer=Checklist.objects.create(user=peer,project=self.project,quality_reviewer=otherq,site_id='ENTERPRISE-PEER',schema_snapshot=self.c.schema_snapshot)
        foreign=Project.objects.create(name='Forbidden foreign project')
        self.foreign=Checklist.objects.create(user=peer,project=foreign,site_id='ENTERPRISE-FOREIGN',schema_snapshot=self.c.schema_snapshot)
        self.final=Checklist.objects.create(user=self.users[Profile.Roles.ENGINEER],project=self.project,quality_reviewer=self.users[Profile.Roles.QUALITY_ENGINEER],site_id='ENTERPRISE-FINAL',status=Checklist.Status.FINAL,schema_snapshot=self.c.schema_snapshot)
        self.url=reverse('governance_tasks')
    def login(self,role):self.client.force_login(self.users[role])
    def test_scopes_match_actual_role_assignments_and_super_has_no_engineering_export(self):
        for role in [Profile.Roles.ADMIN,Profile.Roles.ENGINEER,Profile.Roles.QUALITY_ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.CLIENT]:
            self.login(role);response=self.client.get(self.url)
            self.assertEqual(response.status_code,200);self.assertNotContains(response,'ENTERPRISE-FOREIGN')
            self.assertContains(response,'ENTERPRISE-FINAL')
            if role==Profile.Roles.CLIENT:self.assertNotContains(response,'ENTERPRISE-OWN')
            else:self.assertContains(response,'ENTERPRISE-OWN')
            if role in {Profile.Roles.ENGINEER,Profile.Roles.QUALITY_ENGINEER,Profile.Roles.CLIENT}:self.assertNotContains(response,'ENTERPRISE-PEER')
        self.login(Profile.Roles.SUPER_ADMIN)
        for params in [{},{'export':'csv'}]:self.assertEqual(self.client.get(self.url,params).status_code,403)
    def test_filtered_csv_matches_search_scope_and_escapes_formula_site(self):
        self.login(Profile.Roles.ADMIN)
        self.c.site_id='=SYNTHETIC-FORMULA';self.c.save()
        response=self.client.get(self.url,{'q':'SYNTHETIC-FORMULA','status':Checklist.Status.DRAFT,'export':'csv'})
        self.assertEqual(response.status_code,200)
        rows=list(csv.reader(StringIO(response.content.decode())))
        self.assertEqual(len(rows),2);self.assertEqual(rows[1][0],"'=SYNTHETIC-FORMULA")
        self.assertNotIn('ENTERPRISE-FOREIGN',response.content.decode());self.assertNotIn('ENTERPRISE-PEER',response.content.decode())
        self.assertEqual(response['Cache-Control'],'private, no-store')
    def test_header_all_project_and_invalid_filters_are_safe(self):
        self.login(Profile.Roles.ENGINEER)
        self.assertEqual(self.client.get(self.url,{'project':'all'}).status_code,200)
        for params in [{'project':'99999999'},{'status':'invented'},{'date_from':'2026-10-20','date_to':'2026-10-01'},{'sort':'malicious'},{'assignee':'99999999'}]:
            response=self.client.get(self.url,{**params,'export':'csv'})
            self.assertEqual(response.status_code,400);self.assertNotIn('ENTERPRISE-FOREIGN',response.content.decode())
    def test_client_cannot_filter_personnel_or_access_other_named_independent_deliverable(self):
        named=User.objects.create_user('enterprise_named_client');named.profile.role=Profile.Roles.CLIENT;named.profile.project=self.project;named.profile.save()
        self.final.governance_mode='independent';self.final.save()
        ChecklistReviewPolicy.objects.create(checklist=self.final,workflow_version=2,l2_reviewer=self.users[Profile.Roles.QUALITY_ENGINEER],l3_approver=self.users[Profile.Roles.TEAM_LEAD],customer_reviewer=named,customer_required=True,configured_by=self.users[Profile.Roles.ADMIN],reason='Explicit release')
        self.login(Profile.Roles.CLIENT)
        self.assertNotContains(self.client.get(self.url),'ENTERPRISE-FINAL')
        self.assertEqual(self.client.get(self.url,{'assignee':self.users[Profile.Roles.ENGINEER].pk,'export':'csv'}).status_code,403)
        self.client.force_login(named);response=self.client.get(self.url,{'export':'csv'})
        self.assertEqual(response.status_code,200);self.assertIn('ENTERPRISE-FINAL',response.content.decode())
        self.assertNotIn(self.users[Profile.Roles.ENGINEER].username,response.content.decode())
    def test_unlinked_assignments_are_real_rows_and_list_is_paginated(self):
        engineer=self.users[Profile.Roles.ENGINEER];lead=self.users[Profile.Roles.TEAM_LEAD]
        WorkAssignment.objects.create(project=self.project,assigned_to=engineer,assigned_by=lead,site_id='ENTERPRISE-UNLINKED',latitude=1,longitude=2,description='Synthetic unlinked task')
        self.login(Profile.Roles.ENGINEER)
        response=self.client.get(self.url,{'q':'ENTERPRISE-UNLINKED'})
        self.assertContains(response,'ENTERPRISE-UNLINKED');self.assertEqual(response.context['total'],1)
        for i in range(28):Checklist.objects.create(user=engineer,project=self.project,site_id=f'PAGED-{i}',schema_snapshot=self.c.schema_snapshot)
        response=self.client.get(self.url,{'q':'PAGED-'})
        self.assertEqual(response.context['total'],28);self.assertEqual(len(response.context['page_obj']),25)
        self.assertEqual(self.client.post(self.url,{'action':'approve'}).status_code,405)
