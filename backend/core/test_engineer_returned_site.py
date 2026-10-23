"""Returned sites keep their evidence and enable only the assigned Engineer.

Real Django routes/records/media are isolated by run_backend_tests.py. These
checks queue inference; the independent native worker is verified separately.
"""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json

from django.test import TestCase,override_settings
from django.urls import reverse

from . import test_engineer_category_submission_acceptance as capture_fixtures
from . import category_intake,survey_processing as pipeline
from .independent_workflow import submit_revision
from .models import Checklist,Profile,WorkAssignment
from .survey_processing_models import SurveyProcessingRevision,SurveyProcessingJob,SurveyProcessingEvent


@override_settings(SECRET_KEY='isolated-engineer-returned-site',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EngineerReturnedSiteTests(TestCase):
    setUp=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.setUp
    person=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.person
    add_photo=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.add_photo
    post=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.post
    state=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.state
    raw=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.raw
    upload=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.upload
    submit=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.submit
    route=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.route

    def seed_photos(self):
        ids=[]
        for category,label in [('Civil','return-civil'),('Electrical','return-electrical'),
                               ('Tower','return-tower'),('Civil','retained-uncategorised')]:
            rows,_=self.upload(category,(label,));ids.append(rows[0]['id'])
        # Retained historical blank-category evidence remains readable, although
        # new captures correctly accept only the three photo categories.
        self.checklist.photo_evidence.filter(pk=ids[-1]).update(group='')
        self.assertEqual(len(self.state()['photos']),4)
        return ids

    def rejected_by_qa(self):
        reason='Add a clear tower photograph and correct the recorded site contact.'
        if self.checklist.governance_mode==Checklist.GovernanceMode.INDEPENDENT:
            result=self.route(self.quality,'reject',reason)
        else:
            self.checklist.refresh_from_db();self.client.force_login(self.quality)
            result=self.client.post(reverse('quality_review',args=[self.checklist.pk]),{
                'decision':'reject','reason':reason,'expected_updated_at':self.checklist.updated_at.isoformat()})
        self.assertEqual(result.status_code,302,result.content)
        self.checklist.refresh_from_db();self.assignment.refresh_from_db()
        self.assertEqual(self.checklist.status,Checklist.Status.REJECTED)
        self.assertEqual(self.assignment.status,WorkAssignment.Status.IN_PROGRESS)
        return reason

    def exercise_returned_site(self,ids,first):
        frozen=deepcopy(first.snapshot);first_digest=first.digest
        submitted_records={row.pk:(row.digest,deepcopy(row.snapshot)) for row in self.checklist.submission_revisions.all()}
        submitted_decisions=list(self.checklist.submission_revisions.values_list('decisions__pk','decisions__action','decisions__actor_id'))
        original_files={photo.pk:Path(photo.original.path).read_bytes() for photo in self.checklist.photo_evidence.all()}
        reason=self.rejected_by_qa()
        self.client.force_login(self.engineer)
        page=self.client.get(reverse('photo_workspace',args=[self.checklist.pk]))
        self.assertEqual(page.status_code,200,page.content)
        self.assertContains(page,'id="engineer-capture"')
        current=self.state()
        self.assertTrue(current['can_edit']);self.assertTrue(current['can_submit'])
        self.assertFalse(current['submitted']);self.assertEqual(current['stage'],'engineer')
        self.assertEqual(current['correction_reason'],reason)
        self.assertFalse(current['general_information']['read_only'])
        self.assertEqual({p['id'] for p in current['photos']},set(ids))
        self.assertEqual({p['group'] for p in current['photos']},{'Civil','Electrical','Tower',''})
        for photo in current['photos']:
            for variant in ['original','preview']:
                response=self.client.get(photo[variant+'_url'])
                self.assertEqual(response.status_code,200,(photo['id'],variant))
                data=b''.join(response.streaming_content);response.close()
                self.assertTrue(data)
                if variant=='original':self.assertEqual(data,original_files[photo['id']])
        info=self.post('photo_capture_general_information',{
            'expected_digest':current['digest'],'expected_general_digest':current['general_information']['digest'],
            'site_information':{'site_name':'Synthetic corrected site'},
            'general_info':{'contact':'Recorded corrected site contact'}})
        self.assertEqual(info.status_code,200,info.content)
        self.assertEqual(info.json()['site_info']['site_name'],'Synthetic corrected site')
        changed=self.post('photo_capture_category',{'photo_ids':ids[:2],'group':'Tower',
            'expected_digest':self.state()['digest']})
        self.assertEqual(changed.status_code,200,changed.content)
        removed=self.post('photo_capture_remove',{'photo_id':ids[2],'expected_digest':self.state()['digest']})
        self.assertEqual(removed.status_code,200,removed.content)
        new,_=self.upload('Civil',('return-new-one','return-new-two'))
        new_ids={photo['id'] for photo in new}
        before_submit=self.state()
        self.assertEqual({p['id'] for p in before_submit['photos']},set(ids[:2]+ids[3:])|new_ids)
        self.assertEqual(len(before_submit['photos']),5)
        self.assertEqual(self.checklist.photo_evidence.count(),6,'Soft removal retains the old original evidence')
        self.assertIn(ids[3],[p['id'] for p in before_submit['photos'] if p['group']==''])
        result,digest=self.submit()
        self.assertEqual(result.status_code,201,result.content)
        latest=self.checklist.processing_revisions.get(pk=result.json()['revision_id'])
        self.assertEqual(latest.number,first.number+1)
        self.assertEqual(latest.processing_job.status,'queued')
        self.assertEqual(latest.processing_job.total,5)
        self.assertEqual(latest.snapshot['answers']['custom']['contact'],'Recorded corrected site contact')
        self.assertEqual({p['id'] for p in latest.snapshot['photos']},set(ids[:2]+ids[3:])|new_ids)
        self.assertNotIn(ids[2],{p['id'] for p in latest.snapshot['photos']})
        duplicate,_=self.submit(digest=digest)
        self.assertEqual(duplicate.status_code,200,duplicate.content)
        self.assertEqual(duplicate.json()['revision_id'],latest.pk)
        self.assertEqual(self.checklist.processing_revisions.count(),2)
        self.assertEqual(SurveyProcessingJob.objects.filter(revision__checklist=self.checklist).count(),2)
        first.refresh_from_db();self.checklist.refresh_from_db();self.assignment.refresh_from_db()
        self.assertEqual((first.digest,first.snapshot),(first_digest,frozen))
        self.assertEqual(first.processing_job.status,'queued','Returning work must not reset or replace the retained job')
        self.assertEqual(self.checklist.status,Checklist.Status.SUBMITTED)
        self.assertEqual(self.assignment.status,WorkAssignment.Status.SUBMITTED)
        self.assertFalse(self.state()['can_edit'])
        if self.checklist.governance_mode==Checklist.GovernanceMode.INDEPENDENT:
            self.assertEqual(self.checklist.review_route_record.stage,'quality_engineer')
            self.assertEqual(self.checklist.submission_revisions.count(),2)
            for pk,old in submitted_records.items():
                historical=self.checklist.submission_revisions.get(pk=pk)
                self.assertEqual((historical.digest,historical.snapshot),old)
            retained=list(self.checklist.submission_revisions.filter(pk__in=submitted_records).values_list('decisions__pk','decisions__action','decisions__actor_id'))
            self.assertEqual(retained,submitted_decisions)
            self.assertTrue(self.checklist.review_route_record.events.filter(action='reject',reason=reason).exists())
        for photo in self.checklist.photo_evidence.filter(pk__in=original_files):
            self.assertEqual(Path(photo.original.path).read_bytes(),original_files[photo.pk])
        self.assertFalse(latest.processing_events.filter(action__in=['engineer_complete','qa_complete','technical_approve']).exists())

    def test_routed_return_preserves_gallery_and_all_engineer_actions_then_resubmits(self):
        ids=self.seed_photos()
        response,_=self.submit();self.assertEqual(response.status_code,201,response.content)
        first=self.checklist.processing_revisions.get()
        with patch('core.local_ai.ollama',side_effect=AssertionError('Request handlers must not run inference')) as inference:
            self.exercise_returned_site(ids,first)
            inference.assert_not_called()

    def test_legacy_governance_quality_return_also_preserves_gallery_and_actions(self):
        self.project.review_layers=None;self.project.save(update_fields=['review_layers'])
        self.checklist=Checklist.objects.create(project=self.project,user=self.engineer,quality_reviewer=self.quality,
            site_id='SYNTHETIC-RETURN-LEGACY',governance_mode=Checklist.GovernanceMode.LEGACY)
        self.assignment=WorkAssignment.objects.create(project=self.project,assigned_by=self.lead,assigned_to=self.engineer,
            checklist=self.checklist,site_id=self.checklist.site_id,latitude=24,longitude=46,description='Synthetic legacy return')
        ids=self.seed_photos()
        response,_=self.submit();self.assertEqual(response.status_code,201,response.content)
        self.exercise_returned_site(ids,self.checklist.processing_revisions.get())

    def test_retained_pre_general_info_submission_returns_without_hiding_originals(self):
        ids=self.seed_photos()
        # Construct an older retained immutable submission rather than rewriting
        # a new revision to remove the versioned General Info context.
        self.checklist.refresh_from_db()
        self.checklist.intake_metadata={**self.checklist.intake_metadata,
            'category_intake_version':1,'category_intake_cycle':1}
        self.checklist.save(update_fields=['intake_metadata'])
        snapshot=category_intake.source_snapshot(self.checklist)
        self.assertNotIn('general_information_context',snapshot['intake'])
        first=SurveyProcessingRevision.objects.create(checklist=self.checklist,number=1,
            digest=pipeline.digest(snapshot),snapshot=snapshot,submitted_by=self.engineer)
        SurveyProcessingJob.objects.create(revision=first,status='queued',model='qwen3.5:4b',total=4)
        self.checklist.intake_metadata['category_intake_revision']=first.pk
        self.checklist.save(update_fields=['intake_metadata'])
        SurveyProcessingEvent.objects.create(revision=first,actor=self.engineer,action='capture_submitted',
            payload={'source_digest':first.digest,'request_digest':first.digest})
        submit_revision(self.engineer,self.checklist)
        self.exercise_returned_site(ids,first)
