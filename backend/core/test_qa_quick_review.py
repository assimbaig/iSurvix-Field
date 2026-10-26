"""Guided QA navigation reuses current records, tokens and approval rules."""
from copy import deepcopy
from unittest.mock import patch
from django.db import OperationalError
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from . import test_engineer_category_submission_acceptance as fixture
from .models import Checklist
from .review_route_service import route_context
from .survey_processing_models import SurveyProcessingJob


@override_settings(SECRET_KEY='isolated-qa-quick-review',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QAQuickReviewTests(TestCase):
    setUp=fixture.EngineerCategorySubmissionAcceptanceTests.setUp
    person=fixture.EngineerCategorySubmissionAcceptanceTests.person
    add_photo=fixture.EngineerCategorySubmissionAcceptanceTests.add_photo
    raw=fixture.EngineerCategorySubmissionAcceptanceTests.raw
    post=fixture.EngineerCategorySubmissionAcceptanceTests.post
    upload=fixture.EngineerCategorySubmissionAcceptanceTests.upload
    state=fixture.EngineerCategorySubmissionAcceptanceTests.state
    submit=fixture.EngineerCategorySubmissionAcceptanceTests.submit
    qa_state=fixture.EngineerCategorySubmissionAcceptanceTests.qa_state
    qa_action=fixture.EngineerCategorySubmissionAcceptanceTests.qa_action
    route=fixture.EngineerCategorySubmissionAcceptanceTests.route
    complete_qa_manually=fixture.EngineerCategorySubmissionAcceptanceTests.complete_qa_manually

    def submitted(self):
        self.upload('Civil');response,_=self.submit()
        self.assertEqual(response.status_code,201,response.content)
        self.revision=self.checklist.processing_revisions.get()
        self.client.force_login(self.quality)

    def workbench(self):
        response=self.client.get(reverse('photo_workspace',args=[self.checklist.pk]))
        self.assertEqual(response.status_code,200,response.content)
        return response

    def decision(self,action,*,target=None,token=None,reason='Source evidence needs a clearer recorded observation.',**headers):
        self.checklist.refresh_from_db()
        return self.client.post(reverse('review_route_action',args=[self.checklist.pk]),{
            'action':action,'reason':reason,'expected_token':token or route_context(self.quality,self.checklist)['token'],
            'return_to':target if target is not None else reverse('photo_workspace',args=[self.checklist.pk])+'?qa_step=decision'},**headers)

    def test_qa_default_home_enters_reviews_but_explicit_views_and_other_roles_stay_intact(self):
        self.client.force_login(self.quality)
        response=self.client.get(reverse('governance_home'))
        self.assertRedirects(response,reverse('task_explorer'),fetch_redirect_response=False)
        for view in ['my_work','projects','reports','reviews']:
            response=self.client.get(reverse('governance_home'),{'view':view})
            self.assertEqual(response.status_code,200,(view,response.content))
        self.assertEqual(self.client.get(reverse('governance_home'),{'project':999999}).status_code,404)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('governance_home')).status_code,200)

    def test_task_entry_uses_evidence_and_decision_preserving_existing_filters(self):
        self.submitted()
        response=self.client.get(reverse('task_explorer'),{'q':self.checklist.site_id,'project':self.project.pk})
        self.assertEqual(response.status_code,200,response.content)
        self.assertTrue(response.context['is_quality_engineer'])
        row=next(row for row in response.context['page_obj'] if row['task_pk']==self.checklist.pk)
        self.assertTrue(row['url'].startswith(reverse('photo_workspace',args=[self.checklist.pk])+'?'))
        self.assertIn('return_to=',row['url'])
        self.assertIn('qa_step=decision',row['review_url'])
        self.assertIn('return_to=',row['review_url'])

    def test_workspace_exposes_real_rejection_but_keeps_approval_blocked_until_completion(self):
        self.submitted();before=deepcopy(self.revision.snapshot)
        page=self.workbench()
        self.assertTrue(page.context['qa_quick_review'])
        self.assertTrue(page.context['review_route']['can_reject'])
        self.assertFalse(page.context['review_route']['can_approve'])
        self.assertTrue(page.context['review_route']['qa_review_required'])
        self.assertEqual(self.decision('approve').status_code,409)
        self.revision.refresh_from_db();self.assertEqual(self.revision.snapshot,before)
        self.assertEqual(self.revision.processing_job.status,'queued')

    def test_completed_review_approves_through_existing_endpoint_and_returns_to_guided_workspace(self):
        self.submitted();before=deepcopy(self.revision.snapshot)
        self.complete_qa_manually();self.client.force_login(self.quality)
        page=self.workbench();self.assertTrue(page.context['review_route']['can_approve'])
        result=self.decision('approve')
        expected=reverse('photo_workspace',args=[self.checklist.pk])+'?qa_step=decision'
        self.assertRedirects(result,expected,fetch_redirect_response=False)
        page=self.client.get(expected)
        self.assertContains(page,'Team Lead')
        self.assertTrue(any('Team Lead' in str(message) for message in page.context['messages']))
        self.checklist.refresh_from_db();self.assertEqual(self.checklist.review_route_record.stage,'team_lead')
        self.revision.refresh_from_db();self.assertEqual(self.revision.snapshot,before)
        self.assertEqual(self.revision.processing_job.status,'queued')

    def test_rejection_remains_available_early_and_returns_engineer_without_losing_originals(self):
        self.submitted();count=self.checklist.photo_evidence.count();before=deepcopy(self.revision.snapshot)
        result=self.decision('reject')
        self.assertRedirects(result,reverse('photo_workspace',args=[self.checklist.pk])+'?qa_step=decision',fetch_redirect_response=False)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status,Checklist.Status.REJECTED)
        self.assertEqual(self.checklist.review_route_record.stage,'engineer')
        self.assertEqual(self.checklist.photo_evidence.count(),count)
        self.revision.refresh_from_db();self.assertEqual(self.revision.snapshot,before)
        self.assertFalse(self.workbench().context['review_route']['can_act'])

    def test_external_or_other_record_return_target_cannot_redirect_away(self):
        self.submitted()
        result=self.decision('reject',target='https://external.invalid/private')
        self.assertRedirects(result,reverse('roadmap_activity',args=[self.checklist.pk]),fetch_redirect_response=False)
        self.assertNotIn('external.invalid',result['Location'])

    def test_stale_wrong_role_foreign_record_and_csrf_remain_denied(self):
        self.submitted()
        self.assertEqual(self.decision('reject',token='stale').status_code,409)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.quality)
        self.assertEqual(strict.post(reverse('review_route_action',args=[self.checklist.pk]),{'action':'reject'}).status_code,403)
        self.client.force_login(self.lead)
        self.assertEqual(self.decision('reject').status_code,403)
        self.client.force_login(self.quality)
        other=self.person('unassigned_qa',self.quality.profile.role)
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('photo_workspace',args=[self.checklist.pk])).status_code,404)
        self.assertEqual(self.decision('reject').status_code,404)

    def test_unmarked_inspection_keeps_existing_workflow_and_honest_legacy_links(self):
        self.project.review_layers=None;self.project.save(update_fields=['review_layers'])
        inspection=Checklist.objects.create(project=self.project,user=self.engineer,quality_reviewer=self.quality,
            site_id='SYNTHETIC-LEGACY-INSPECTION',workflow_type=Checklist.WorkflowType.TELECOM_INSPECTION)
        self.client.force_login(self.quality)
        before=SurveyProcessingJob.objects.count()
        response=self.client.get(reverse('photo_workspace',args=[inspection.pk]))
        self.assertEqual(response.status_code,200,response.content)
        self.assertTrue(response.context['qa_legacy_fallback'])
        self.assertFalse(response.context['qa_quick_review'])
        self.assertEqual(response.context['qa_legacy_decision_url'],reverse('custom_checklist',args=[inspection.pk]))
        inspection.refresh_from_db();self.assertNotIn('category_intake_version',inspection.intake_metadata)
        self.assertEqual(SurveyProcessingJob.objects.count(),before)

    def test_json_qa_decision_success_uses_same_route_and_preserves_feedback(self):
        self.submitted();self.complete_qa_manually();self.client.force_login(self.quality)
        response=self.decision('approve',HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,200,response.content)
        data=response.json();self.assertTrue(data['ok']);self.assertIn('Team Lead',data['message'])
        target=reverse('photo_workspace',args=[self.checklist.pk])+'?qa_step=decision'
        self.assertEqual(data['redirect_url'],target)
        page=self.client.get(target);self.assertContains(page,data['message'])
        self.checklist.refresh_from_db();self.assertEqual(self.checklist.review_route_record.stage,'team_lead')

    def test_json_stale_decision_is_409_without_mutation_or_navigation(self):
        self.submitted();before=self.checklist.review_route_record.events.count()
        response=self.decision('reject',token='stale',HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,409,response.content)
        self.assertFalse(response.json()['ok']);self.assertIn('Reload',response.json()['error'])
        self.assertNotIn('redirect_url',response.json())
        self.assertEqual(self.checklist.review_route_record.events.count(),before)

    def test_json_save_failure_rolls_back_and_returns_retryable_feedback(self):
        self.submitted();before=self.checklist.review_route_record.events.count()
        with patch('core.review_route_service._event',side_effect=OperationalError('PRIVATE_DATABASE_DETAILS')):
            response=self.decision('reject',HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,503,response.content)
        self.assertFalse(response.json()['ok']);self.assertIn('retry',response.json()['error'].lower())
        self.assertNotIn(b'PRIVATE_DATABASE_DETAILS',response.content)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status,Checklist.Status.SUBMITTED)
        self.assertEqual(self.checklist.review_route_record.stage,'quality_engineer')
        self.assertEqual(self.checklist.review_route_record.events.count(),before)

    def test_json_header_does_not_enable_new_contract_for_wrong_role_or_invalid_target(self):
        # Named Team Leads now share the guided response contract. Engineers
        # remain outside it and cannot gain reviewer authority via Accept.
        self.submitted();self.client.force_login(self.engineer)
        wrong=self.decision('reject',HTTP_ACCEPT='application/json')
        self.assertEqual(wrong.status_code,403)
        self.assertNotIn('application/json',wrong['Content-Type'])
        self.client.force_login(self.quality)
        invalid=self.decision('reject',target='https://external.invalid',HTTP_ACCEPT='application/json')
        self.assertRedirects(invalid,reverse('roadmap_activity',args=[self.checklist.pk]),fetch_redirect_response=False)
