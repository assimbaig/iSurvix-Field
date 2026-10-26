"""Approval comments reuse frozen routes, signatures and the existing policy."""
from copy import deepcopy

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from . import test_review_route_service as route_fixture
from . import test_engineer_category_submission_acceptance as capture_fixture
from .models import Profile
from .review_route_service import act_on_route, route_context, route_for


@override_settings(SECRET_KEY='isolated-commented-approval',
    ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ApprovalCommentsTests(TestCase):
    setUp=route_fixture.ReviewRouteServiceTests.setUp
    person=route_fixture.ReviewRouteServiceTests.person
    configure=route_fixture.ReviewRouteServiceTests.configure
    submit=route_fixture.ReviewRouteServiceTests.submit
    act=route_fixture.ReviewRouteServiceTests.act

    def test_four_layer_comments_preserve_canonical_approval_and_each_human_note(self):
        self.configure();revision=self.submit();snapshot=deepcopy(revision.snapshot)
        for actor,note in [(self.quality,'QA checked the submitted source'),
                           (self.lead,'Team Lead approved the recorded scope'),
                           (self.customer,'Client accepts this submitted revision')]:
            with self.subTest(actor=actor.pk):
                context=route_context(actor,self.checklist)
                self.assertTrue(context['can_approve_with_comments'])
                event=self.act(actor,'approve_with_comments','  '+note+'  ')
                self.assertEqual(event.action,'approve')
                self.assertEqual(event.reason,note)
                self.assertTrue(revision.decisions.filter(actor=actor,reason=note).exists())
        self.assertEqual(route_for(self.checklist).stage,'closed')
        revision.refresh_from_db();self.assertEqual(revision.snapshot,snapshot)
        self.assertEqual(self.checklist.client_approval['decision'],'approved')
        self.assertEqual(self.checklist.client_approval['reference'],'Client accepts this submitted revision')

    def test_three_layers_close_after_named_team_lead_comment(self):
        self.configure(layers=3);self.submit()
        self.act(self.quality,'approve_with_comments','QA source checked')
        self.act(self.lead,'approve_with_comments','Scope accepted')
        self.assertEqual(route_for(self.checklist).stage,'closed')

    def test_commented_approval_requires_a_bounded_nonempty_comment_without_mutation(self):
        self.configure();self.submit()
        before=route_for(self.checklist).generation
        for note in ['', '   ', 'x'*4001, ['not a comment']]:
            with self.subTest(note_type=type(note).__name__):
                with self.assertRaisesMessage(ValidationError,'comments'):
                    self.act(self.quality,'approve_with_comments',note)
                self.assertEqual(route_for(self.checklist).generation,before)
                self.assertEqual(route_for(self.checklist).stage,'quality_engineer')

    def test_ordinary_approval_still_allows_an_empty_comment(self):
        self.configure();self.submit()
        event=self.act(self.quality,'approve','')
        self.assertEqual((event.action,event.reason),('approve',''))

    def test_comment_approval_does_not_grant_an_unnamed_reviewer_authority(self):
        self.configure();self.submit()
        other=self.person('other_qa_comment',Profile.Roles.QUALITY_ENGINEER)
        for actor in [self.engineer,self.lead,self.customer,other]:
            with self.subTest(actor=actor.pk):
                with self.assertRaises(PermissionDenied):self.act(actor,'approve_with_comments','Not my stage')
        self.assertEqual(route_for(self.checklist).stage,'quality_engineer')

    def test_comment_approval_rejects_stale_tokens_and_preserves_clarification_rules(self):
        self.configure();self.submit()
        stale=route_context(self.quality,self.checklist)['token']
        self.act(self.quality,'approve_with_comments','QA accepted')
        with self.assertRaises(ValidationError):
            act_on_route(self.lead,self.checklist,'approve_with_comments','Old token',stale)
        self.act(self.lead,'reject','QA must clarify this observation')
        with self.assertRaises(ValidationError):self.act(self.quality,'approve_with_comments','Cannot bypass clarification')


@override_settings(SECRET_KEY='isolated-guided-decision-roles',
    ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GuidedDecisionRoleTests(TestCase):
    setUp=capture_fixture.EngineerCategorySubmissionAcceptanceTests.setUp
    person=capture_fixture.EngineerCategorySubmissionAcceptanceTests.person
    add_photo=capture_fixture.EngineerCategorySubmissionAcceptanceTests.add_photo
    raw=capture_fixture.EngineerCategorySubmissionAcceptanceTests.raw
    post=capture_fixture.EngineerCategorySubmissionAcceptanceTests.post
    state=capture_fixture.EngineerCategorySubmissionAcceptanceTests.state
    upload=capture_fixture.EngineerCategorySubmissionAcceptanceTests.upload
    submit=capture_fixture.EngineerCategorySubmissionAcceptanceTests.submit
    qa_state=capture_fixture.EngineerCategorySubmissionAcceptanceTests.qa_state
    qa_action=capture_fixture.EngineerCategorySubmissionAcceptanceTests.qa_action
    route=capture_fixture.EngineerCategorySubmissionAcceptanceTests.route
    complete_qa_manually=capture_fixture.EngineerCategorySubmissionAcceptanceTests.complete_qa_manually

    def submitted(self):
        self.upload('Civil');result,_=self.submit();self.assertEqual(result.status_code,201,result.content)
        self.client.force_login(self.quality)

    def test_incomplete_qa_exposes_disabled_approval_reason_without_bypassing_completion(self):
        self.submitted();self.checklist.refresh_from_db()
        context=route_context(self.quality,self.checklist)
        self.assertTrue(context['can_attempt_approve'])
        self.assertFalse(context['can_approve_with_comments'])
        self.assertTrue(context['approval_block_reason'])
        result=self.route(self.quality,'approve_with_comments','A comment does not waive missing evidence')
        self.assertEqual(result.status_code,409,result.content)
        self.assertEqual(route_for(self.checklist).stage,'quality_engineer')

    def ready_for_lead(self):
        self.submitted();self.complete_qa_manually()
        self.assertEqual(self.route(self.quality,'approve','QA verified').status_code,302)
        self.client.force_login(self.lead)

    def test_team_lead_has_guided_decision_context_with_readonly_evidence(self):
        self.ready_for_lead()
        page=self.client.get(reverse('photo_workspace',args=[self.checklist.pk]))
        self.assertEqual(page.status_code,200,page.content)
        self.assertTrue(page.context['qa_quick_review'])
        self.assertFalse(page.context['is_quality_engineer'])
        self.assertTrue(page.context['review_route']['can_approve_with_comments'])
        state=self.client.get(reverse('photo_capture_review_state',args=[self.checklist.pk]))
        self.assertEqual(state.status_code,200,state.content)
        self.assertFalse(state.json()['can_review'])

    def test_team_lead_commented_decision_uses_confirmed_json_return(self):
        self.ready_for_lead();self.checklist.refresh_from_db()
        target=reverse('photo_workspace',args=[self.checklist.pk])+'?qa_step=decision'
        response=self.client.post(reverse('review_route_action',args=[self.checklist.pk]),
            {'action':'approve_with_comments','reason':'Scope accepted by Team Lead',
             'expected_token':route_context(self.lead,self.checklist)['token'],'return_to':target},
            HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.headers['Content-Type'],'application/json')
        self.assertEqual(response.json()['redirect_url'],target)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(route_for(self.checklist).stage,'client')
        event=route_for(self.checklist).events.order_by('-sequence').first()
        self.assertEqual((event.action,event.reason),('approve','Scope accepted by Team Lead'))

    def test_team_lead_failed_comment_keeps_route_and_returns_json_error(self):
        self.ready_for_lead();self.checklist.refresh_from_db()
        target=reverse('photo_workspace',args=[self.checklist.pk])+'?qa_step=decision'
        response=self.client.post(reverse('review_route_action',args=[self.checklist.pk]),
            {'action':'approve_with_comments','reason':' ',
             'expected_token':route_context(self.lead,self.checklist)['token'],'return_to':target},
            HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,409,response.content)
        self.assertEqual(response.headers['Content-Type'],'application/json')
        self.assertFalse(response.json()['ok'])
        self.assertEqual(route_for(self.checklist).stage,'team_lead')

    def test_named_team_lead_json_contract_does_not_allow_acting_before_qa(self):
        self.submitted();self.client.force_login(self.lead);self.checklist.refresh_from_db()
        before=route_for(self.checklist).events.count()
        target=reverse('photo_workspace',args=[self.checklist.pk])+'?qa_step=decision'
        response=self.client.post(reverse('review_route_action',args=[self.checklist.pk]),
            {'action':'approve_with_comments','reason':'Not yet my review stage',
             'expected_token':route_context(self.lead,self.checklist)['token'],'return_to':target},
            HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,403,response.content)
        self.assertFalse(response.json()['ok'])
        self.assertEqual(route_for(self.checklist).stage,'quality_engineer')
        self.assertEqual(route_for(self.checklist).events.count(),before)
