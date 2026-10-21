"""Real saved-record upload recovery; no Ollama, private cache or network calls."""
import hashlib
import json
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import survey_processing as pipeline, survey_upload_sessions as uploads
from . import test_survey_processing as fixtures
from .models import Profile, ProjectMembership
from .survey_processing_models import SurveyUploadSession, SurveyUploadSessionEvent


@override_settings(SECRET_KEY='isolated-upload-recovery', ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class UploadSessionRecoveryTests(TestCase):
    setUp = fixtures.SurveyProcessingTests.setUp
    person = fixtures.SurveyProcessingTests.person
    request = fixtures.SurveyProcessingTests.request
    add_photo = fixtures.SurveyProcessingTests.add_photo

    def stale(self, session, **extra):
        SurveyUploadSession.objects.filter(pk=session.pk).update(
            heartbeat_at=timezone.now() - timedelta(minutes=20), **extra)
        session.refresh_from_db()

    def replace_engineer(self):
        replacement = self.person('replacement', Profile.Roles.ENGINEER)
        self.checklist.user = replacement
        self.checklist.save(update_fields=['user'])
        return replacement

    def test_reassigned_engineer_recovers_stale_session_then_submits_without_file_changes(self):
        session = uploads.start(self.request(), self.checklist.pk)
        before = {p.pk: hashlib.sha256(Path(p.original.path).read_bytes()).hexdigest() for p in (self.photo, self.photo2)}
        replacement = self.replace_engineer()
        with self.assertRaises(ValidationError):
            pipeline.submit(self.request(replacement), self.checklist.pk, True)
        with self.assertRaises((PermissionDenied, Http404)):
            uploads.finish(self.request(self.engineer), self.checklist.pk, session.token)
        with self.assertRaises(ValidationError):
            uploads.recover(self.request(replacement), self.checklist.pk, session.token, 'Previous Engineer was reassigned')
        self.stale(session)
        for _ in range(2):
            recovered = uploads.recover(self.request(replacement), self.checklist.pk, session.token,
                                        'Interrupted old Engineer upload; retained files checked')
            self.assertIsNotNone(recovered.finished_at)
        self.assertEqual(session.events.filter(action='recovered').count(), 1)
        recovered.refresh_from_db()
        self.assertEqual(recovered.recovered_by_id, replacement.pk)
        self.assertEqual(recovered.actor_id, self.engineer.pk)
        revision, created = pipeline.submit(self.request(replacement), self.checklist.pk, True)
        self.assertTrue(created)
        self.assertEqual(revision.snapshot['assigned_engineer_id'], replacement.pk)
        for photo in (self.photo, self.photo2):
            self.assertEqual(hashlib.sha256(Path(photo.original.path).read_bytes()).hexdigest(), before[photo.pk])

    def test_admin_recovers_inactive_actor_and_audit_is_append_only(self):
        session = uploads.start(self.request(), self.checklist.pk)
        self.engineer.is_active = False
        self.engineer.save(update_fields=['is_active'])
        self.stale(session)
        uploads.recover(self.request(self.admin), self.checklist.pk, session.token, 'Account deactivated during interrupted upload')
        event = session.events.get(action='recovered')
        self.assertEqual(event.actor_id, self.admin.pk)
        self.assertEqual(event.payload['previous_actor_id'], self.engineer.pk)
        with self.assertRaises(ValidationError):
            SurveyUploadSessionEvent.objects.filter(pk=event.pk).update(reason='tampered')
        with self.assertRaises(ValidationError):
            event.delete()

    def test_project_revocation_does_not_prevent_lead_from_recovering_abandoned_files(self):
        session = uploads.start(self.request(), self.checklist.pk)
        ProjectMembership.objects.create(user=self.engineer, project=self.project, is_active=False)
        self.stale(session)
        with self.assertRaises((Http404, PermissionDenied)):
            uploads.heartbeat(self.request(), self.checklist.pk, session.token)
        recovered = uploads.recover(self.request(self.lead), self.checklist.pk, session.token,
                                   'Project access revoked after interrupted upload')
        self.assertIsNotNone(recovered.finished_at)
        self.assertEqual(self.checklist.photo_evidence.count(), 2)

    def test_live_heartbeat_and_active_batch_protect_against_premature_recovery(self):
        session = uploads.start(self.request(), self.checklist.pk)
        self.stale(session)
        uploads.heartbeat(self.request(), self.checklist.pk, session.token)
        with self.assertRaises(ValidationError):
            uploads.recover(self.request(self.admin), self.checklist.pk, session.token, 'Cannot close a live browser upload')
        with uploads.upload_batch(self.request(), self.checklist.pk, session.token):
            self.stale(session)
            with self.assertRaises(ValidationError):
                uploads.recover(self.request(self.admin), self.checklist.pk, session.token, 'Cannot close an active transfer')
            with self.assertRaises(ValidationError):
                uploads.finish(self.request(), self.checklist.pk, session.token)
            session.refresh_from_db()
            old_lease = session.active_until
            uploads.heartbeat(self.request(), self.checklist.pk, session.token)
            session.refresh_from_db()
            self.assertGreaterEqual(session.active_until, old_lease)
        session.refresh_from_db()
        self.assertEqual(session.active_batches, 0)
        self.assertIsNone(session.active_until)

    def test_concurrent_batch_counter_keeps_other_transfer_protected(self):
        session = uploads.start(self.request(), self.checklist.pk)
        with uploads.upload_batch(self.request(), self.checklist.pk, session.token):
            with uploads.upload_batch(self.request(), self.checklist.pk, session.token):
                session.refresh_from_db()
                self.assertEqual(session.active_batches, 2)
            session.refresh_from_db()
            self.assertEqual(session.active_batches, 1)
            self.assertIsNotNone(session.active_until)
            uploads.interrupt(self.request(), self.checklist.pk, session.token)
            with self.assertRaises(ValidationError):
                uploads.recover(self.request(self.admin), self.checklist.pk, session.token, 'One transfer is still working')
        session.refresh_from_db()
        self.assertEqual(uploads.activity(session)[0], 'interrupted')
        uploads.recover(self.request(self.admin), self.checklist.pk, session.token, 'Both interrupted transfers have finished')

    def test_browser_closure_without_beacon_becomes_stale_not_silently_finished(self):
        session = uploads.start(self.request(), self.checklist.pk)
        self.stale(session)
        state = uploads.state(self.request(), self.checklist)
        self.assertEqual(state['inflight'], 1)
        self.assertEqual(state['sessions'][0]['status'], 'stale')
        self.assertTrue(state['sessions'][0]['recoverable'])
        self.assertIsNone(SurveyUploadSession.objects.get(pk=session.pk).finished_at)
        with self.assertRaises(ValidationError):
            pipeline.submit(self.request(), self.checklist.pk, True)

    def test_crashed_batch_expiry_allows_recovery_and_forbids_late_commit(self):
        session = uploads.start(self.request(), self.checklist.pk)
        self.stale(session, active_batches=1, active_until=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(ValidationError):
            with uploads.upload_batch(self.request(), self.checklist.pk, session.token):
                self.fail('A crashed envelope must not be resumed without explicit recovery')
        uploads.recover(self.request(self.admin), self.checklist.pk, session.token, 'Server process stopped during this transfer')
        with self.assertRaises(ValidationError):
            uploads.require_batch_open(self.checklist, session.token)
        self.assertEqual(self.checklist.photo_evidence.count(), 2)

    def test_explicit_interruption_recovery_and_normal_finish_are_idempotent(self):
        session = uploads.start(self.request(), self.checklist.pk)
        for _ in range(2):
            uploads.interrupt(self.request(), self.checklist.pk, session.token)
        self.assertEqual(session.events.filter(action='interrupted').count(), 1)
        uploads.recover(self.request(), self.checklist.pk, session.token, 'Browser upload was explicitly interrupted')
        for _ in range(2):
            uploads.finish(self.request(), self.checklist.pk, session.token)
        self.assertEqual(session.events.count(), 3)
        with self.assertRaises(ValidationError):
            uploads.heartbeat(self.request(), self.checklist.pk, session.token)
        with self.assertRaises(ValidationError):
            with uploads.upload_batch(self.request(), self.checklist.pk, session.token):
                self.fail('Closed sessions must not reopen')

    def test_recovery_requires_reason_and_an_authorised_project_role(self):
        session = uploads.start(self.request(), self.checklist.pk)
        self.stale(session)
        other_engineer = self.person('unassigned', Profile.Roles.ENGINEER)
        for actor in (self.customer, self.quality, other_engineer):
            with self.subTest(actor=actor.username), self.assertRaises((PermissionDenied, Http404)):
                uploads.recover(self.request(actor), self.checklist.pk, session.token, 'Unauthorised recovery must be denied')
        for reason in ('', 'bad', 'x' * 1001, None):
            with self.subTest(reason=reason), self.assertRaises(ValidationError):
                uploads.recover(self.request(self.admin), self.checklist.pk, session.token, reason)
        self.assertFalse(session.events.filter(action='recovered').exists())

    def test_unknown_and_foreign_tokens_are_scoped_and_do_not_close_another_session(self):
        session = uploads.start(self.request(), self.checklist.pk)
        for token in ('invalid', '00000000-0000-0000-0000-000000000000'):
            with self.subTest(token=token), self.assertRaises(Http404):
                uploads.recover(self.request(self.admin), self.checklist.pk, token, 'Unknown token must not resolve')
        self.assertIsNone(SurveyUploadSession.objects.get(pk=session.pk).finished_at)

    def test_batch_exception_closes_only_server_owned_envelope_and_preserves_existing_files(self):
        before = Path(self.photo.original.path).read_bytes()
        with self.assertRaisesRegex(ValueError, 'interrupted'):
            with uploads.upload_batch(self.request(), self.checklist.pk):
                raise ValueError('interrupted')
        session = self.checklist.survey_upload_sessions.get()
        self.assertIsNotNone(session.finished_at)
        self.assertEqual(session.active_batches, 0)
        self.assertEqual(Path(self.photo.original.path).read_bytes(), before)

    def test_photo_upload_session_api_supports_heartbeat_and_interrupt(self):
        self.client.force_login(self.engineer)
        url = reverse('photo_processing_upload_session', args=[self.checklist.pk])
        started = self.client.post(url, '{}', content_type='application/json')
        self.assertEqual(started.status_code, 200, started.content)
        token = started.json()['token']
        for action in ('heartbeat', 'interrupt'):
            response = self.client.post(url, json.dumps({'token': token, 'action': action}), content_type='application/json')
            self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(uploads.activity(SurveyUploadSession.objects.get(token=token))[0], 'interrupted')
