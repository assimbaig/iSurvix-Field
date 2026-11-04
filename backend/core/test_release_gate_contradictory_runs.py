"""An independent same-source run cannot hide a pending/failed required check."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from django.test import SimpleTestCase

from . import test_release_gate as fixtures


class ContradictoryReleaseRunTests(SimpleTestCase):
    def setUp(self):
        self.gate = fixtures.module()
        self.runs = [dict(id=i, run_number=i, run_attempt=1, head_sha=fixtures.SHA,
            path=path, status='completed', conclusion='success', event='pull_request',
            updated_at='2026-11-04T16:40:21Z', head_repository={'full_name': fixtures.REPO})
            for i, path in enumerate(self.gate.REQUIRED_WORKFLOWS, 1)]

    def app(self, **changes):
        return {**self.runs[0], **changes}

    def verify(self, app_runs):
        return self.gate.verified_runs([*app_runs, *self.runs[1:]], fixtures.SHA, fixtures.REPO)

    def test_completed_push_cannot_hide_a_newer_unfinished_pr_run(self):
        # Actual PR33 race: the older push finished after the newer PR started,
        # while that PR's Windows job was still running and would later fail.
        push = self.app(id=41, run_number=41, event='push')
        pending_pr = self.app(id=42, run_number=42, event='pull_request',
            status='in_progress', conclusion=None, updated_at='2026-11-04T16:28:33Z')
        with self.assertRaises(self.gate.ChecksPending):
            self.verify([push, pending_pr])

    def test_a_successful_other_run_does_not_supersede_an_independent_failure(self):
        failed_pr = self.app(id=42, run_number=42, conclusion='failure')
        successful_push_retry = self.app(id=41, run_number=41, run_attempt=2,
            event='push', updated_at='2026-11-04T17:00:00Z')
        with self.assertRaises(ValueError):
            self.verify([failed_pr, successful_push_retry])

    def test_own_successful_retry_supersedes_only_its_older_attempt(self):
        failed = self.app(id=42, run_number=42, conclusion='failure')
        retry = {**failed, 'run_attempt': 2, 'conclusion': 'success',
                 'updated_at': '2026-11-04T17:00:00Z'}
        checks = self.verify([failed, retry, self.app(id=41, run_number=41, event='push')])
        self.assertEqual(checks[self.gate.REQUIRED_WORKFLOWS[0]]['run_id'], 42)
        self.assertEqual(checks[self.gate.REQUIRED_WORKFLOWS[0]]['run_attempt'], 2)

    def test_latest_attempt_identity_precedes_older_snapshot_update_time(self):
        old_success = self.app(run_attempt=1, updated_at='2026-11-04T17:00:00Z')
        current_failed = self.app(run_attempt=2, conclusion='failure',
            updated_at='2026-11-04T16:59:00Z')
        with self.assertRaises(ValueError):
            self.verify([old_success, current_failed])
        current_pending = {**current_failed, 'status': 'in_progress', 'conclusion': None}
        with self.assertRaises(self.gate.ChecksPending):
            self.verify([old_success, current_pending])

    def test_conflicting_same_attempt_snapshots_do_not_depend_on_input_order(self):
        success = self.app()
        failure = self.app(conclusion='failure')
        for records in ([success, failure], [failure, success]):
            with self.subTest(first=records[0]['conclusion']), self.assertRaises(ValueError):
                self.verify(records)

    def test_identical_pagination_duplicates_are_safe_and_foreign_runs_cannot_block(self):
        foreign = self.app(id=99, status='in_progress', conclusion=None,
            head_repository={'full_name': 'foreign/repository'})
        other_source = self.app(id=100, status='in_progress', conclusion=None, head_sha='b'*40)
        checks = self.verify([self.app(), self.app(), foreign, other_source])
        self.assertEqual(set(checks), set(self.gate.REQUIRED_WORKFLOWS))
        self.assertEqual(checks[self.gate.REQUIRED_WORKFLOWS[0]]['run_id'], 1)

    def test_pagination_duplicates_do_not_hide_an_independent_pending_run(self):
        unrelated = [self.app(id=1000+i, path=f'.github/workflows/unrelated-{i}.yml') for i in range(97)]
        first_page = {'workflow_runs': [*self.runs, *unrelated]}
        second_page = {'workflow_runs': [self.app(status='in_progress', conclusion=None,
            updated_at='2026-11-04T16:20:00Z'), self.app(id=42, run_number=42,
            status='in_progress', conclusion=None, updated_at='2026-11-04T16:28:33Z')]}
        with patch.object(self.gate, '_api', side_effect=[first_page, second_page]) as api:
            with self.assertRaises(self.gate.ChecksPending):
                self.gate.fetch_verified(fixtures.REPO, fixtures.SHA, 'synthetic-reader-token')
        self.assertEqual(api.call_count, 2)
        self.assertIn('page=2', api.call_args_list[-1].args[0])

    def test_real_http_gate_does_not_persist_eligibility_until_each_run_passes(self):
        pending = self.app(id=42, run_number=42, status='in_progress', conclusion=None,
            updated_at='2026-11-04T16:28:33Z')
        state = {'runs': [*self.runs, pending]}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                raw = json.dumps({'workflow_runs': state['runs']}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def transport(path, token):
            self.assertEqual(token, 'synthetic-reader-token')
            self.assertIn('head_sha=' + fixtures.SHA, path)
            page = parse_qs(urlsplit(path).query)['page'][0]
            with urlopen(f'http://127.0.0.1:{server.server_port}/{page}', timeout=5) as response:
                return json.load(response)

        try:
            with tempfile.TemporaryDirectory(dir=fixtures.ROOT/'.local') as temporary:
                destination = Path(temporary)/'verified-gate.json'
                command = ['check', '--repository', fixtures.REPO, '--release-id', fixtures.SHA,
                           '--output', str(destination)]
                with patch.object(self.gate, '_api', side_effect=transport), patch.dict(
                        os.environ, {'GITHUB_TOKEN': 'synthetic-reader-token'}):
                    with self.assertRaises(SystemExit) as stopped:
                        self.gate.main(command)
                    self.assertEqual(stopped.exception.code, 2)
                    self.assertFalse(destination.exists())
                    pending.update(status='completed', conclusion='failure', updated_at='2026-11-04T16:42:33Z')
                    with self.assertRaises(SystemExit):
                        self.gate.main(command)
                    self.assertFalse(destination.exists())
                    retry = {**pending, 'run_attempt': 2, 'conclusion': 'success',
                             'updated_at': '2026-11-04T17:00:00Z'}
                    state['runs'].append(retry)
                    self.gate.main(command)
                saved = json.loads(destination.read_text())
                self.assertEqual(saved['source_commit'], fixtures.SHA)
                self.assertEqual(saved['required_checks'][self.gate.REQUIRED_WORKFLOWS[0]]['run_attempt'], 2)
                self.assertEqual(saved['customer_run_id'], self.runs[2]['id'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)
