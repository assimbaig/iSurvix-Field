"""Independent negative cases derived from release-hardening requirements.

These use disposable real Django records and originals. They exercise HTTP/service
authorization and recovery rather than invoking native inference or customer data.
"""
import hashlib
import json
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from . import remote_worker_service as bridge, survey_processing as pipeline
from . import survey_upload_sessions as uploads, test_survey_processing as fixtures
from .models import Checklist, Profile
from .remote_worker_models import RemoteSurveyTask
from .survey_processing_models import SurveyProcessingJob, SurveyUploadSession


@override_settings(SECRET_KEY='independent-hardening-only', ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], OLLAMA_MODEL='qwen3.5:4b')
class IndependentReleaseHardeningTests(TestCase):
    setUp = fixtures.SurveyProcessingTests.setUp
    person = fixtures.SurveyProcessingTests.person
    request = fixtures.SurveyProcessingTests.request
    add_photo = fixtures.SurveyProcessingTests.add_photo
    analysed = fixtures.SurveyProcessingTests.analysed

    def remote(self):
        credential, token = bridge.provision(self.admin, [self.project.pk])
        revision, _ = pipeline.submit(self.request(), self.checklist.pk, True)
        job = bridge.claim(credential, {'versions': bridge.versions(), 'model': 'qwen3.5:4b', 'model_digest': 'c' * 64})
        task = bridge.next_task(credential, job['job_id'], job['lease'])
        client = Client(HTTP_AUTHORIZATION='Bearer ' + token, HTTP_X_WORKER_LEASE=job['lease'])
        return credential, token, revision, job, task, client

    def completion(self, task):
        return {'versions': bridge.versions(), 'input_digest': task['input_digest'],
                'result': self.analysed(task['input'], 'qwen3.5:4b')}

    def test_revoke_and_expiry_stop_heartbeat_image_next_and_result_delivery(self):
        credential, token, revision, job, task, client = self.remote()
        for invalidation in ('expired', 'revoked'):
            credential.expires_at = timezone.now() - timedelta(seconds=1) if invalidation == 'expired' else timezone.now() + timedelta(hours=1)
            credential.revoked_at = timezone.now() if invalidation == 'revoked' else None
            credential.save()
            cases = [
                ('post', reverse('remote_worker_heartbeat', args=[job['job_id']]), {}),
                ('post', reverse('remote_worker_next', args=[job['job_id']]), {}),
                ('get', reverse('remote_worker_image', args=[job['job_id'], task['task_id']]), None),
                ('post', reverse('remote_worker_complete', args=[job['job_id'], task['task_id']]), self.completion(task)),
            ]
            for method, url, data in cases:
                with self.subTest(invalidation=invalidation, url=url):
                    response = client.get(url) if method == 'get' else client.post(url, json.dumps(data), content_type='application/json')
                    self.assertEqual(response.status_code, 403)
                    self.assertNotIn(token.encode(), response.content)
            self.assertEqual(revision.source_analyses.count(), 0)
            self.assertEqual(RemoteSurveyTask.objects.get(pk=task['task_id']).completed_digest, '')

    def test_removing_project_grant_revokes_an_existing_lease_without_deleting_checkpoints(self):
        credential, _, revision, job, task, client = self.remote()
        bridge.complete_task(credential, job['job_id'], job['lease'], task['task_id'], self.completion(task))
        before = list(revision.source_analyses.values_list('pk', 'digest'))
        credential.projects.remove(self.project)
        for name in ('remote_worker_next', 'remote_worker_heartbeat'):
            response = client.post(reverse(name, args=[job['job_id']]), '{}', content_type='application/json')
            self.assertEqual(response.status_code, 403)
        self.assertEqual(list(revision.source_analyses.values_list('pk', 'digest')), before)

    def test_a_valid_worker_cannot_mix_tasks_from_two_authorised_jobs(self):
        credential, token, revision, first, task, _ = self.remote()
        second_checklist = Checklist.objects.create(project=self.project, user=self.engineer,
            quality_reviewer=self.quality, site_id='SYNTHETIC-SECOND-JOB',
            answer_data={'custom': {'contact': 'Second synthetic contact'}})
        image = Path(self.photo.original.path).read_bytes()
        from .models import PhotoEvidence
        second_photo = PhotoEvidence.objects.create(checklist=second_checklist, uploaded_by=self.engineer,
            filename='second.png', sha256=hashlib.sha256(image).hexdigest())
        second_photo.original.save('second.png', ContentFile(image))
        second_revision, _ = pipeline.submit(self.request(), second_checklist.pk, True)
        second = bridge.claim(credential, {'versions': bridge.versions(), 'model': 'qwen3.5:4b', 'model_digest': 'c' * 64})
        self.assertEqual(second['revision_id'], second_revision.pk)
        client = Client(HTTP_AUTHORIZATION='Bearer ' + token, HTTP_X_WORKER_LEASE=second['lease'])
        response = client.post(reverse('remote_worker_complete', args=[second['job_id'], task['task_id']]),
            json.dumps(self.completion(task)), content_type='application/json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(revision.source_analyses.count() + second_revision.source_analyses.count(), 0)

    def test_changed_worker_result_and_injected_approval_cannot_override_canonical_checkpoint(self):
        credential, _, revision, job, task, client = self.remote()
        payload = self.completion(task)
        payload['result'].update(approved=True, released=True, accepted=True, output_path='foreign/private.pdf')
        payload['result']['findings'][0].update(measured=True, verification_status='approved', source_id='photo:999999')
        url = reverse('remote_worker_complete', args=[job['job_id'], task['task_id']])
        self.assertEqual(client.post(url, json.dumps(payload), content_type='application/json').status_code, 200)
        saved = revision.source_analyses.get()
        self.assertNotIn('approved', saved.payload)
        self.assertNotIn('output_path', saved.payload)
        self.assertFalse(saved.payload['findings'][0]['measured'])
        self.assertEqual(saved.payload['findings'][0]['verification_status'], 'needs_review')
        self.assertEqual(saved.payload['findings'][0]['source_id'], task['input']['source_id'])
        payload['result']['findings'][0]['value'] = 'Conflicting replacement'
        self.assertEqual(client.post(url, json.dumps(payload), content_type='application/json').status_code, 409)
        saved.refresh_from_db()
        self.assertEqual(saved.payload['findings'][0]['value'], 'SyntheticCo')
        self.assertEqual(revision.source_analyses.count(), 1)

    def test_malformed_json_and_stale_software_return_controlled_errors_without_results(self):
        _, _, revision, job, task, client = self.remote()
        url = reverse('remote_worker_complete', args=[job['job_id'], task['task_id']])
        for raw in ('{', '[]', 'null', '{"versions": {}}'):
            response = client.post(url, raw, content_type='application/json')
            self.assertIn(response.status_code, (400, 409))
            self.assertIn('error', response.json())
        self.assertEqual(revision.source_analyses.count(), 0)

    def test_late_photo_transfer_cannot_commit_after_authorised_abandoned_session_recovery(self):
        session = uploads.start(self.request(), self.checklist.pk)
        before = {p.pk: hashlib.sha256(Path(p.original.path).read_bytes()).hexdigest() for p in (self.photo, self.photo2)}
        data = BytesIO()
        Image.new('RGB', (64, 48), 'purple').save(data, 'PNG')
        from .photo_service import prepare_image

        def interrupted(file):
            prepared = prepare_image(file)
            SurveyUploadSession.objects.filter(token=session.token).update(
                heartbeat_at=timezone.now() - timedelta(hours=1), active_until=timezone.now() - timedelta(seconds=1))
            uploads.recover(self.request(self.admin), self.checklist.pk, session.token,
                            'Transfer lease expired; preserve old evidence and close abandoned envelope')
            return prepared

        self.client.force_login(self.engineer)
        with patch('core.photo_views.prepare_image', side_effect=interrupted):
            response = self.client.post(reverse('photo_upload', args=[self.checklist.pk]),
                {'group': 'Civil', 'processing_upload_token': str(session.token),
                 'files': [SimpleUploadedFile('delayed.png', data.getvalue(), content_type='image/png')]})
        self.assertIn(response.status_code, (400, 409))
        self.assertEqual(self.checklist.photo_evidence.count(), 2)
        session.refresh_from_db()
        self.assertIsNotNone(session.finished_at)
        self.assertEqual(session.events.filter(action='recovered').count(), 1)
        for photo in (self.photo, self.photo2):
            self.assertEqual(hashlib.sha256(Path(photo.original.path).read_bytes()).hexdigest(), before[photo.pk])

    def test_expired_remote_lease_has_an_honest_connection_recovery_message(self):
        _, _, _, job, _, _ = self.remote()
        SurveyProcessingJob.objects.filter(pk=job['job_id']).update(lease_until=timezone.now() - timedelta(seconds=1))
        self.client.force_login(self.engineer)
        response = self.client.get(reverse('survey_processing_progress', args=[self.checklist.pk]))
        self.assertEqual(response.status_code,403)
        self.client.force_login(self.quality)
        response = self.client.get(reverse('survey_processing_progress', args=[self.checklist.pk]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        message = str(data.get('queue_message') or data.get('active', {}).get('message') or '').lower()
        self.assertIn('worker', message)
        self.assertTrue(any(word in message for word in ('offline', 'lost', 'expired', 'waiting', 'reconnect')),
                        'Expired PC ownership must not look like a healthy running analysis indefinitely.')
