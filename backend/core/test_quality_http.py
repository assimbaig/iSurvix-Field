"""Quality Control route, evidence and AI scope acceptance on synthetic data."""
from django.contrib.auth.models import User
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from .models import Checklist,ChecklistTemplate,Project,Profile

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QualityHttpTests(TestCase):
    def setUp(self):
        template=ChecklistTemplate.objects.create(name='Quality HTTP',published=True,definition={'title':'Quality HTTP','sections':[{'id':'general','title':'General','fields':[{'id':'condition','label':'Condition','type':'text','required':True}]}]})
        self.project=Project.objects.create(name='Quality HTTP',checklist_template=template)
        def person(name,role):
            user=User.objects.create_user(name,password='Synthetic-only-349!')
            user.profile.role=role;user.profile.project=self.project;user.profile.save()
            return user
        self.engineer=person('quality_http_engineer',Profile.Roles.ENGINEER)
        self.qe=person('quality_http_qe',Profile.Roles.QUALITY_ENGINEER)
        self.other=person('quality_http_other_qe',Profile.Roles.QUALITY_ENGINEER)
        self.lead=person('quality_http_lead',Profile.Roles.TEAM_LEAD)
        self.c=Checklist.objects.create(user=self.engineer,project=self.project,site_id='QC-HTTP',quality_reviewer=self.qe,answer_data={'custom':{'condition':'Recorded'}})
        self.peer=Checklist.objects.create(user=self.engineer,project=self.project,site_id='QC-PRIVATE',quality_reviewer=self.other)
        self.url=reverse('quality_review',args=[self.c.pk])
    def submit(self):
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.post(reverse('custom_checklist_submit',args=[self.c.pk])).status_code,302)
        self.c.refresh_from_db()
    def payload(self,decision='approve'):
        self.c.refresh_from_db()
        return {'decision':decision,'reason':'Recorded evidence needs correction','expected_updated_at':self.c.updated_at.isoformat()}
    def test_named_quality_engineer_can_read_evidence_and_ai_but_not_edit_or_share(self):
        self.client.force_login(self.qe)
        for name in ['custom_checklist','photo_workspace','checklist_ai_review']:
            self.assertEqual(self.client.get(reverse(name,args=[self.c.pk])).status_code,200)
            self.assertEqual(self.client.get(reverse(name,args=[self.peer.pk])).status_code,404)
        response=self.client.get(reverse('custom_checklist',args=[self.c.pk]))
        self.assertFalse(response.context['can_edit']);self.assertFalse(response.context['can_submit'])
        self.assertEqual(self.client.post(reverse('custom_checklist_save',args=[self.c.pk]),'{}',content_type='application/json').status_code,403)
        response=self.client.get(reverse('checklist_ai_review',args=[self.c.pk]))
        self.assertTrue(response.context['can_request']);self.assertFalse(response.context['can_share'])
    def test_review_requires_csrf_current_submission_and_actual_assigned_role(self):
        self.submit()
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.qe)
        self.assertEqual(strict.post(self.url,self.payload()).status_code,403)
        for user in [self.engineer,self.lead,self.other]:
            self.client.force_login(user)
            self.assertIn(self.client.post(self.url,self.payload()).status_code,(403,404))
        self.client.force_login(self.qe)
        data=self.payload();data['expected_updated_at']='stale'
        self.assertEqual(self.client.post(self.url,data).status_code,409)
        self.assertEqual(self.client.post(self.url,self.payload()).status_code,302)
        self.assertEqual(self.client.post(self.url,self.payload()).status_code,409)
    def test_quality_return_resubmission_repeats_quality_before_team_lead(self):
        self.submit();self.client.force_login(self.qe)
        self.assertEqual(self.client.post(self.url,self.payload('reject')).status_code,302)
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.REJECTED)
        self.submit();self.client.force_login(self.lead)
        self.assertEqual(self.client.post(reverse('custom_checklist_review',args=[self.c.pk]),{'action':'approve'}).status_code,302)
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.SUBMITTED)
        self.client.force_login(self.qe)
        self.assertEqual(self.client.post(self.url,self.payload()).status_code,302)
        self.client.force_login(self.lead)
        self.assertEqual(self.client.post(reverse('custom_checklist_review',args=[self.c.pk]),{'action':'approve'}).status_code,302)
        self.c.refresh_from_db();self.assertEqual(self.c.status,Checklist.Status.FINAL)
