"""Durable source-boundary controls; native model checks run separately."""
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import survey_processing as pipeline, test_survey_processing as fixture
from .survey_processing_models import SurveyProcessingJob, SurveyProcessingEvent
from . import test_remote_survey_worker as remote_fixture


@override_settings(SECRET_KEY='isolated-pause-tests', ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SurveyPauseTests(TestCase):
    setUp = fixture.SurveyProcessingTests.setUp
    person = fixture.SurveyProcessingTests.person
    request = fixture.SurveyProcessingTests.request
    add_photo = fixture.SurveyProcessingTests.add_photo
    analysed = fixture.SurveyProcessingTests.analysed
    processing = fixture.SurveyProcessingTests.processing

    def submitted(self):
        self.revision, _ = pipeline.submit(self.request(), self.checklist.pk, True)
        return self.revision

    def control(self, action, actor=None, signature=None):
        from .survey_pause import control
        return control(self.request(actor or self.quality), self.checklist.pk, self.revision.pk,
                       action, signature if signature is not None else self.revision.digest)

    def test_queued_pause_survives_worker_restart_and_resume_is_idempotent(self):
        self.submitted()
        snapshot = self.revision.snapshot
        self.control('pause_ai'); self.control('pause_ai')
        job = SurveyProcessingJob.objects.get(revision=self.revision)
        self.assertEqual(job.status, 'paused')
        with patch('core.photo_service.verify_vision') as model:
            self.assertIsNone(pipeline.claim())
            self.assertFalse(pipeline.process_next())
            model.assert_not_called()
        self.assertEqual(self.revision.processing_events.filter(action='pause_requested').count(), 1)
        self.control('resume_ai'); self.control('resume_ai')
        job.refresh_from_db(); self.assertEqual(job.status, 'queued')
        self.assertEqual(self.revision.processing_events.filter(action='resumed').count(), 1)
        self.assertEqual(self.revision.source_analyses.count(), 0)
        self.assertEqual(self.revision.snapshot, snapshot)

    def test_pause_during_inference_saves_current_source_and_resumes_only_missing_sources(self):
        self.submitted()
        def analyse(source, model, **kwargs):
            self.control('pause_ai')
            self.assertEqual(SurveyProcessingJob.objects.get(revision=self.revision).status, 'pausing')
            return self.analysed(source, model, **kwargs)
        stack, native, _ = self.processing(analyse=analyse)
        self.assertTrue(pipeline.process_next())
        job = SurveyProcessingJob.objects.get(revision=self.revision)
        self.assertEqual(job.status, 'paused', job.error)
        self.assertEqual((job.completed, self.revision.source_analyses.count(), native.call_count), (1, 1, 1))
        first = self.revision.source_analyses.get()
        stack.close()
        self.control('resume_ai')
        _, native2, _ = self.processing()
        self.assertTrue(pipeline.process_next())
        job.refresh_from_db(); self.assertEqual(job.status, 'ready_for_review', job.error)
        self.assertEqual(native2.call_count, 1)
        self.assertEqual(self.revision.source_analyses.get(pk=first.pk).digest, first.digest)
        self.assertEqual(self.revision.source_analyses.count(), 2)
        self.assertEqual(job.completed, 2)

    def test_expired_pausing_lease_becomes_paused_without_reclaim_or_inference(self):
        self.submitted()
        claimed = pipeline.claim()
        self.control('pause_ai')
        SurveyProcessingJob.objects.filter(pk=claimed.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        self.assertIsNone(pipeline.claim())
        claimed.refresh_from_db(); self.assertEqual(claimed.status, 'paused')
        self.assertEqual(claimed.lease_owner, '')

    def test_stale_inputs_wrong_roles_and_terminal_jobs_cannot_change_processing(self):
        self.submitted()
        with self.assertRaises(ValidationError): self.control('pause_ai', signature='stale')
        for actor in [self.lead, self.customer, self.admin]:
            with self.subTest(role=actor.profile.role), self.assertRaises((PermissionDenied, Http404)):
                self.control('pause_ai', actor=actor)
        SurveyProcessingJob.objects.filter(revision=self.revision).update(status='ready_for_review')
        with self.assertRaises(ValidationError): self.control('pause_ai')
        self.assertFalse(SurveyProcessingEvent.objects.filter(action='pause_requested').exists())

    def test_busy_model_cannot_requeue_a_pause_request(self):
        from .local_ai import InferenceBusy
        self.submitted()
        def busy(source, model, **kwargs):
            self.control('pause_ai')
            raise InferenceBusy('Controlled busy local inference')
        self.processing(analyse=busy)
        pipeline.process_next()
        job = SurveyProcessingJob.objects.get(revision=self.revision)
        self.assertEqual(job.status, 'paused', job.error)
        self.assertEqual(job.completed, 0)
        self.assertIsNone(pipeline.claim())

    def test_http_pause_progress_and_resume_use_persisted_job(self):
        self.submitted(); self.client.force_login(self.quality)
        url = reverse('survey_processing_action', args=[self.checklist.pk])
        payload = {'revision_id': self.revision.pk, 'expected_digest': self.revision.digest}
        response = self.client.post(url, {'action':'pause', **payload})
        self.assertEqual(response.status_code, 200, response.content)
        state = self.client.get(reverse('survey_processing_progress', args=[self.checklist.pk])).json()
        self.assertEqual(state['active']['status'], 'paused')
        self.assertTrue(state['active']['can_resume'])
        response = self.client.post(url, {'action':'resume', **payload})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(SurveyProcessingJob.objects.get(revision=self.revision).status, 'queued')

    def test_engineer_cannot_gain_ai_actions_through_legacy_or_new_processing_routes(self):
        self.submitted(); self.client.force_login(self.engineer)
        response = self.client.post(reverse('survey_processing_action', args=[self.checklist.pk]),
            {'action': 'pause', 'revision_id': self.revision.pk, 'expected_digest': self.revision.digest})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(SurveyProcessingJob.objects.get(revision=self.revision).status, 'queued')
        from .survey_pause import flags
        self.assertFalse(flags(self.request(self.engineer), self.checklist, self.revision)['can_pause'])
        with self.assertRaises(PermissionDenied): self.control('pause_ai', actor=self.engineer)

    def test_pause_at_final_status_transition_cannot_leave_an_ownerless_running_lease(self):
        self.submitted(); self.processing()
        original = pipeline.progress
        def racing(job, status=None, **values):
            if status == 'ready_for_review':
                self.control('pause_ai')
            return original(job, status, **values)
        with patch.object(pipeline, 'progress', side_effect=racing):
            self.assertTrue(pipeline.process_next())
        job = SurveyProcessingJob.objects.get(revision=self.revision)
        self.assertEqual(job.status, 'paused')
        self.assertIsNone(job.lease_until)
        self.assertEqual(job.lease_owner, '')
        self.assertEqual(job.completed, 2)
        self.assertEqual(self.revision.source_analyses.count(), 2)

    def test_paused_revision_blocks_changed_input_submission_and_revoked_actor(self):
        self.submitted(); self.control('pause_ai')
        self.checklist.answer_data = {'custom': {'contact': 'Changed submission'}}
        self.checklist.save(update_fields=['answer_data'])
        with self.assertRaises(ValidationError):
            pipeline.submit(self.request(), self.checklist.pk, True)
        with self.assertRaises(ValidationError): self.control('resume_ai')
        self.checklist.answer_data = {'custom': {'contact': 'Synthetic contact'}}
        self.checklist.save(update_fields=['answer_data'])
        self.quality.is_active = False; self.quality.save(update_fields=['is_active'])
        with self.assertRaises((Http404, PermissionDenied)): self.control('resume_ai')
        self.assertEqual(SurveyProcessingJob.objects.get(revision=self.revision).status, 'paused')


@override_settings(**remote_fixture.SETTINGS)
class RemotePauseTests(remote_fixture.Fixtures, TestCase):
    def pause(self):
        from .survey_pause import control
        control(self.request(self.quality), self.checklist.pk, self.revision.pk,
                'pause_ai', self.revision.digest)

    def test_remote_inflight_source_is_retained_and_next_task_acknowledges_pause(self):
        bridge = remote_fixture.bridge
        claimed = self.claim()
        task = bridge.next_task(self.credential, claimed['job_id'], claimed['lease'])
        self.pause()
        heartbeat = bridge.heartbeat(self.credential, claimed['job_id'], claimed['lease'])
        self.assertEqual(heartbeat['status'], 'pausing')
        self.complete(claimed, task)
        saved = self.revision.source_analyses.get()
        stop = bridge.next_task(self.credential, claimed['job_id'], claimed['lease'])
        self.assertEqual(stop, {'complete': True, 'status': 'paused'})
        self.assertIsNone(self.claim())
        from .survey_pause import control
        control(self.request(self.quality), self.checklist.pk, self.revision.pk,
                'resume_ai', self.revision.digest)
        resumed = self.claim()
        next_task = bridge.next_task(self.credential, resumed['job_id'], resumed['lease'])
        self.assertNotEqual(next_task['task_id'], task['task_id'])
        self.assertEqual(self.revision.source_analyses.get(pk=saved.pk).digest, saved.digest)

    def test_remote_interruption_or_busy_cannot_erase_pause(self):
        bridge = remote_fixture.bridge
        claimed = self.claim()
        self.pause()
        result = bridge.fail(self.credential, claimed['job_id'], claimed['lease'], 'local_busy', retryable=True)
        self.assertEqual(result['status'], 'paused')
        self.assertIsNone(self.claim())

    def test_remote_expired_pausing_job_stays_stopped_after_pc_restart(self):
        claimed = self.claim()
        self.pause()
        SurveyProcessingJob.objects.filter(pk=claimed['job_id']).update(lease_until=timezone.now()-timedelta(seconds=1))
        self.assertIsNone(self.claim())
        job = SurveyProcessingJob.objects.get(pk=claimed['job_id'])
        self.assertEqual(job.status, 'paused')
