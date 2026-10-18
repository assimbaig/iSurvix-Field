"""Independent HTTP acceptance for optional roadmap governance and source isolation."""
import hashlib
import json
import tempfile
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import Client,TestCase,override_settings
from django.urls import reverse
from PIL import Image
from .models import Company,Project,ProjectMembership,Profile,ChecklistTemplate,Checklist,PhotoEvidence
from .independent_workflow import configure_policy,submit_revision,review_revision
from .roadmap_service import qualify_template


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RoadmapHttpAcceptanceTests(TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='roadmap-http-qa-',dir=Path(__file__).resolve().parents[2]/'.local')
        self.addCleanup(temporary.cleanup)
        storage=override_settings(MEDIA_ROOT=temporary.name)
        storage.enable()
        self.addCleanup(storage.disable)
        self.company=Company.objects.create(name='Roadmap QA company')
        self.other_company=Company.objects.create(name='Foreign roadmap QA company')
        self.schema={'title':'Roadmap QA checklist','sections':[{'id':'general','title':'General','fields':[{'id':'condition','label':'Recorded condition','type':'text'},{'id':'overview','label':'Overview evidence','type':'photo'}]}]}
        template=ChecklistTemplate.objects.create(name='Roadmap QA checklist',definition=deepcopy(self.schema),published=True)
        self.project=Project.objects.create(name='Roadmap QA project',company=self.company,checklist_template=template)
        self.other_project=Project.objects.create(name='Foreign roadmap QA project',company=self.other_company,checklist_template=template)
        self.admin=self.person('roadmap_http_admin',Profile.Roles.ADMIN,self.project)
        self.super=self.person('roadmap_http_super',Profile.Roles.SUPER_ADMIN,superuser=True)
        self.engineer=self.person('roadmap_http_engineer',Profile.Roles.ENGINEER,self.project)
        self.quality=self.person('roadmap_http_quality',Profile.Roles.QUALITY_ENGINEER,self.project)
        self.lead=self.person('roadmap_http_lead',Profile.Roles.TEAM_LEAD,self.project)
        self.customer=self.person('roadmap_http_client',Profile.Roles.CLIENT,self.project)
        self.peer=self.person('roadmap_http_peer',Profile.Roles.ENGINEER,self.project)
        self.other_lead=self.person('roadmap_http_unassigned_lead',Profile.Roles.TEAM_LEAD,self.project)
        self.outsider=self.person('roadmap_http_foreign',Profile.Roles.PROJECT_MANAGER,self.other_project)
        self.c=Checklist.objects.create(user=self.engineer,project=self.project,site_id='SYNTHETIC-ROADMAP',answer_data={'custom':{'condition':'Frozen original observation'}},coordinate_reference={'source':'Synthetic test source','crs':'Synthetic test CRS'})
        qualify_template(self.lead,self.project,self.c.workflow_type,'Synthetic criteria','Synthetic visual method','Synthetic applicability review')
        configure_policy(self.admin,self.c,self.quality,self.lead,'Explicit independent test assignments',customer_reviewer=self.customer,customer_required=True)
        self.c.refresh_from_db()
        data=BytesIO();Image.new('RGB',(10,10),'blue').save(data,format='PNG');self.original=data.getvalue()
        self.photo=PhotoEvidence.objects.create(checklist=self.c,filename='synthetic-original.png',sha256=hashlib.sha256(self.original).hexdigest(),metadata={'format':'PNG'})
        self.photo.original.save('synthetic-source.bin',ContentFile(self.original))
        self.photo.preview.save('synthetic-preview.png',ContentFile(self.original))
        self.client.force_login(self.engineer)

    def person(self,name,role,project=None,superuser=False):
        user=User.objects.create_user(name,email=name+'@example.test',password='Roadmap-fixture-912!')
        user.is_superuser=superuser;user.save()
        user.profile.role=role;user.profile.project=project;user.profile.company=project.company if project else None;user.profile.save()
        if project:ProjectMembership.objects.create(user=user,project=project,is_primary=True)
        return user

    def submit(self):
        self.c.refresh_from_db()
        return submit_revision(self.engineer,self.c)

    def review_url(self,revision):
        return reverse('roadmap_revision_review',args=[self.c.pk,revision.pk])

    def test_direct_activity_and_original_access_requires_explicit_site_assignment(self):
        for actor in [self.peer,self.other_lead,self.outsider]:
            self.client.force_login(actor)
            self.assertEqual(self.client.get(reverse('roadmap_activity',args=[self.c.pk])).status_code,404)
            self.assertEqual(self.client.get(reverse('photo_evidence',args=[self.c.pk,self.photo.pk,'original'])).status_code,404)
        for actor in [self.engineer,self.quality,self.lead,self.admin]:
            self.client.force_login(actor)
            self.assertEqual(self.client.get(reverse('roadmap_activity',args=[self.c.pk])).status_code,200)
            response=self.client.get(reverse('photo_evidence',args=[self.c.pk,self.photo.pk,'original']))
            self.assertEqual(response.status_code,200)
            self.assertEqual(b''.join(response.streaming_content),self.original)
            response.close()
        self.client.force_login(self.super)
        self.assertEqual(self.client.get(reverse('roadmap_activity',args=[self.c.pk])).status_code,403)
        self.assertEqual(self.client.get(reverse('photo_evidence',args=[self.c.pk,self.photo.pk,'original'])).status_code,403)

    def test_revision_export_and_report_deny_foreign_company_peer_and_early_customer(self):
        revision=self.submit()
        for actor in [self.outsider,self.peer,self.other_lead,self.customer]:
            self.client.force_login(actor)
            for name in ['roadmap_revision_export','roadmap_revision_report']:
                self.assertEqual(self.client.get(reverse(name,args=[self.c.pk,revision.pk])).status_code,404)
        self.client.force_login(self.quality)
        response=self.client.get(reverse('roadmap_revision_export',args=[self.c.pk,revision.pk]))
        self.assertEqual(response.status_code,200)
        self.assertIn('Frozen original observation',response.content.decode())
        self.assertNotIn('password',response.content.decode().lower())
        self.assertEqual(response.json()['snapshot']['photos'][0]['sha256'],self.photo.sha256)
        report=self.client.get(reverse('roadmap_revision_report',args=[self.c.pk,revision.pk]))
        self.assertEqual(report.status_code,200)
        self.assertContains(report,'Frozen original observation')
        self.assertEqual(report['Cache-Control'],'private, no-store')

    def test_http_signatures_deny_admin_super_wrong_reviewer_and_out_of_order_pm(self):
        revision=self.submit()
        for actor in [self.admin,self.super,self.engineer,self.other_lead]:
            self.client.force_login(actor)
            response=self.client.post(self.review_url(revision),{'action':'validate','reason':'Attempted substituted signature'})
            self.assertIn(response.status_code,(403,404))
        self.client.force_login(self.lead)
        self.assertEqual(self.client.post(self.review_url(revision),{'action':'approve','reason':'Out of order'}).status_code,403)
        self.assertEqual(revision.decisions.count(),1)
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.SUBMITTED)
        self.client.force_login(self.quality)
        self.assertEqual(self.client.post(self.review_url(revision),{'action':'validate','reason':'Independent L2 validation'}).status_code,302)
        self.client.force_login(self.lead)
        self.assertEqual(self.client.post(self.review_url(revision),{'action':'approve','reason':'Independent L3 approval'}).status_code,302)
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.FINAL)
        self.assertEqual(revision.decisions.count(),3)

    def test_revision_http_review_requires_csrf(self):
        revision=self.submit()
        browser=Client(enforce_csrf_checks=True);browser.force_login(self.quality)
        self.assertEqual(browser.post(self.review_url(revision),{'action':'validate','reason':'Missing CSRF'}).status_code,403)
        self.assertEqual(revision.decisions.count(),1)

    def test_revoked_assignment_blocks_read_export_original_and_new_decisions(self):
        revision=self.submit()
        ProjectMembership.objects.filter(user=self.quality,project=self.project).update(is_active=False)
        self.client.force_login(self.quality)
        for name,args in [('roadmap_activity',[self.c.pk]),('roadmap_revision_export',[self.c.pk,revision.pk]),('roadmap_revision_report',[self.c.pk,revision.pk]),('photo_evidence',[self.c.pk,self.photo.pk,'original'])]:
            self.assertEqual(self.client.get(reverse(name,args=args)).status_code,404)
        self.assertIn(self.client.post(self.review_url(revision),{'action':'validate','reason':'Revoked reviewer'}).status_code,(403,404))
        self.assertEqual(revision.decisions.count(),1)

    def test_frozen_export_preserves_original_snapshot_even_if_live_data_is_changed(self):
        revision=self.submit();before=deepcopy(revision.snapshot)
        Checklist.objects.filter(pk=self.c.pk).update(answer_data={'custom':{'condition':'Later mutable data must not leak'}})
        self.client.force_login(self.engineer)
        response=self.client.get(reverse('roadmap_revision_export',args=[self.c.pk,revision.pk]))
        self.assertEqual(response.status_code,200)
        body=response.content.decode()
        self.assertIn('Frozen original observation',body)
        self.assertNotIn('Later mutable data must not leak',body)
        report=self.client.get(reverse('roadmap_revision_report',args=[self.c.pk,revision.pk]))
        self.assertEqual(report.status_code,200)
        self.assertContains(report,'Frozen original observation')
        self.assertNotContains(report,'Later mutable data must not leak')
        revision.refresh_from_db();self.assertEqual(revision.snapshot,before)
        self.client.force_login(self.quality)
        self.assertIn(self.client.post(self.review_url(revision),{'action':'validate','reason':'Stale live inputs'}).status_code,(400,409))
        self.assertEqual(revision.decisions.count(),1)

    def test_qualified_technical_route_cannot_be_signed_by_administrators(self):
        url=reverse('roadmap_qualify',args=[self.project.pk])
        payload={'workflow_type':self.c.workflow_type,'criteria_reference':'Synthetic criteria','inspection_method':'Synthetic method','reason':'Synthetic scope'}
        for actor in [self.admin,self.super,self.engineer,self.quality,self.customer]:
            self.client.force_login(actor);self.assertEqual(self.client.post(url,payload).status_code,403)
        self.client.force_login(self.outsider);self.assertIn(self.client.post(url,payload).status_code,(403,404))
        self.client.force_login(self.lead);self.assertEqual(self.client.post(url,payload).status_code,302)

    def test_finding_rejects_foreign_photo_without_partial_creation(self):
        other=Checklist.objects.create(user=self.peer,project=self.project,site_id='OTHER-SYNTHETIC-SITE')
        photo=PhotoEvidence.objects.create(checklist=other,filename='other.png',sha256='other-synthetic')
        self.client.force_login(self.engineer)
        response=self.client.post(reverse('roadmap_finding',args=[self.c.pk]),{'description':'Synthetic observed issue','severity':'high','blocking':'on','photo_ids':json.dumps([photo.pk])})
        self.assertIn(response.status_code,(400,409))
        self.assertFalse(self.c.inspection_findings.exists())

    def test_generic_legacy_review_cannot_bypass_explicit_revision_route(self):
        revision=self.submit()
        self.client.force_login(self.quality)
        for name in ['custom_checklist_review','checklist_review_update']:
            response=self.client.post(reverse(name,args=[self.c.pk]),{'action':'approve','status':'FINAL','reason':'Attempted generic bypass'})
            self.assertEqual(response.status_code,409)
        self.assertEqual(revision.decisions.count(),1)
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.SUBMITTED)

    def test_stage_ordered_returns_create_linked_correction_without_rewriting_old_export(self):
        revision=self.submit()
        self.client.force_login(self.lead)
        self.assertEqual(self.client.post(self.review_url(revision),{'action':'return','reason':'Premature L3 return'}).status_code,403)
        self.client.force_login(self.quality)
        self.assertEqual(self.client.post(self.review_url(revision),{'action':'return','reason':'Source evidence needs correction'}).status_code,302)
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.REJECTED)
        self.client.force_login(self.engineer)
        response=self.client.post(reverse('custom_checklist_save',args=[self.c.pk]),json.dumps({'answers':{'condition':'Linked corrected observation'}}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.post(reverse('custom_checklist_submit',args=[self.c.pk])).status_code,302)
        self.c.refresh_from_db();next_revision=self.c.review_policy.current_revision
        self.assertNotEqual(next_revision.pk,revision.pk)
        self.assertEqual(next_revision.parent_id,revision.pk)
        self.assertEqual(next_revision.number,revision.number+1)
        old=self.client.get(reverse('roadmap_revision_export',args=[self.c.pk,revision.pk]))
        self.assertIn('Frozen original observation',old.content.decode())
        self.assertNotIn('Linked corrected observation',old.content.decode())
        self.client.force_login(self.quality)
        self.assertIn(self.client.post(self.review_url(revision),{'action':'validate','reason':'Obsolete revision'}).status_code,(400,409))

    def test_only_named_customer_can_read_approved_revision_and_cross_checklist_id_is_denied(self):
        revision=self.submit()
        review_revision(self.quality,self.c,revision.pk,'validate','L2 fixture validation')
        review_revision(self.lead,self.c,revision.pk,'approve','L3 fixture approval')
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse('roadmap_revision_export',args=[self.c.pk,revision.pk])).status_code,200)
        other_customer=self.person('roadmap_http_other_client',Profile.Roles.CLIENT,self.project)
        self.client.force_login(other_customer)
        self.assertEqual(self.client.get(reverse('roadmap_revision_export',args=[self.c.pk,revision.pk])).status_code,404)
        self.client.force_login(self.admin)
        other=Checklist.objects.create(user=self.peer,project=self.project,site_id='OTHER-REVISION-CONTEXT')
        self.assertEqual(self.client.get(reverse('roadmap_revision_export',args=[other.pk,revision.pk])).status_code,404)

    def test_customer_http_rejects_then_linked_engineer_correction_repeats_independent_stages(self):
        from .models import WorkAssignment
        from .independent_workflow import revision_state
        task=WorkAssignment.objects.create(checklist=self.c,project=self.project,assigned_to=self.engineer,assigned_by=self.quality,site_id=self.c.site_id,latitude=24,longitude=46,description='Synthetic customer-return activity')
        first=self.submit()
        frozen=deepcopy(first.snapshot)
        review_revision(self.quality,self.c,first.pk,'validate','L2 validated source')
        review_revision(self.lead,self.c,first.pk,'approve','L3 approved source')
        self.c.refresh_from_db();task.refresh_from_db()
        self.assertEqual(task.status,WorkAssignment.Status.CLIENT_REVIEW)
        url=reverse('governance_client_approval',args=[self.c.pk])
        self.client.force_login(self.customer)
        payload={'decision':'rejected','reference':'Customer requests a corrected source observation','expected_updated_at':self.c.updated_at.isoformat(),'expected_review_token':self.c.client_review_token}
        self.assertEqual(self.client.post(url,payload).status_code,302)
        self.c.refresh_from_db();task.refresh_from_db();first.refresh_from_db()
        self.assertEqual(self.c.status,Checklist.Status.REJECTED)
        self.assertEqual(revision_state(first),'customer_rejected')
        self.assertEqual(first.snapshot,frozen)
        self.assertTrue(first.decisions.filter(action='approve',actor=self.lead).exists())
        self.assertTrue(first.decisions.filter(action='customer_reject',level='C1',actor=self.customer).exists())
        self.assertNotEqual(task.status,WorkAssignment.Status.COMPLETED)
        self.assertIsNone(task.completed_at)
        for name in ['roadmap_revision_export','roadmap_revision_report']:
            response=self.client.get(reverse(name,args=[self.c.pk,first.pk]))
            self.assertEqual(response.status_code,200)
            self.assertIn('Frozen original observation',response.content.decode())
        self.client.force_login(self.engineer)
        response=self.client.post(reverse('custom_checklist_save',args=[self.c.pk]),json.dumps({'answers':{'condition':'Corrected after customer return'}}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.post(reverse('custom_checklist_submit',args=[self.c.pk])).status_code,302)
        self.c.refresh_from_db();second=self.c.review_policy.current_revision
        self.assertEqual(second.parent_id,first.pk)
        self.assertEqual(second.number,first.number+1)
        self.assertEqual(self.c.client_approval,{})
        self.assertEqual(list(second.decisions.values_list('action',flat=True)),['submit'])
        review_revision(self.quality,self.c,second.pk,'validate','L2 validates corrected source')
        review_revision(self.lead,self.c,second.pk,'approve','L3 approves corrected source')
        self.c.refresh_from_db()
        self.client.force_login(self.customer)
        payload={'decision':'approved','reference':'Customer accepts corrected revision','expected_updated_at':self.c.updated_at.isoformat(),'expected_review_token':self.c.client_review_token}
        self.assertEqual(self.client.post(url,payload).status_code,302)
        self.c.refresh_from_db();task.refresh_from_db()
        self.assertEqual(task.status,WorkAssignment.Status.COMPLETED)
        self.assertIsNotNone(task.completed_at)
        self.assertTrue(second.decisions.filter(action='customer_approve',level='C1',actor=self.customer).exists())
        first.refresh_from_db();self.assertEqual(first.snapshot,frozen)
        self.assertTrue(first.decisions.filter(action='customer_reject').exists())
        old=self.client.get(reverse('roadmap_revision_export',args=[self.c.pk,first.pk]))
        self.assertEqual(old.status_code,200)
        self.assertIn('Frozen original observation',old.content.decode())
        self.assertNotIn('Corrected after customer return',old.content.decode())

    def test_customer_approval_fresh_http_token_cannot_accept_tampered_frozen_inputs(self):
        from .models import WorkAssignment
        task=WorkAssignment.objects.create(checklist=self.c,project=self.project,assigned_to=self.engineer,assigned_by=self.quality,site_id=self.c.site_id,latitude=24,longitude=46,description='Synthetic stale customer review')
        revision=self.submit()
        review_revision(self.quality,self.c,revision.pk,'validate','L2 validated source')
        review_revision(self.lead,self.c,revision.pk,'approve','L3 approved source')
        Checklist.objects.filter(pk=self.c.pk).update(answer_data={'custom':{'condition':'Tampered after independent approval'}})
        self.c.refresh_from_db();task.refresh_from_db()
        before_history=deepcopy(self.c.review_history)
        before_sections=deepcopy(self.c.section_approvals)
        # Token is fresh for the current row: the immutable revision digest must reject it.
        payload={'decision':'approved','reference':'Fresh page over changed source','expected_updated_at':self.c.updated_at.isoformat(),'expected_review_token':self.c.client_review_token}
        self.client.force_login(self.customer)
        response=self.client.post(reverse('governance_client_approval',args=[self.c.pk]),payload)
        self.assertEqual(response.status_code,409)
        self.c.refresh_from_db();task.refresh_from_db()
        self.assertEqual(self.c.client_approval,{})
        self.assertIsNone(self.c.client_review_completed_at)
        self.assertEqual(self.c.review_history,before_history)
        self.assertEqual(self.c.section_approvals,before_sections)
        self.assertEqual(task.status,WorkAssignment.Status.CLIENT_REVIEW)
        self.assertIsNone(task.completed_at)
        self.assertFalse(revision.decisions.filter(action__in=['customer_approve','customer_reject']).exists())

    def test_frozen_source_named_customer_after_return_and_revocation_boundaries(self):
        revision=self.submit()
        url=reverse('roadmap_revision_source',args=[self.c.pk,revision.pk,self.photo.pk])
        for actor in [self.outsider,self.peer,self.other_lead,self.customer]:
            self.client.force_login(actor)
            self.assertEqual(self.client.get(url).status_code,404)
        review_revision(self.quality,self.c,revision.pk,'validate','L2 validates frozen source')
        review_revision(self.lead,self.c,revision.pk,'approve','L3 approves frozen source')
        self.c.refresh_from_db();self.client.force_login(self.customer)
        payload={'decision':'rejected','reference':'Correct this submission while retaining its source','expected_updated_at':self.c.updated_at.isoformat(),'expected_review_token':self.c.client_review_token}
        self.assertEqual(self.client.post(reverse('governance_client_approval',args=[self.c.pk]),payload).status_code,302)
        response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        data=b''.join(response.streaming_content)
        response.close()
        self.assertEqual(data,self.original)
        self.assertEqual(hashlib.sha256(data).hexdigest(),self.photo.sha256)
        self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        self.assertIn('attachment',response['Content-Disposition'])
        fresh=PhotoEvidence.objects.create(checklist=self.c,filename='new-draft-source.png',sha256='new-draft-source')
        self.assertEqual(self.client.get(reverse('roadmap_revision_source',args=[self.c.pk,revision.pk,fresh.pk])).status_code,404)
        self.assertEqual(self.client.get(reverse('photo_evidence',args=[self.c.pk,self.photo.pk,'original'])).status_code,404)
        ProjectMembership.objects.filter(user=self.customer,project=self.project).update(is_active=False)
        self.assertEqual(self.client.get(url).status_code,404)

    def test_frozen_source_corruption_is_controlled_and_never_streams_changed_bytes(self):
        revision=self.submit()
        url=reverse('roadmap_revision_source',args=[self.c.pk,revision.pk,self.photo.pk])
        self.client.force_login(self.quality)
        marker=b'CORRUPTED SYNTHETIC FILE MUST NOT BE RETURNED'
        Path(self.photo.original.path).write_bytes(marker)
        response=self.client.get(url)
        self.assertEqual(response.status_code,409)
        self.assertFalse(response.streaming)
        self.assertNotIn(marker,response.content)
        self.assertNotIn(self.original,response.content)
        PhotoEvidence.objects.filter(pk=self.photo.pk).update(sha256='f'*64)
        self.assertEqual(self.client.get(url).status_code,404)
        PhotoEvidence.objects.filter(pk=self.photo.pk).update(sha256=self.photo.sha256)
        Path(self.photo.original.path).unlink()
        missing=self.client.get(url)
        self.assertEqual(missing.status_code,503)
        self.assertFalse(missing.streaming)
        self.assertNotIn(b'Traceback',missing.content)
        self.assertNotIn(self.photo.original.path.encode(),missing.content)
        self.assertNotIn(marker,missing.content)
