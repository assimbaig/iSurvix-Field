from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse
from .models import Company, Project, Profile, WorkAssignment, Checklist

class SuperadminDeskTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_superuser('desk-owner','owner@example.test','test')
        self.engineer=User.objects.create_user('desk-engineer')
        self.a=Company.objects.create(name='Desk A')
        self.b=Company.objects.create(name='Desk B')
        self.pa=Project.objects.create(name='Desk project A',company=self.a)
        self.pb=Project.objects.create(name='Desk project B',company=self.b)
        self.engineer.profile.company=self.a
        self.engineer.profile.save()
        self.site=WorkAssignment.objects.create(site_id='DESK-001',latitude=0,longitude=0,description='test',project=self.pa,assigned_to=self.engineer,assigned_by=self.owner)
    def desk(self, **params):
        from .superadmin_dashboard import build_superadmin_desk
        request=RequestFactory().get('/governance/',params)
        request.user=self.owner
        return build_superadmin_desk(request)
    def test_totals_and_rows_use_saved_records_without_join_inflation(self):
        Project.objects.create(name='Desk project A2',company=self.a)
        desk=self.desk()
        self.assertEqual(desk['counts'],{'companies':2,'projects':3,'sites':1,'users':2})
        row=next(row for row in desk['company_rows'] if row['company'].pk==self.a.pk)
        self.assertEqual((row['project_count'],row['site_count'],row['user_count']),(2,1,1))
    def test_company_project_site_selection_is_scoped_to_ancestors(self):
        with self.assertRaises(Http404): self.desk(desk_company=self.a.pk,desk_project=self.pb.pk)
        with self.assertRaises(Http404): self.desk(desk_company=self.b.pk,desk_project=self.pb.pk,desk_site=self.site.pk)
        desk=self.desk(desk_company=self.a.pk,desk_project=self.pa.pk,desk_site=self.site.pk)
        self.assertEqual(desk['selected_site'].pk,self.site.pk)
        self.assertEqual(len(desk['breadcrumbs']),4)
    def test_invalid_or_orphan_hierarchy_ids_are_rejected(self):
        for params in ({'desk_company':'9'*5000},{'desk_project':self.pa.pk},{'desk_company':self.a.pk,'desk_site':self.site.pk}):
            with self.subTest(params=str(params)[:80]),self.assertRaises(Http404): self.desk(**params)
    def test_builder_rejects_customer_accounts(self):
        from .superadmin_dashboard import build_superadmin_desk
        request=RequestFactory().get('/governance/')
        request.user=self.engineer
        with self.assertRaises(PermissionDenied): build_superadmin_desk(request)
    def test_company_table_is_paginated_and_search_preserves_hierarchy_links(self):
        Company.objects.bulk_create([Company(name='Extra %02d'%n) for n in range(30)])
        self.assertEqual(len(self.desk()['company_rows']),25)
        rows=self.desk(q='Desk A')['company_rows']
        self.assertEqual(len(rows),1)
        self.assertIn('desk_company='+str(self.a.pk),rows[0]['url'])
    def test_real_workspace_exposes_owner_desk_only(self):
        self.client.force_login(self.owner)
        response=self.client.get(reverse('governance_home'),{'view':'companies'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['superadmin_desk']['counts']['companies'],2)
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.get(reverse('governance_home'),{'view':'companies'}).status_code,404)

class SuperadminOnboardingModalTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_superuser('modal-owner','owner@example.test','test')
        self.client.force_login(self.owner)
    def test_compact_get_uses_saved_form_and_no_new_records(self):
        from .models import CompanyApplication
        response=self.client.get(reverse('company_onboarding_apply'),{'desk_modal':'1'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['desk_modal'])
        self.assertEqual(CompanyApplication.objects.count(),0)
    def test_modal_intake_redirect_keeps_wizard_context_and_replay_is_safe(self):
        import uuid
        from .models import CompanyApplication, IndustryCatalog
        data={'name':'Modal company','email':'admin@example.test','industry':IndustryCatalog.objects.get(code='telecom').pk,'request_key':uuid.uuid4(),'desk_return':'companies'}
        response=self.client.post(reverse('company_onboarding_apply'),data)
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.url.endswith('?desk_modal=1'))
        self.client.post(reverse('company_onboarding_apply'),data)
        self.assertEqual(CompanyApplication.objects.count(),1)
    def test_modal_return_rejects_arbitrary_destination_without_mutation(self):
        from .models import CompanyApplication
        response=self.client.post(reverse('company_onboarding_apply'),{'desk_return':'https://evil.example'})
        self.assertEqual(response.status_code,400)
        self.assertEqual(CompanyApplication.objects.count(),0)
    def test_modal_review_retains_errors_and_cannot_provision_before_approval(self):
        import uuid
        from .models import IndustryCatalog
        from .onboarding_service import apply_application
        app=apply_application(self.owner,request_key=uuid.uuid4(),name='Review modal',email='review@example.test',industry=IndustryCatalog.objects.get(code='telecom'))
        response=self.client.post(reverse('company_onboarding_action',args=[app.pk]),{'desk_return':'companies','action':'provision'})
        self.assertEqual(response.status_code,400)
        self.assertTrue(response.context['desk_modal'])
        app.refresh_from_db()
        self.assertIsNone(app.company_id)

