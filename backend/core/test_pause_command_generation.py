"""Pause/resume requests are bound to the human control state they observed."""
from django.test import TestCase, override_settings
from django.urls import reverse

from . import (survey_processing as pipeline, test_survey_pause as fixture,
    test_qa_matching_backend as category_fixture)
from .survey_processing_models import SurveyProcessingEvent, SurveyProcessingJob


@override_settings(SECRET_KEY='isolated-pause-command-generation',
    ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PauseCommandGenerationTests(TestCase):
    setUp = fixture.SurveyPauseTests.setUp
    person = fixture.SurveyPauseTests.person
    request = fixture.SurveyPauseTests.request
    add_photo = fixture.SurveyPauseTests.add_photo
    submitted = fixture.SurveyPauseTests.submitted

    def token(self):
        data = self.client.get(reverse('survey_processing_progress',
            args=[self.checklist.pk])).json()
        return data['active'].get('control_token')

    def send(self, action, token):
        return self.client.post(reverse('survey_processing_action', args=[self.checklist.pk]),
            {'action': action, 'revision_id': self.revision.pk,
             'expected_digest': self.revision.digest,
             'expected_control_token': token or ''})

    def begin(self):
        self.submitted()
        self.client.force_login(self.quality)

    def test_old_resume_cannot_undo_a_newer_pause(self):
        self.begin()
        self.assertEqual(self.send('pause', self.token()).status_code, 200)
        old_resume = self.token()
        self.assertEqual(self.send('resume', old_resume).status_code, 200)
        self.assertEqual(self.send('pause', self.token()).status_code, 200)
        before = list(self.revision.processing_events.values_list('pk', flat=True))
        result = self.send('resume', old_resume)
        self.assertEqual(result.status_code, 409, result.content)
        self.assertEqual(SurveyProcessingJob.objects.get(revision=self.revision).status, 'paused')
        self.assertEqual(list(self.revision.processing_events.values_list('pk', flat=True)), before)

    def test_old_pause_cannot_stop_a_later_resumed_job(self):
        self.begin()
        old_pause = self.token()
        self.assertEqual(self.send('pause', old_pause).status_code, 200)
        self.assertEqual(self.send('resume', self.token()).status_code, 200)
        result = self.send('pause', old_pause)
        self.assertEqual(result.status_code, 409, result.content)
        self.assertEqual(SurveyProcessingJob.objects.get(revision=self.revision).status, 'queued')

    def test_same_resume_retry_does_not_reset_a_claimed_live_lease(self):
        self.begin()
        self.assertEqual(self.send('pause', self.token()).status_code, 200)
        resume = self.token()
        self.assertEqual(self.send('resume', resume).status_code, 200)
        job = pipeline.claim()
        before = (job.status, job.lease_owner, job.lease_until, job.attempts)
        self.assertEqual(self.send('resume', resume).status_code, 200)
        job.refresh_from_db()
        self.assertEqual((job.status, job.lease_owner, job.lease_until, job.attempts), before)
        self.assertEqual(self.revision.processing_events.filter(action='resumed').count(), 1)

    def test_duplicate_pause_records_only_one_control_event(self):
        self.begin()
        pause = self.token()
        self.assertEqual(self.send('pause', pause).status_code, 200)
        self.assertEqual(self.send('pause', pause).status_code, 200)
        self.assertEqual(self.revision.processing_events.filter(action='pause_requested').count(), 1)

    def test_missing_or_forged_token_cannot_change_processing(self):
        self.begin()
        missing = self.client.post(reverse('survey_processing_action', args=[self.checklist.pk]),
            {'action': 'pause', 'revision_id': self.revision.pk,
             'expected_digest': self.revision.digest})
        self.assertEqual(missing.status_code, 409, missing.content)
        for token in ['', 'forged-control-generation']:
            with self.subTest(token=token):
                result = self.send('pause', token)
                self.assertEqual(result.status_code, 409, result.content)
        self.assertEqual(SurveyProcessingJob.objects.get(revision=self.revision).status, 'queued')
        self.assertFalse(self.revision.processing_events.filter(action='pause_requested').exists())

    def test_worker_progress_and_unrelated_events_do_not_invalidate_current_control(self):
        self.begin()
        pause = self.token()
        job = pipeline.claim()
        pipeline.progress(job, completed=1, total=2)
        SurveyProcessingEvent.objects.create(revision=self.revision, actor=self.quality,
            action='independent_review_note', payload={'note': 'No processing intent changed.'})
        self.assertEqual(self.send('pause', pause).status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, 'pausing')
        self.assertEqual(job.completed, 1)


@override_settings(SECRET_KEY='isolated-category-pause-command-generation',
    ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CategoryPauseCommandGenerationTests(TestCase):
    setUp = category_fixture.QAMatchingBackendTests.setUp
    person = category_fixture.QAMatchingBackendTests.person
    add_photo = category_fixture.QAMatchingBackendTests.add_photo
    post = category_fixture.QAMatchingBackendTests.post
    state = category_fixture.QAMatchingBackendTests.state
    raw = category_fixture.QAMatchingBackendTests.raw
    upload = category_fixture.QAMatchingBackendTests.upload
    submit = category_fixture.QAMatchingBackendTests.submit
    assert_submitted = category_fixture.QAMatchingBackendTests.assert_submitted
    qa_state = category_fixture.QAMatchingBackendTests.qa_state

    def send(self, action, token):
        state = self.qa_state()
        return self.post('photo_capture_review_action', {'action': action,
            'revision_id': state['revision_id'], 'source_digest': state['source_digest'],
            'expected_review_digest': state['review_digest'], 'expected_control_token': token})

    def test_category_review_rejects_old_resume_after_newer_pause(self):
        state = self.qa_state()
        self.assertIsInstance(state['ai']['control_token'], str)
        paused = self.send('pause_ai', state['ai']['control_token'])
        self.assertEqual(paused.status_code, 200, paused.content)
        old_resume = paused.json()['ai']['control_token']
        resumed = self.send('resume_ai', old_resume)
        self.assertEqual(resumed.status_code, 200, resumed.content)
        paused_again = self.send('pause_ai', resumed.json()['ai']['control_token'])
        self.assertEqual(paused_again.status_code, 200, paused_again.content)
        stale = self.send('resume_ai', old_resume)
        self.assertEqual(stale.status_code, 409, stale.content)
        self.assertEqual(SurveyProcessingJob.objects.get(revision=self.revision).status, 'paused')

    def test_scalar_qa_tick_and_legacy_details_share_the_current_control_generation(self):
        from types import SimpleNamespace
        from .qa_review_progress import progress
        state = self.qa_state()
        tick = progress(SimpleNamespace(user=self.quality, GET={}), self.checklist.pk)
        self.assertEqual(tick['ai']['control_token'], state['ai']['control_token'])
        details = self.client.get(reverse('survey_processing_progress',
            args=[self.checklist.pk])).json()
        self.assertEqual(details['active']['control_token'], state['ai']['control_token'])
        paused = self.send('pause_ai', tick['ai']['control_token'])
        self.assertEqual(paused.status_code, 200, paused.content)
        updated = progress(SimpleNamespace(user=self.quality, GET={}), self.checklist.pk)
        self.assertNotEqual(updated['ai']['control_token'], tick['ai']['control_token'])
        self.assertTrue(updated['ai']['can_resume'])
