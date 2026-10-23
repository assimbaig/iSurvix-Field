"""Deterministic bridge tests. Native Ollama benchmarks are explicitly separate.

The HTTP integration uses a real disposable Django WSGI server, DB, media store,
normalized image transfer, immutable results and actual PDF/DXF renderer. Only the
local inference boundary is controlled; no user model/cache/network is required.
"""
import base64
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from contextlib import nullcontext
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command, CommandError
from django.test import Client, LiveServerTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import remote_worker_service as bridge, survey_processing as pipeline
from . import test_survey_processing as fixtures
from .models import Checklist, Company, GovernanceAudit, Profile, Project
from .remote_worker_client import RemoteSurveyClient, WorkerAccessError, WorkerConnectionError
from .remote_worker_models import RemoteWorkerCredential, RemoteSurveyLease, RemoteSurveyTask
from .survey_processing_models import SurveyDrawingSet, SurveyProcessingJob, SurveyProcessingResult, SurveySourceAnalysis

SETTINGS = {'SECRET_KEY': 'isolated-remote-worker-tests', 'ROOT_URLCONF': 'checklist.urls_local',
    'ALLOWED_HOSTS': ['testserver', 'localhost', '127.0.0.1'], 'SECURE_SSL_REDIRECT': False,
    'PASSWORD_HASHERS': ['django.contrib.auth.hashers.MD5PasswordHasher'], 'OLLAMA_MODEL': 'qwen3.5:4b'}


class Fixtures:
    person = fixtures.SurveyProcessingTests.person
    request = fixtures.SurveyProcessingTests.request
    add_photo = fixtures.SurveyProcessingTests.add_photo
    analysed = fixtures.SurveyProcessingTests.analysed

    def setUp(self):
        fixtures.SurveyProcessingTests.setUp(self)
        self.credential, self.token = bridge.provision(self.admin, [self.project.pk])
        self.revision, _ = pipeline.submit(self.request(), self.checklist.pk, True)
        self.identity = {'versions': bridge.versions(), 'model': 'qwen3.5:4b', 'model_digest': 'd' * 64}

    def claim(self):
        return bridge.claim(self.credential, self.identity)

    def complete(self, job, task, result=None):
        result = result or self.analysed(task['input'], 'qwen3.5:4b')
        return bridge.complete_task(self.credential, job['job_id'], job['lease'], task['task_id'],
            {'versions': bridge.versions(), 'input_digest': task['input_digest'], 'result': result})


