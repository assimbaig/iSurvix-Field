"""Whole-task rejection is independent of optional per-photo review.

Real HTTP/database/media integration, isolated by run_backend_tests.py. These
tests verify existing behaviour and do not invoke native inference or approve
operational work. Original evidence and historical analysis are immutable.
"""
from copy import deepcopy
from pathlib import Path

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from . import category_intake, survey_processing as pipeline
from . import test_engineer_category_submission_acceptance as fixtures
from .models import Checklist, Company, Profile, Project, WorkAssignment
from .review_route_service import route_context
from .survey_processing_models import SurveyProcessingResult, SurveySourceAnalysis


@override_settings(SECRET_KEY='isolated-unreviewed-photo-task-return',
    ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QATaskRejectWithoutPhotoReviewTests(TestCase):
    person=fixtures.EngineerCategorySubmissionAcceptanceTests.person
    add_photo=fixtures.EngineerCategorySubmissionAcceptanceTests.add_photo
    post=fixtures.EngineerCategorySubmissionAcceptanceTests.post
    state=fixtures.EngineerCategorySubmissionAcceptanceTests.state
    raw=fixtures.EngineerCategorySubmissionAcceptanceTests.raw
    upload=fixtures.EngineerCategorySubmissionAcceptanceTests.upload
    submit=fixtures.EngineerCategorySubmissionAcceptanceTests.submit
    assert_submitted=fixtures.EngineerCategorySubmissionAcceptanceTests.assert_submitted

    def setUp(self):
        fixtures.EngineerCategorySubmissionAcceptanceTests.setUp(self)
        self.ids=[]
        for category in ('Civil','Electrical','Tower'):
            rows,_=self.upload(category,('unreviewed-'+category.lower(),))
            self.ids.append(rows[0]['id'])
        submitted,_=self.submit()
        self.assertEqual(submitted.status_code,201,submitted.content)
        self.revision=self.assert_submitted()
        self.originals={p.pk:Path(p.original.path).read_bytes()
            for p in self.checklist.photo_evidence.all()}
        self.snapshot=deepcopy(self.revision.snapshot)
        self.digest=self.revision.digest
        self.url=reverse('review_route_action',args=[self.checklist.pk])
        self.return_to=reverse('photo_workspace',args=[self.checklist.pk])+'?qa_step=decision'

    def decision(self,actor=None,action='reject',reason='Add the missing site evidence.',token=None):
        actor=actor or self.quality
        self.checklist.refresh_from_db()
        if token is None:token=route_context(actor,self.checklist)['token']
        self.client.force_login(actor)
        return self.client.post(self.url,{'action':action,'reason':reason,
            'expected_token':token,'return_to':self.return_to},HTTP_ACCEPT='application/json')

    def assert_returned_with_originals(self):
        self.checklist.refresh_from_db();self.assignment.refresh_from_db()
        self.assertEqual(self.checklist.status,Checklist.Status.REJECTED)
        self.assertEqual(self.checklist.review_route_record.stage,'engineer')
        self.assertEqual(self.assignment.status,WorkAssignment.Status.IN_PROGRESS)
        current=self.state(self.engineer)
        self.assertTrue(current['can_edit']);self.assertTrue(current['can_submit'])
        self.assertEqual(current['correction_reason'],'Add the missing site evidence.')
        self.assertEqual({p['id'] for p in current['photos']},set(self.ids))
        self.assertEqual({p['group'] for p in current['photos']},{'Civil','Electrical','Tower'})
        for photo in current['photos']:
            response=self.client.get(photo['original_url'])
            self.assertEqual(response.status_code,200)
            data=b''.join(response.streaming_content);response.close()
            self.assertEqual(data,self.originals[photo['id']])
        self.revision.refresh_from_db()
        self.assertEqual((self.revision.digest,self.revision.snapshot),(self.digest,self.snapshot))
        self.assertFalse(self.revision.processing_events.filter(
            action__in=['qa_complete','qa_answer','qa_link','technical_approve']).exists())

    def test_queued_unreviewed_submission_can_be_rejected_before_ai_or_checklist_review(self):
        self.assertEqual(self.revision.processing_job.status,'queued')
        self.assertFalse(self.revision.source_analyses.exists())
        self.assertTrue(category_intake.missing_for_review(self.checklist))
        context=route_context(self.quality,self.checklist)
        self.assertTrue(context['can_reject'])
        self.assertFalse(context['can_approve'])
        self.assertTrue(context['qa_review_required'])
        response=self.decision()
        self.assertEqual(response.status_code,200,response.content)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(response.json()['redirect_url'],self.return_to)
        self.assert_returned_with_originals()
        self.revision.processing_job.refresh_from_db()
        self.assertEqual(self.revision.processing_job.status,'queued')

    def test_active_ai_does_not_block_rejection_or_reset_completed_progress(self):
        job=self.revision.processing_job
        job.status='analysing_evidence';job.completed=1;job.total=3
        job.save(update_fields=['status','completed','total'])
        response=self.decision()
        self.assertEqual(response.status_code,200,response.content)
        self.assert_returned_with_originals()
        job.refresh_from_db()
        self.assertEqual((job.status,job.completed,job.total),('analysing_evidence',1,3))

    def test_completed_analysis_survives_return_and_unchanged_engineer_resubmission(self):
        photo=self.revision.snapshot['photos'][0]
        finding={'source_id':'photo:'+str(photo['id']),'reference':photo['filename'],
            'category':'equipment','component':'Synthetic cabinet','field_hint':'manufacturer',
            'value':'SYNTHETIC retained label','unit':'','basis':'recorded',
            'evidence_quote':'SYNTHETIC retained label','confidence':'high','notes':''}
        raw={'reference':photo['filename'],'findings':[finding]}
        source=SurveySourceAnalysis.objects.create(revision=self.revision,
            source_id=finding['source_id'],payload=raw,digest=pipeline.digest(raw))
        package=pipeline.prepare_checklist(self.revision.snapshot,
            {'findings':[finding],'missing':[],'conflicts':[]})
        saved=SurveyProcessingResult.objects.create(revision=self.revision,
            payload=package,digest=pipeline.digest(package))
        job=self.revision.processing_job;job.status='ready_for_review';job.completed=3;job.total=3
        job.save(update_fields=['status','completed','total'])
        response=self.decision()
        self.assertEqual(response.status_code,200,response.content)
        self.assert_returned_with_originals()
        resubmitted,digest=self.submit()
        self.assertEqual(resubmitted.status_code,201,resubmitted.content)
        latest=self.checklist.processing_revisions.get(pk=resubmitted.json()['revision_id'])
        self.assertEqual(latest.number,self.revision.number+1)
        self.assertEqual([p['id'] for p in latest.snapshot['photos']],self.ids)
        self.assertEqual(latest.snapshot['photos'],self.revision.snapshot['photos'])
        source.refresh_from_db();saved.refresh_from_db();job.refresh_from_db()
        self.assertEqual((source.payload,source.digest),(raw,pipeline.digest(raw)))
        self.assertEqual((saved.payload,saved.digest),(package,pipeline.digest(package)))
        self.assertEqual((job.status,job.completed),('ready_for_review',3))
        duplicate,_=self.submit(digest=digest)
        self.assertEqual(duplicate.status_code,200,duplicate.content)
        self.assertEqual(duplicate.json()['revision_id'],latest.pk)
        self.assertEqual(self.checklist.processing_revisions.count(),2)
        self.assertEqual(self.checklist.processing_revisions.filter(processing_job__isnull=False).count(),2)

    def test_missing_reason_and_stale_token_cannot_record_a_decision(self):
        before=self.checklist.review_route_record.events.count()
        empty=self.decision(reason='  ')
        self.assertEqual(empty.status_code,409,empty.content)
        self.assertFalse(empty.json()['ok'])
        stale=self.decision(token='stale-request')
        self.assertEqual(stale.status_code,409,stale.content)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage,'quality_engineer')
        self.assertEqual(self.checklist.review_route_record.events.count(),before)

    def test_unauthorised_roles_foreign_qa_and_missing_csrf_cannot_return_task(self):
        before=self.checklist.review_route_record.events.count()
        other=self.person('unnamed-return-qa',Profile.Roles.QUALITY_ENGINEER)
        foreign_project=Project.objects.create(name='Foreign return project',
            company=Company.objects.create(name='Foreign return company'))
        foreign=self.person('foreign-return-qa',Profile.Roles.QUALITY_ENGINEER,foreign_project)
        for actor in (self.engineer,self.lead,self.customer,self.admin,other,foreign):
            with self.subTest(role=actor.profile.role,user=actor.pk):
                denied=self.decision(actor)
                self.assertIn(denied.status_code,(403,404),denied.content)
        client=Client(enforce_csrf_checks=True);client.force_login(self.quality)
        self.assertEqual(client.post(self.url,{'action':'reject','reason':'No token'}).status_code,403)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage,'quality_engineer')
        self.assertEqual(self.checklist.review_route_record.events.count(),before)

    def test_repeated_rejection_does_not_duplicate_return_or_bypass_approval_requirements(self):
        # Rejection never needs individual photo review. Approval is a distinct
        # engineering signature and must not inherit a bypass from this UI rule.
        approval=self.decision(action='approve',reason='')
        self.assertEqual(approval.status_code,409,approval.content)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage,'quality_engineer')
        token=route_context(self.quality,self.checklist)['token']
        first=self.decision(token=token)
        self.assertEqual(first.status_code,200,first.content)
        second=self.decision(token=token)
        self.assertEqual(second.status_code,403,second.content)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage,'engineer')
        self.assertEqual(self.checklist.review_route_record.events.filter(action='reject').count(),1)
        self.assertFalse(self.revision.processing_events.filter(action='technical_approve').exists())