class SuperadminSavedRecordsTests(TestCase):
    setUp=SuperadminDeskTests.setUp
    desk=SuperadminDeskTests.desk
    def test_saved_application_table_has_real_stage_and_independent_invitation_state(self):
        import uuid
        from .models import IndustryCatalog
        from .onboarding_service import apply_application, review_application, provision_application, invite_application
        app=apply_application(self.owner,request_key=uuid.uuid4(),name='Saved intake',email='saved@example.test',industry=IndustryCatalog.objects.get(code='telecom'))
        row=self.desk(desk_records='applications',q='Saved intake')['application_rows'][0]
        self.assertEqual(row['application'].status,'applied')
        self.assertEqual(row['invite_status'],'Not issued')
        review_application(self.owner,app.pk,approve=True)
        provision_application(self.owner,app.pk)
        app,token=invite_application(self.owner,app.pk)
        row=self.desk(desk_records='applications',app_status='invited')['application_rows'][0]
        self.assertEqual(row['application'].pk,app.pk)
        self.assertEqual(row['invite_status'],'Issued · acceptance pending')
        self.assertNotIn(token,str(row))
        self.assertNotEqual(row['email_status'],'Sent')
    def test_revision_metadata_stays_under_selected_site_without_snapshot_payload(self):
        from .models import SubmissionRevision
        checklist=Checklist.objects.create(user=self.engineer,project=self.pa,site_id='DESK-001')
        self.site.checklist=checklist;self.site.save()
        revision=SubmissionRevision.objects.create(checklist=checklist,number=1,snapshot={'secret_photo_path':'not_for_desk'},digest='a'*64,submitted_by=self.engineer,l2_reviewer=self.owner,l3_approver=self.owner)
        desk=self.desk(desk_company=self.a.pk,desk_project=self.pa.pk,desk_site=self.site.pk,desk_submission=revision.pk)
        self.assertIn('snapshot',desk['selected_submission'].get_deferred_fields())
        other=Checklist.objects.create(user=self.engineer,project=self.pb,site_id='OTHER')
        foreign=SubmissionRevision.objects.create(checklist=other,number=1,snapshot={},digest='b'*64,submitted_by=self.engineer,l2_reviewer=self.owner,l3_approver=self.owner)
        with self.assertRaises(Http404):self.desk(desk_company=self.a.pk,desk_project=self.pa.pk,desk_site=self.site.pk,desk_submission=foreign.pk)


class SuperadminDeskBoundaryTests(TestCase):
    setUp=SuperadminDeskTests.setUp
    desk=SuperadminDeskTests.desk
    def test_customer_admin_cannot_open_platform_company_desk(self):
        self.engineer.profile.role=Profile.Roles.ADMIN
        self.engineer.profile.save()
        self.client.force_login(self.engineer)
        for view in ('companies','system'):
            self.assertEqual(self.client.get(reverse('governance_home'),{'view':view}).status_code,404)
    def test_application_status_filter_rejects_invalid_enum_and_preserves_company_page(self):
        with self.assertRaises(Http404):self.desk(app_status='unsupported')
        Company.objects.bulk_create([Company(name='Paged %02d'%n) for n in range(30)])
        desk=self.desk(desk_page='2',q='Paged')
        self.assertEqual(desk['company_rows'].number,2)
        self.assertIn('desk_page=2',desk['company_rows'][0]['url'])
        self.assertIn('q=Paged',desk['company_navigation']['previous_url'])
