"""Release eligibility tests use independent CI records, never a real token."""
import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.request import urlopen

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]
SHA = 'a' * 40
REPO = 'assimbaig/iSurvix-Field'


def module():
    spec = importlib.util.spec_from_file_location('release_gate', ROOT / 'deploy/release_gate.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class SharedReleaseGateTests(SimpleTestCase):
    def setUp(self):
        self.gate = module()
        self.runs = [dict(id=i, run_number=i, run_attempt=1, head_sha=SHA,
                         path=path, status='completed', conclusion='success',
                         updated_at='2026-10-31T10:00:00Z',
                         head_repository={'full_name': REPO})
                     for i, path in enumerate(self.gate.REQUIRED_WORKFLOWS, 1)]

    def test_one_failed_required_check_prevents_release_record(self):
        self.runs[0]['conclusion'] = 'failure'
        with self.assertRaises(ValueError):
            self.gate.verified_runs(self.runs, SHA, REPO)

    def test_missing_cancelled_skipped_pending_foreign_and_wrong_sha_gates_are_rejected(self):
        for field, value in [('conclusion', 'cancelled'), ('conclusion', 'skipped'),
                             ('status', 'in_progress'), ('head_sha', 'b' * 40),
                             ('head_repository', {'full_name': 'foreign/repository'})]:
            with self.subTest(field=field, value=value):
                records = copy.deepcopy(self.runs)
                records[0][field] = value
                with self.assertRaises(ValueError):
                    self.gate.verified_runs(records, SHA, REPO)
        with self.assertRaises(ValueError):
            self.gate.verified_runs(self.runs[1:], SHA, REPO)

    def test_newer_failed_rerun_cannot_be_hidden_by_an_older_success(self):
        newer = dict(self.runs[0], run_attempt=2, conclusion='failure')
        with self.assertRaises(ValueError):
            self.gate.verified_runs([newer, *self.runs], SHA, REPO)

    def test_recent_failed_attempt_of_older_run_cannot_be_hidden_by_run_number(self):
        earlier = dict(self.runs[0], id=90, run_number=1, updated_at='2026-10-31T10:00:00Z')
        higher = dict(earlier, id=100, run_number=2)
        recent_failure = dict(earlier, run_attempt=2, updated_at='2026-10-31T11:00:00Z', conclusion='failure')
        with self.assertRaises(ValueError):
            self.gate.verified_runs([higher, recent_failure, *self.runs[1:]], SHA, REPO)

    def test_deleted_fork_shape_is_rejected_without_an_unhandled_exception(self):
        self.runs[0]['head_repository'] = None
        with self.assertRaises(ValueError):
            self.gate.verified_runs(self.runs, SHA, REPO)

    def test_success_records_exact_same_sha_run_and_both_edition_images(self):
        checks = self.gate.verified_runs(self.runs, SHA, REPO)
        manifest = {'release_id': SHA, 'images': {'app': 'sha256:' + 'b' * 64, 'nginx': 'sha256:' + 'c' * 64},
                    'status': 'draft-for-review', 'owner_release_approved': False}
        proof = {'release': SHA, 'fresh_install': True, 'runtime_image_pulls': 0,
                 'restart_preserved_db_and_media': True, 'upgrade_recovery_verified': True,
                 'supported_from': ['d' * 40], 'images': manifest['images'], 'manifest_sha256': 'e' * 64}
        record = self.gate.release_record(manifest, 'e' * 64, checks, proof)
        self.assertEqual(record['source_commit'], SHA)
        self.assertEqual(record['editions'], ['cloud', 'customer'])
        self.assertEqual(record['images'], manifest['images'])
        self.assertEqual(record['supported_from'], ['d' * 40])
        self.assertFalse(record['owner_release_approved'])

    def test_missing_upgrade_proof_or_changed_release_is_not_a_supported_version(self):
        checks = self.gate.verified_runs(self.runs, SHA, REPO)
        manifest = {'release_id': SHA, 'images': {'app': 'sha256:' + 'b' * 64, 'nginx': 'sha256:' + 'c' * 64},
                    'status': 'draft-for-review', 'owner_release_approved': False}
        proof = {'release': SHA, 'fresh_install': True, 'runtime_image_pulls': 0,
                 'restart_preserved_db_and_media': True, 'upgrade_recovery_verified': True,
                 'supported_from': ['d' * 40], 'images': manifest['images'], 'manifest_sha256': 'e' * 64}
        for field, value in [('upgrade_recovery_verified', False), ('supported_from', []),
                             ('release', 'b' * 40), ('runtime_image_pulls', 1)]:
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    self.gate.release_record(manifest, 'e' * 64, checks, {**proof, field: value})

    def test_same_source_proof_with_different_image_or_manifest_cannot_publish(self):
        checks = self.gate.verified_runs(self.runs, SHA, REPO)
        manifest = {'release_id': SHA, 'images': {'app': 'sha256:' + 'b' * 64, 'nginx': 'sha256:' + 'c' * 64},
                    'status': 'draft-for-review', 'owner_release_approved': False}
        proof = {'release': SHA, 'fresh_install': True, 'runtime_image_pulls': 0,
                 'restart_preserved_db_and_media': True, 'upgrade_recovery_verified': True,
                 'supported_from': ['d' * 40], 'images': manifest['images'], 'manifest_sha256': 'e' * 64}
        for field, value in [('images', {**manifest['images'], 'app': 'sha256:' + 'f' * 64}), ('manifest_sha256', 'f' * 64)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.gate.release_record(manifest, 'e' * 64, checks, {**proof, field: value})

    def test_failed_validation_does_not_create_a_publication_file(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.local') as temporary:
            target = Path(temporary) / 'release.json'
            with self.assertRaises(ValueError):
                self.gate.publish_record(target, {'owner_release_approved': True})
            self.assertFalse(target.exists())

    def test_publication_rejects_changed_gate_attempt_after_artifact_download(self):
        checks = self.gate.verified_runs(self.runs, SHA, REPO)
        before = {'source_commit': SHA, 'required_checks': checks}
        fresh = copy.deepcopy(before)
        fresh['observed_utc'] = datetime.now(timezone.utc).isoformat()
        self.gate.confirm_gate_pair(before, fresh)
        fresh['required_checks'][self.gate.REQUIRED_WORKFLOWS[0]]['run_attempt'] += 1
        with self.assertRaises(ValueError):
            self.gate.confirm_gate_pair(before, fresh)


class SharedReleaseHTTPIntegration(SimpleTestCase):
    """Controlled HTTP delivers CI records through the gate into durable output."""
    setUp = SharedReleaseGateTests.setUp

    def test_http_provenance_to_persisted_shared_record_and_failed_retry(self):
        state = {'runs': self.runs, 'paths': []}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                state['paths'].append(self.path)
                payload = json.dumps({'workflow_runs': state['runs']}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.shutdown)

        def transport(path, token):
            self.assertEqual(token, 'synthetic-actions-read-token')
            with urlopen('http://127.0.0.1:%d%s' % (server.server_port, path), timeout=3) as response:
                return json.load(response)

        with tempfile.TemporaryDirectory(dir=ROOT / '.local') as temporary, patch.object(self.gate, '_api', side_effect=transport):
            target = Path(temporary) / 'release.json'
            checks = self.gate.fetch_verified(REPO, SHA, 'synthetic-actions-read-token')
            manifest = {'release_id': SHA, 'images': {'app': 'sha256:' + 'b' * 64, 'nginx': 'sha256:' + 'c' * 64},
                        'status': 'draft-for-review', 'owner_release_approved': False}
            proof = {'release': SHA, 'fresh_install': True, 'runtime_image_pulls': 0,
                     'restart_preserved_db_and_media': True, 'upgrade_recovery_verified': True,
                     'supported_from': ['d' * 40], 'images': manifest['images'], 'manifest_sha256': 'e' * 64}
            record = self.gate.release_record(manifest, 'e' * 64, checks, proof)
            self.gate.publish_record(target, record)
            saved = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(saved['images'], manifest['images'])
            self.assertEqual(saved['editions'], ['cloud', 'customer'])
            self.assertNotIn('synthetic-actions-read-token', target.read_text())
            with self.assertRaises(FileExistsError):
                self.gate.publish_record(target, record)
            state['runs'][0] = {**state['runs'][0], 'conclusion': 'failure'}
            with self.assertRaises(ValueError):
                self.gate.fetch_verified(REPO, SHA, 'synthetic-actions-read-token')
            self.assertEqual(json.loads(target.read_text()), saved)
            self.assertTrue(all('head_sha=' + SHA in path for path in state['paths']))