@override_settings(**SETTINGS)
class RemoteSurveyWorkerTests(Fixtures, TestCase):
    def test_windows_and_linux_checkout_line_endings_are_compatible(self):
        expected = bridge.versions()
        read_bytes = Path.read_bytes
        with patch.object(Path, 'read_bytes', lambda path: read_bytes(path).replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')):
            self.assertEqual(bridge.versions(), expected)

    def test_scoped_token_hash_expiry_and_admin_only_provisioning(self):
        self.assertNotIn(self.token, self.credential.secret_hash)
        self.assertEqual(bridge.authenticate(self.token).pk, self.credential.pk)
        self.assertTrue(GovernanceAudit.objects.filter(action='remote_worker.provisioned', project=self.project).exists())
        for actor in [self.engineer, self.quality, self.lead, self.customer]:
            with self.subTest(role=actor.profile.role), self.assertRaises(PermissionDenied):
                bridge.provision(actor, [self.project.pk])
        self.credential.expires_at = timezone.now() - timedelta(seconds=1)
        self.credential.save()
        with self.assertRaises(PermissionDenied):
            bridge.authenticate(self.token)

    def test_revoked_credential_and_inactive_admin_cannot_poll_or_download(self):
        job = self.claim()
        task = bridge.next_task(self.credential, job['job_id'], job['lease'])
        bridge.revoke(self.admin, self.credential.pk)
        client = Client(HTTP_AUTHORIZATION='Bearer ' + self.token, HTTP_X_WORKER_LEASE=job['lease'])
        for endpoint in [reverse('remote_worker_claim'), reverse('remote_worker_image', args=[job['job_id'], task['task_id']])]:
            response = client.get(endpoint)
            self.assertEqual(response.status_code, 403)
            self.assertNotIn(self.token.encode(), response.content)
        self.credential.revoked_at = None
        self.credential.save()
        self.admin.is_active = False
        self.admin.save()
        with self.assertRaises(PermissionDenied):
            bridge.authenticate(self.token)

    def test_anonymous_session_login_and_wrong_scope_never_authorise_machine_inputs(self):
        job = self.claim()
        task = bridge.next_task(self.credential, job['job_id'], job['lease'])
        url = reverse('remote_worker_image', args=[job['job_id'], task['task_id']])
        client = Client()
        self.assertEqual(client.get(url).status_code, 403)
        client.force_login(self.admin)
        self.assertEqual(client.get(url).status_code, 403)
        company = Company.objects.create(name='Foreign remote company')
        project = Project.objects.create(name='Foreign remote project', company=company)
        other_admin = self.person('foreign_admin', Profile.Roles.ADMIN, project)
        project.administrator = other_admin
        project.save()
        other_credential, other_token = bridge.provision(other_admin, [project.pk])
        self.assertIsNone(bridge.claim(other_credential, self.identity))
        response = client.get(url, HTTP_AUTHORIZATION='Bearer ' + other_token, HTTP_X_WORKER_LEASE=job['lease'])
        self.assertEqual(response.status_code, 403)

    def test_offline_pc_keeps_job_queued_and_local_worker_does_not_consume_it(self):
        self.assertIsNone(pipeline.claim())
        self.revision.processing_job.refresh_from_db()
        self.assertEqual(self.revision.processing_job.status, 'queued')
        self.assertEqual(self.revision.processing_job.attempts, 0)
        client = Client()
        client.force_login(self.engineer)
        self.assertRedirects(client.get(reverse('survey_processing_workspace', args=[self.checklist.pk])),
            reverse('photo_workspace',args=[self.checklist.pk]),fetch_redirect_response=False)

    def test_stale_versions_and_wrong_model_do_not_claim_job(self):
        for values in [{**self.identity, 'versions': {'protocol': 'old'}}, {**self.identity, 'model': 'not-installed'}]:
            with self.assertRaises(ValidationError):
                bridge.claim(self.credential, values)
        self.revision.processing_job.refresh_from_db()
        self.assertEqual(self.revision.processing_job.attempts, 0)

    def test_saved_checkpoints_cannot_mix_different_worker_implementations(self):
        job = self.claim()
        original = RemoteSurveyLease.objects.get(job_id=job['job_id'])
        original.versions = {**original.versions, 'implementation': 'old-reviewed-implementation'}
        original.save()
        with self.assertRaises(ValidationError):
            bridge.heartbeat(self.credential, job['job_id'], job['lease'])
        SurveyProcessingJob.objects.filter(pk=job['job_id']).update(lease_until=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(ValidationError):
            self.claim()
        self.revision.processing_job.refresh_from_db()
        self.assertEqual(self.revision.processing_job.attempts, 1)

    def test_authenticated_image_is_normalized_and_original_bytes_unchanged(self):
        original = Path(self.photo.original.path).read_bytes()
        job = self.claim()
        task = bridge.next_task(self.credential, job['job_id'], job['lease'])
        client = Client(HTTP_AUTHORIZATION='Bearer ' + self.token, HTTP_X_WORKER_LEASE=job['lease'])
        response = client.get(reverse('remote_worker_image', args=[job['job_id'], task['task_id']]))
        self.assertEqual(response.status_code, 200)
        raw = b''.join(response.streaming_content)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), task['image_sha256'])
        self.assertEqual(len(raw), task['image_size'])
        self.assertEqual(raw[:2], b'\xff\xd8')
        self.assertEqual(Path(self.photo.original.path).read_bytes(), original)

    def test_returned_sources_are_canonical_unverified_and_unsupported_measurement_withheld(self):
        job = self.claim()
        task = bridge.next_task(self.credential, job['job_id'], job['lease'])
        result = self.analysed(task['input'], 'qwen3.5:4b')
        result['findings'][0].update(measured=True, verification_status='confirmed', source_id='foreign:999')
        result['findings'][1].update(basis='visible', unit='', evidence_quote='', value='12345')
        self.complete(job, task, result)
        saved = self.revision.source_analyses.get(source_id=task['input']['source_id']).payload
        self.assertEqual(saved['findings'][0]['source_id'], task['input']['source_id'])
        self.assertEqual(saved['findings'][0]['verification_status'], 'needs_review')
        self.assertFalse(saved['findings'][0]['measured'])
        self.assertIsNone(saved['findings'][1]['value'])
        self.assertTrue(saved['missing'])
        self.checklist.refresh_from_db()
        self.assertNotIn('manufacturer', self.checklist.answer_data.get('custom', {}))

    def test_malformed_unknown_source_and_stale_input_results_fail_without_checkpoint(self):
        job = self.claim()
        task = bridge.next_task(self.credential, job['job_id'], job['lease'])
        for result in [{'findings': 'broken'}, {'source_id': 'foreign', 'sha256': 'x', 'model': job['model']}]:
            with self.assertRaises(ValidationError):
                self.complete(job, task, result)
        with self.assertRaises(ValidationError):
            bridge.complete_task(self.credential, job['job_id'], job['lease'], task['task_id'],
                {'versions': bridge.versions(), 'input_digest': 'f' * 64, 'result': self.analysed(task['input'], job['model'])})
        self.assertEqual(SurveySourceAnalysis.objects.count(), 0)

    def test_duplicate_result_is_idempotent_and_different_result_cannot_replace_it(self):
        job = self.claim()
        task = bridge.next_task(self.credential, job['job_id'], job['lease'])
        first, second = self.complete(job, task), self.complete(job, task)
        self.assertFalse(first['duplicate'])
        self.assertTrue(second['duplicate'])
        self.assertEqual(self.revision.source_analyses.count(), 1)
        altered = self.analysed(task['input'], job['model'])
        altered['findings'][0]['value'] = 'Different vendor'
        with self.assertRaises(ValidationError):
            self.complete(job, task, altered)
        self.assertEqual(self.revision.source_analyses.count(), 1)

    def test_expired_lease_reclaims_without_repeating_completed_inference(self):
        job = self.claim()
        first = bridge.next_task(self.credential, job['job_id'], job['lease'])
        self.complete(job, first)
        SurveyProcessingJob.objects.filter(pk=job['job_id']).update(lease_until=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(PermissionDenied):
            bridge.heartbeat(self.credential, job['job_id'], job['lease'])
        recovered = self.claim()
        self.assertNotEqual(job['lease'], recovered['lease'])
        next_task = bridge.next_task(self.credential, recovered['job_id'], recovered['lease'])
        self.assertNotEqual(first['task_id'], next_task['task_id'])
        self.assertEqual(self.revision.source_analyses.count(), 1)
        with self.assertRaises(PermissionDenied):
            self.complete(job, first)

    def test_heartbeat_extends_lease_and_concurrent_claim_cannot_duplicate_job(self):
        job = self.claim()
        self.assertIsNone(self.claim())
        SurveyProcessingJob.objects.filter(pk=job['job_id']).update(lease_until=timezone.now() + timedelta(seconds=2))
        bridge.heartbeat(self.credential, job['job_id'], job['lease'])
        current = SurveyProcessingJob.objects.get(pk=job['job_id'])
        self.assertGreater(current.lease_until, timezone.now() + timedelta(seconds=590))

    def test_busy_requeues_and_explicit_failure_preserves_checkpoints_for_engineer_retry(self):
        job = self.claim()
        task = bridge.next_task(self.credential, job['job_id'], job['lease'])
        self.complete(job, task)
        bridge.fail(self.credential, job['job_id'], job['lease'], 'local_busy', True)
        recovered = self.claim()
        self.assertNotEqual(bridge.next_task(self.credential, recovered['job_id'], recovered['lease'])['task_id'], task['task_id'])
        bridge.fail(self.credential, recovered['job_id'], recovered['lease'], 'invalid_response')
        self.revision.processing_job.refresh_from_db()
        self.assertEqual(self.revision.processing_job.status, 'failed')
        pipeline.retry(self.request(), self.checklist.pk, self.revision.pk)
        self.assertIsNotNone(self.claim())
        self.assertEqual(self.revision.source_analyses.count(), 1)

    def test_project_revocation_or_survey_reassignment_stops_existing_worker_lease(self):
        job = self.claim()
        replacement = self.person('replacement', Profile.Roles.ENGINEER)
        Checklist.objects.filter(pk=self.checklist.pk).update(user=replacement)
        with self.assertRaises(ValidationError):
            bridge.heartbeat(self.credential, job['job_id'], job['lease'])

    def test_stale_submitter_job_becomes_failed_instead_of_permanently_blocking_queue(self):
        replacement = self.person('new_submitter', Profile.Roles.ENGINEER)
        Checklist.objects.filter(pk=self.checklist.pk).update(user=replacement)
        self.assertIsNone(self.claim())
        self.revision.processing_job.refresh_from_db()
        self.assertEqual(self.revision.processing_job.status, 'failed')
        self.assertIn('assignment', self.revision.processing_job.error)

    def test_provision_command_never_prints_token_or_overwrites_existing_private_file(self):
        output = Path(self.photo.original.path).parent / 'private-worker-config.json'
        captured = StringIO()
        call_command('provision_survey_worker', admin=self.admin.username, project=[self.project.pk],
            server_url='https://synthetic.example.invalid', output=str(output), stdout=captured)
        configuration = json.loads(output.read_text())
        self.assertNotIn(configuration['token'], captured.getvalue())
        self.assertEqual(bridge.authenticate(configuration['token']).pk.hex, configuration['credential_id'].replace('-', ''))
        count = RemoteWorkerCredential.objects.count()
        before = output.read_bytes()
        with self.assertRaises(CommandError):
            call_command('provision_survey_worker', admin=self.admin.username, project=[self.project.pk],
                server_url='https://synthetic.example.invalid', output=str(output), stdout=StringIO())
        self.assertEqual(RemoteWorkerCredential.objects.count(), count)
        self.assertEqual(output.read_bytes(), before)
        for _ in range(2):
            call_command('provision_survey_worker', admin=self.admin.username, revoke=configuration['credential_id'], stdout=StringIO())
        self.assertEqual(GovernanceAudit.objects.filter(action='remote_worker.revoked', details__credential_id=configuration['credential_id']).count(), 1)

    def test_server_mapping_rejects_unknown_ids_and_preserves_source_bound_proposals(self):
        job = self.claim()
        while True:
            task = bridge.next_task(self.credential, job['job_id'], job['lease'])
            if task['kind'] == 'mapping':
                break
            result = self.analysed(task['input'], job['model'])
            result['findings'][0]['field_hint'] = ''
            self.complete(job, task, result)
        finding = task['input']['findings'][0]['finding_key']
        invalid = {'bindings': [{'finding_key': finding, 'field_id': 'foreign-field', 'reason': 'Invalid foreign target'}], 'unassigned': []}
        with self.assertRaises(ValidationError):
            self.complete(job, task, invalid)
        keys = [entry['finding_key'] for entry in task['input']['findings'] if entry['category'] == 'equipment']
        valid = {'bindings': [{'finding_key': key, 'field_id': 'manufacturer', 'reason': 'Recorded manufacturer label matches this exact field.'} for key in keys],
                 'unassigned': [entry['finding_key'] for entry in task['input']['findings'] if entry['finding_key'] not in keys]}
        self.complete(job, task, valid)
        saved = self.revision.source_analyses.get(source_id=task['input']['key']).payload
        self.assertTrue(all(entry['field_id'] == 'manufacturer' and entry['verification_status'] == 'needs_review' for entry in saved['bindings']))
        self.assertEqual(len(saved['bindings']), len(keys))

    def test_normalized_input_tampering_is_explicit_failed_job_and_does_not_touch_original(self):
        job = self.claim()
        task = bridge.next_task(self.credential, job['job_id'], job['lease'])
        record = RemoteSurveyTask.objects.get(pk=task['task_id'])
        original = Path(self.photo.original.path).read_bytes()
        Path(record.image.path).write_bytes(b'corrupt separate inference image')
        client = Client(HTTP_AUTHORIZATION='Bearer ' + self.token, HTTP_X_WORKER_LEASE=job['lease'])
        response = client.get(reverse('remote_worker_image', args=[job['job_id'], task['task_id']]))
        self.assertEqual(response.status_code, 409)
        self.revision.processing_job.refresh_from_db()
        self.assertEqual(self.revision.processing_job.status, 'failed')
        self.assertEqual(Path(self.photo.original.path).read_bytes(), original)

    def test_corrupt_local_cache_is_preserved_separately_and_recomputed(self):
        cache = Path(self.photo.original.path).parent / 'private-cache-test'
        client = RemoteSurveyClient('https://synthetic.example.invalid', self.token, cache)
        path = cache / ('a' * 64 + '.json')
        path.write_text('{corrupt incomplete cache', encoding='utf-8')
        with self.assertLogs('core.remote_worker_client', level='WARNING'):
            self.assertIsNone(client._read_cached(path, 'a' * 64))
        self.assertFalse(path.exists())
        self.assertTrue(path.with_suffix('.quarantined.json').is_file())

    def test_unsupported_local_model_cannot_claim_remote_work(self):
        client = RemoteSurveyClient('https://synthetic.example.invalid', self.token, Path(self.photo.original.path).parent / 'private-model-test')
        with patch('core.local_ai.ollama', side_effect=[{'models': [{'name': 'qwen3.5:4b'}]}, {'capabilities': ['completion']}]), self.assertRaises(ValueError):
            client.process_once()
        self.revision.processing_job.refresh_from_db()
        self.assertEqual(self.revision.processing_job.attempts, 0)


@override_settings(**SETTINGS)
class RemoteSurveyHTTPIntegrationTests(Fixtures, LiveServerTestCase):
    # Bind and request the same explicit address. A localhost IPv6-first DNS
    # probe is not a connection to this IPv4-only disposable fixture.
    host = '127.0.0.1'

    def worker(self):
        return RemoteSurveyClient(self.live_server_url, self.token, Path(self.photo.original.path).parent / 'private-worker-cache')

    def controlled_inference(self):
        from contextlib import ExitStack
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(RemoteSurveyClient, 'model_identity', return_value=('qwen3.5:4b', 'd' * 64)))
        stack.enter_context(patch('core.photo_queue.photo_inference_lease', side_effect=lambda: nullcontext(lambda: None)))
        def analyse(source, model, **kwargs):
            self.assertTrue(base64.b64decode(source['image_b64'], validate=True).startswith(b'\xff\xd8'))
            return self.analysed(source, model)
        return stack.enter_context(patch('core.survey_evidence.analyse_source', side_effect=analyse))

    def test_real_outbound_http_image_checkpoint_result_and_actual_draft_exports(self):
        inference = self.controlled_inference()
        self.assertTrue(self.worker().process_once())
        self.assertEqual(inference.call_count, 2)
        self.revision.processing_job.refresh_from_db()
        self.assertEqual(self.revision.processing_job.status, 'ready_for_review')
        self.assertEqual(self.revision.source_analyses.count(), 2)
        self.assertEqual(SurveyProcessingResult.objects.count(), 1)
        drawing = SurveyDrawingSet.objects.get(revision=self.revision)
        self.assertFalse(drawing.released)
        self.assertTrue(Path(drawing.manifest['pdf']).is_file())
        self.assertTrue(all(Path(sheet['dxf']).is_file() for sheet in drawing.manifest['sheets']))
        self.assertFalse(any(item['accepted'] for item in self.revision.processing_result.payload['checklist_items']))
        self.checklist.refresh_from_db()
        self.assertNotIn('manufacturer', self.checklist.answer_data.get('custom', {}))
        self.assertEqual(SurveyProcessingJob.objects.count(), 1)
        self.assertEqual(bridge.versions()['protocol'], 'isurvix-survey-worker-v1')

    def test_disconnected_result_transfer_and_restart_reuse_durable_pc_cache(self):
        inference = self.controlled_inference()
        client = self.worker()
        original = client.request
        def interrupted(path, *args, **kwargs):
            if path.endswith('/complete/'):
                raise WorkerConnectionError('Simulated interrupted outbound transfer')
            return original(path, *args, **kwargs)
        with patch.object(client, 'request', side_effect=interrupted), self.assertRaises(WorkerConnectionError):
            client.process_once()
        self.assertEqual(inference.call_count, 1)
        self.assertEqual(self.revision.source_analyses.count(), 0)
        SurveyProcessingJob.objects.filter(revision=self.revision).update(lease_until=timezone.now() - timedelta(seconds=1))
        self.assertTrue(self.worker().process_once())
        self.assertEqual(inference.call_count, 2, 'Only the second image should require new inference after cache recovery.')
        self.assertEqual(self.revision.source_analyses.count(), 2)
        self.assertEqual(SurveyDrawingSet.objects.count(), 1)

    def test_connection_rejects_public_http_redirects_and_invalid_credentials(self):
        with self.assertRaises(ValidationError):
            RemoteSurveyClient('http://example.com', self.token, Path(self.photo.original.path).parent / 'cache')
        client = self.worker()
        client.token = 'invalid-token'
        with self.assertRaises(WorkerAccessError):
            client.request('claim/', self.identity)

    def test_real_http_redirect_never_forwards_bearer_credentials(self):
        requests = []
        class RedirectHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                self.send_response(302)
                self.send_header('Location', self.path + 'redirected')
                self.end_headers()
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), RedirectHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = RemoteSurveyClient(f'http://127.0.0.1:{server.server_port}', self.token,
                Path(self.photo.original.path).parent / 'private-redirect-test')
            with self.assertRaises(WorkerConnectionError):
                client.request('claim/')
            self.assertEqual(len(requests), 1, 'A redirect must never cause a second authenticated request.')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_interrupted_image_transfer_runs_no_inference_and_resumes_same_task(self):
        inference = self.controlled_inference()
        client = self.worker()
        original = client.request
        def interrupted(path, *args, **kwargs):
            if kwargs.get('binary'):
                raise WorkerConnectionError('Simulated interrupted image download')
            return original(path, *args, **kwargs)
        with patch.object(client, 'request', side_effect=interrupted), self.assertRaises(WorkerConnectionError):
            client.process_once()
        self.assertEqual(inference.call_count, 0)
        self.assertEqual(self.revision.source_analyses.count(), 0)
        SurveyProcessingJob.objects.filter(revision=self.revision).update(lease_until=timezone.now() - timedelta(seconds=1))
        self.assertTrue(self.worker().process_once())
        self.assertEqual(inference.call_count, 2)
        self.assertEqual(self.revision.source_analyses.count(), 2)
