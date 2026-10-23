"""Reproduce a pre-QC returned checklist and exercise explicit reviewer correction."""
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase,override_settings
from django.urls import reverse
from .models import Checklist,ChecklistTemplate,Project,Profile,WorkAssignment

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RectificationRegressionTests(TestCase):
    def setUp(self):
        template=ChecklistTemplate.objects.create(name='Synthetic two-checkpoint correction',published=True,definition={'sections':[{'id':'one','title':'Checkpoint one','fields':[{'id':'point_one','label':'Checkpoint one observation','type':'text','required':True}]},{'id':'two','title':'Checkpoint two','fields':[{'id':'point_two','label':'Checkpoint two observation','type':'text','required':True}]}]})
        self.project=Project.objects.create(name='Synthetic correction project',checklist_template=template)
        self.engineer=self.person('correction_engineer',Profile.Roles.ENGINEER)
        self.quality=self.person('correction_quality',Profile.Roles.QUALITY_ENGINEER)
        self.lead=self.person('correction_lead',Profile.Roles.TEAM_LEAD)
        self.admin=self.person('correction_admin',Profile.Roles.ADMIN)
        self.survey=Checklist.objects.create(user=self.engineer,project=self.project,site_id='SYNTHETIC-CORRECTION',status=Checklist.Status.REJECTED,answer_data={'custom':{'point_one':'Recorded observation one','point_two':'Recorded observation two'}},review_history=[{'action':'reject','comment':'Earlier correction requested'}])
        self.work=WorkAssignment.objects.create(project=self.project,assigned_to=self.engineer,assigned_by=self.lead,site_id=self.survey.site_id,latitude=1,longitude=1,description='Synthetic correction task',checklist=self.survey,status=WorkAssignment.Status.IN_PROGRESS)
    def person(self,name,role):
        user=User.objects.create_user(name)
        user.profile.role=role;user.profile.project=self.project;user.profile.save()
        return user
    def test_missing_named_qe_is_reported_without_bypass_then_correction_can_finish(self):
        self.client.force_login(self.engineer)
        response=self.client.post(reverse('custom_checklist_submit',args=[self.survey.pk]))
        self.assertEqual(response.status_code,302)
        self.assertTrue(any('Assign an active project Quality Engineer before submission.' in str(message)
            for message in get_messages(response.wsgi_request)))
        self.survey.refresh_from_db();self.assertEqual(self.survey.status,Checklist.Status.REJECTED)
        self.assertIsNone(self.survey.quality_reviewer_id)
        self.client.force_login(self.admin)
        response=self.client.post(reverse('quality_reviewer_assign',args=[self.survey.pk]),{'quality_reviewer':self.quality.pk,'reason':'Explicit assignment for returned legacy work','expected_updated_at':self.survey.updated_at.isoformat()})
        self.assertEqual(response.status_code,302)
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.post(reverse('custom_checklist_submit',args=[self.survey.pk])).status_code,302)
        self.survey.refresh_from_db();self.assertEqual(self.survey.status,Checklist.Status.SUBMITTED)
        self.client.force_login(self.quality)
        reason='Clarify checkpoint two observation before resubmission'
        response=self.client.post(reverse('quality_review',args=[self.survey.pk]),{'decision':'reject','reason':reason,'expected_updated_at':self.survey.updated_at.isoformat()})
        self.assertEqual(response.status_code,302)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.status,Checklist.Status.REJECTED)
        self.assertEqual(self.survey.comment,reason)
        self.assertEqual(self.survey.comment_by_id,self.quality.pk)
        self.client.force_login(self.engineer)
        response=self.client.get(reverse('custom_checklist',args=[self.survey.pk]))
        self.assertRedirects(response,reverse('photo_workspace',args=[self.survey.pk]),fetch_redirect_response=False)
        state=self.client.get(reverse('photo_capture_state',args=[self.survey.pk])).json()
        self.assertEqual(state['correction_reason'],reason)
        self.assertTrue(state['can_edit'])
        self.assertEqual(self.client.post(reverse('custom_checklist_save',args=[self.survey.pk]),{'answers':{'point_two':'Corrected checkpoint two observation'}},content_type='application/json').status_code,200)
        self.assertEqual(self.client.post(reverse('custom_checklist_submit',args=[self.survey.pk])).status_code,302)
        self.survey.refresh_from_db();self.assertEqual(self.survey.quality_approval,{})
        self.client.force_login(self.lead)
        self.client.post(reverse('custom_checklist_review',args=[self.survey.pk]),{'action':'approve'})
        self.survey.refresh_from_db();self.assertEqual(self.survey.status,Checklist.Status.SUBMITTED)
        self.client.force_login(self.quality)
        self.assertEqual(self.client.post(reverse('quality_review',args=[self.survey.pk]),{'decision':'approve','reason':'Corrected evidence reviewed','expected_updated_at':self.survey.updated_at.isoformat()}).status_code,302)
        self.client.force_login(self.lead)
        self.assertEqual(self.client.post(reverse('custom_checklist_review',args=[self.survey.pk]),{'action':'approve','comment':'Accepted corrected observations'}).status_code,302)
        self.survey.refresh_from_db();self.work.refresh_from_db()
        self.assertEqual(self.survey.status,Checklist.Status.FINAL)
        self.assertEqual(self.work.status,WorkAssignment.Status.COMPLETED)
        self.assertEqual(self.survey.answer_data['custom']['point_two'],'Corrected checkpoint two observation')
        self.assertEqual([event['action'] for event in self.survey.review_history],['reject','quality_assigned','quality_reject','quality_approve','approve'])
