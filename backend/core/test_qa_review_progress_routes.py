"""The real QA page routes light progress separately from checklist/evidence."""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from . import test_engineer_category_submission_acceptance as fixture


@override_settings(SECRET_KEY='isolated-qa-progress-route',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QAReviewProgressRouteTests(TestCase):
    setUp=fixture.EngineerCategorySubmissionAcceptanceTests.setUp
    person=fixture.EngineerCategorySubmissionAcceptanceTests.person
    add_photo=fixture.EngineerCategorySubmissionAcceptanceTests.add_photo
    post=fixture.EngineerCategorySubmissionAcceptanceTests.post
    raw=fixture.EngineerCategorySubmissionAcceptanceTests.raw
    state=fixture.EngineerCategorySubmissionAcceptanceTests.state
    upload=fixture.EngineerCategorySubmissionAcceptanceTests.upload
    submit=fixture.EngineerCategorySubmissionAcceptanceTests.submit
    qa_state=fixture.EngineerCategorySubmissionAcceptanceTests.qa_state

    def submitted(self):
        self.upload('Civil');response,_=self.submit()
        self.assertEqual(response.status_code,201,response.content)
        self.client.force_login(self.quality)
        return self.checklist.processing_revisions.get()

    def test_page_and_saved_state_expose_the_same_lightweight_route_and_detail_token(self):
        revision=self.submitted()
        url=reverse('photo_capture_review_progress',args=[self.checklist.pk])
        page=self.client.get(reverse('photo_workspace',args=[self.checklist.pk]))
        self.assertEqual(page.status_code,200,page.content)
        self.assertEqual(page.context['review_progress_url'],url)
        state=self.qa_state()
        self.assertIsInstance(state['progress_token'],str)
        with patch('core.category_intake.review_state',side_effect=AssertionError('Progress must not serialize full review state')):
            response=self.client.get(url)
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response['Cache-Control'],'private, no-store')
        data=response.json();self.assertEqual(data['revision_id'],revision.pk)
        self.assertEqual(data['progress_token'],state['progress_token'])
        self.assertEqual(data['ai']['status'],'queued')
        for heavy in ['photos','items','matching_history','general_information','site_information_table','documents']:
            self.assertNotIn(heavy,data)
        self.assertLess(len(response.content),8000)

    def test_progress_endpoint_remains_quality_only_and_does_not_allow_post(self):
        self.submitted();url=reverse('photo_capture_review_progress',args=[self.checklist.pk])
        self.assertEqual(self.client.post(url,{}).status_code,405)
        for actor in [self.engineer,self.lead,self.customer]:
            self.client.force_login(actor)
            response=self.client.get(url)
            self.assertIn(response.status_code,(403,404),response.content)
