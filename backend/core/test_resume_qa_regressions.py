"""Independent existing-route regressions; temporary DB/media, zero native AI."""
from copy import deepcopy
from pathlib import Path
import hashlib
from django.test import TestCase,override_settings
from django.urls import reverse
from . import test_engineer_category_submission_acceptance as fixtures
from .models import Checklist
from .review_route_service import route_context
from .revision_models import RevisionDecision

@override_settings(SECRET_KEY='independent-quick-review',ROOT_URLCONF='checklist.urls_local',
 ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
 PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentQuickReviewTests(TestCase):
 setUp=fixtures.EngineerCategorySubmissionAcceptanceTests.setUp
 person=fixtures.EngineerCategorySubmissionAcceptanceTests.person
 add_photo=fixtures.EngineerCategorySubmissionAcceptanceTests.add_photo
 raw=fixtures.EngineerCategorySubmissionAcceptanceTests.raw
 post=fixtures.EngineerCategorySubmissionAcceptanceTests.post
 upload=fixtures.EngineerCategorySubmissionAcceptanceTests.upload
 state=fixtures.EngineerCategorySubmissionAcceptanceTests.state
 submit=fixtures.EngineerCategorySubmissionAcceptanceTests.submit
 qa_state=fixtures.EngineerCategorySubmissionAcceptanceTests.qa_state
 qa_action=fixtures.EngineerCategorySubmissionAcceptanceTests.qa_action
 complete_qa_manually=fixtures.EngineerCategorySubmissionAcceptanceTests.complete_qa_manually

 def prepared(self):
  self.upload('Civil');response,_=self.submit();self.assertEqual(response.status_code,201,response.content)
  self.revision=self.checklist.processing_revisions.get();self.before=deepcopy(self.revision.snapshot)
  self.photo=self.checklist.photo_evidence.get();self.original=Path(self.photo.original.path).read_bytes()
  self.client.force_login(self.quality)

 def decision(self,action,token,target=None):
  return self.client.post(reverse('review_route_action',args=[self.checklist.pk]),{
   'action':action,'expected_token':token,'reason':'SYNTHETIC independent source review',
   'return_to':target or reverse('photo_workspace',args=[self.checklist.pk])+'?qa_step=decision'})

 def preserved(self):
  self.revision.refresh_from_db();self.assertEqual(self.revision.snapshot,self.before)
  self.assertEqual(Path(self.photo.original.path).read_bytes(),self.original)
  self.assertEqual(self.checklist.processing_revisions.count(),1)

 def test_repeated_successful_workbench_decision_cannot_duplicate_signatures_or_skip_stage(self):
  self.prepared();self.complete_qa_manually();self.checklist.refresh_from_db()
  token=route_context(self.quality,self.checklist)['token']
  first=self.decision('approve',token);self.assertEqual(first.status_code,302,first.content)
  self.assertEqual(first['Location'],reverse('photo_workspace',args=[self.checklist.pk])+'?qa_step=decision')
  second=self.decision('approve',token);self.assertIn(second.status_code,[403,409],second.content)
  self.checklist.refresh_from_db();self.assertEqual(self.checklist.review_route_record.stage,'team_lead')
  events=self.checklist.review_route_record.events.filter(action='approve')
  self.assertEqual(events.count(),1);self.assertEqual(events.get().actor_id,self.quality.pk)
  self.assertEqual(RevisionDecision.objects.filter(revision=self.checklist.review_route_record.revision,action='validate').count(),1)
  self.preserved()

 def test_foreign_local_record_return_cannot_redirect_or_mutate_that_record(self):
  self.prepared()
  other=Checklist.objects.create(project=self.project,user=self.engineer,quality_reviewer=self.quality,
   site_id='SYNTHETIC-OTHER-RETURN',schema_snapshot=deepcopy(self.schema))
  previous=other.status;self.checklist.refresh_from_db();token=route_context(self.quality,self.checklist)['token']
  response=self.decision('reject',token,reverse('photo_workspace',args=[other.pk])+'?qa_step=decision')
  self.assertEqual(response.status_code,302,response.content)
  self.assertEqual(response['Location'],reverse('roadmap_activity',args=[self.checklist.pk]))
  other.refresh_from_db();self.assertEqual(other.status,previous);self.assertFalse(other.processing_revisions.exists())
  self.checklist.refresh_from_db();self.assertEqual(self.checklist.review_route_record.stage,'engineer')
  self.preserved()

 def test_real_failed_ai_does_not_block_manual_review_or_turn_qa_approval_into_ai_retry(self):
  self.prepared();job=self.revision.processing_job
  job.status='failed';job.error='SYNTHETIC unavailable model';job.save(update_fields=['status','error'])
  self.complete_qa_manually();self.checklist.refresh_from_db();token=route_context(self.quality,self.checklist)['token']
  response=self.decision('approve',token);self.assertEqual(response.status_code,302,response.content)
  job.refresh_from_db();self.assertEqual((job.status,job.error),('failed','SYNTHETIC unavailable model'))
  self.assertEqual(self.revision.processing_events.filter(action='technical_approve',actor=self.quality).count(),1)
  self.preserved()
