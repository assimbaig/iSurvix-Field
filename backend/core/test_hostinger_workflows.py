"""Release-channel and actual workflow contracts; no credentials/network required."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import urllib.request

from django.test import SimpleTestCase
from django.urls import reverse
import yaml

ROOT = Path(__file__).resolve().parents[2]
REPO = 'assimbaig/iSurvix-Field'
BRANCH = 'feat/ai-settings-routing-20261031'


class PlatformLoginRouteTests(SimpleTestCase):
    def test_private_deep_link_returns_to_the_actual_login_screen(self):
        response = self.client.get(reverse('ai_settings_index'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('/login/?next='), response['Location'])
        self.assertEqual(self.client.get('/login/').status_code, 200)


def channel_module():
    spec = importlib.util.spec_from_file_location('hostinger_channel', ROOT / 'deploy/hostinger/channel.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def record():
    return {'format': 'isurvix-hostinger-channel-v1', 'repository': REPO,
            'branch': BRANCH, 'source_commit': 'a' * 40, 'merge_commit': 'b' * 40,
            'source_schema': '0059_task_page_indexes', 'manifest_sha256': 'c' * 64,
            'artifact_id': 123, 'artifact_sha256': 'd' * 64,
            'images': {'app': 'sha256:' + 'e' * 64, 'nginx': 'sha256:' + 'f' * 64}}


class HostingerWorkflowTests(SimpleTestCase):
    def workflow(self, name):
        # BaseLoader intentionally preserves YAML's 'on' key instead of YAML1.1 bool.
        return yaml.load((ROOT / '.github/workflows' / name).read_text(), Loader=yaml.BaseLoader)

    def test_ui_and_operations_prs_cannot_skip_required_release_checks(self):
        for name in ('repair-validation.yml', 'staging-verification.yml',
                     'customer-server-verification.yml', 'shared-release-candidate.yml'):
            with self.subTest(workflow=name):
                triggers = self.workflow(name)['on']
                self.assertIn('pull_request', triggers)
                config = triggers['pull_request'] or {}
                self.assertNotIn('paths', config)
                self.assertNotIn('paths-ignore', config)

    def test_deployment_only_runs_for_merged_same_repository_live_branch_pr(self):
        workflow = self.workflow('hostinger-approved-deploy.yml')
        self.assertNotIn('pull_request_target', workflow['on'])
        self.assertNotIn('pull_request', workflow['on'])
        self.assertEqual(workflow['on']['push']['branches'], [BRANCH])
        resolver = workflow['jobs']['resolve']
        self.assertNotIn('environment', resolver, 'Unresolved pushes cannot obtain receiver credentials')
        self.assertNotIn('secrets.', json.dumps(resolver))
        self.assertEqual(resolver['permissions'], {'contents': 'read', 'pull-requests': 'read'})
        self.assertTrue(any('channel.py resolve-pr' in step.get('run', '') for step in resolver['steps']))
        self.assertEqual(resolver['steps'][0]['with']['ref'], '${{ github.sha }}')
        job = workflow['jobs']['deliver']
        self.assertEqual(job['needs'], 'resolve')
        self.assertIn("needs.resolve.result == 'success'", job['if'])
        self.assertIn('needs.resolve.outputs.pr', job['if'])
        self.assertEqual(job['steps'][0]['with']['ref'], '${{ github.sha }}')
        receiver = next(step for step in job['steps'] if 'VPS_DEPLOY_KEY' in step.get('env', {}))
        self.assertEqual(receiver['env']['PR_NUMBER'], '${{ needs.resolve.outputs.pr }}')
        self.assertEqual(workflow['concurrency']['cancel-in-progress'], 'false')
        self.assertEqual(job['environment']['name'], 'hostinger-beta')
        self.assertEqual(job['permissions'].get('pull-requests'), 'read',
                         'The receiver independently reads the approved PR and owner review')
        text = (ROOT / '.github/workflows/hostinger-approved-deploy.yml').read_text()
        self.assertIn('StrictHostKeyChecking=yes', text)
        self.assertNotIn('ssh-keyscan', text)
        self.assertNotIn('git pull', text)
        self.assertNotIn('github.event.pull_request', text)

    def test_customer_upgrade_proves_actual_channel_baseline(self):
        workflow = self.workflow('customer-server-verification.yml')
        steps = workflow['jobs']['disposable-linux']['steps']
        self.assertTrue(any('channel.py baseline' in step.get('run', '') for step in steps))
        rehearsal = next(step for step in steps if 'verify_customer.sh' in step.get('run', ''))
        self.assertIn('ISURVIX_UPGRADE_BASELINE', rehearsal['env'])
        self.assertIn('ISURVIX_UPGRADE_SOURCE_SCHEMA', rehearsal['env'])

    def test_published_website_source_checks_are_in_the_release_gate(self):
        workflow = self.workflow('repair-validation.yml')
        self.assertTrue(any('website/corporate/tests' in step.get('run', '')
                            for step in workflow['jobs']['backend']['steps']))

    def test_real_docker_delivery_is_required_before_candidate_publication(self):
        steps = self.workflow('customer-server-verification.yml')['jobs']['disposable-linux']['steps']
        checks = [i for i, step in enumerate(steps) if 'verify_delivery.py' in step.get('run', '')]
        self.assertEqual(len(checks), 1)
        publication = next(i for i, step in enumerate(steps) if step.get('name') == 'Retain unapproved transferable candidate for owner review')
        self.assertLess(checks[0], publication)
        self.assertIn('ISURVIX_DISPOSABLE_REHEARSAL=yes', steps[checks[0]]['run'])

    def test_customer_verification_artifact_retains_its_existing_root_contract(self):
        steps = self.workflow('customer-server-verification.yml')['jobs']['disposable-linux']['steps']
        evidence = next(step for step in steps if step.get('with', {}).get('name') == 'customer-server-verification')
        paths = [line.strip().replace('${{ runner.temp }}', '/runner-temp')
                 for line in evidence['with']['path'].splitlines() if line.strip()]
        common = Path(os.path.commonpath(paths))
        verification = Path('/runner-temp/isurvix-customer/verification.json')
        self.assertEqual(verification.relative_to(common).as_posix(), 'verification.json',
                         'Shared release consumer must find verification.json at the artifact root')
        native = [step for step in steps if step.get('with', {}).get('name') == 'hostinger-delivery-verification']
        self.assertEqual(len(native), 1, 'Different evidence roots need separate artifacts')
        self.assertIn('hostinger-delivery-rehearsal/verification.json', native[0]['with']['path'])


class HostingerChannelTests(SimpleTestCase):
    def test_valid_channel_roundtrip_and_closed_schema(self):
        channel = channel_module()
        self.assertEqual(channel.validate(record()), record())
        for key, value in [('source_commit', 'a; echo unsafe'), ('source_schema', '../../secret'),
                           ('repository', 'foreign/repo'), ('branch', 'main'),
                           ('artifact_id', True), ('artifact_sha256', 'short')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                channel.validate(dict(record(), **{key: value}))
        with self.assertRaises(ValueError):
            channel.validate(dict(record(), github_token='never-persist'))

    def test_receipt_must_bind_success_exact_prior_source_and_images(self):
        channel = channel_module()
        receipt = {'format': 'isurvix-hostinger-receipt-v1', 'status': 'completed', 'source_release': 'a' * 40, 'release': '1' * 40,
                   'merge_sha': '2' * 40, 'manifest_sha256': '3' * 64, 'artifact_id': 456,
                   'artifact_sha256': '4' * 64, 'images': record()['images'],
                   'core_schema': '0059_task_page_indexes'}
        updated = channel.from_receipt(record(), receipt)
        self.assertEqual(updated['source_commit'], '1' * 40)
        self.assertEqual(updated['source_schema'], receipt['core_schema'])
        self.assertEqual(channel.from_receipt(updated, receipt), updated)
        for key, value in [('status', 'failed'), ('source_release', '5' * 40),
                           ('images', {}), ('release', 'not-a-commit')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                channel.from_receipt(record(), dict(receipt, **{key: value}))

    def test_cli_writes_real_ci_baseline_without_secret_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / 'channel.json').write_text(json.dumps(record()))
            result = subprocess.run([sys.executable, str(ROOT / 'deploy/hostinger/channel.py'),
                                     'baseline', '--record', str(path / 'channel.json'),
                                     '--github-output', str(path / 'outputs')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((path / 'outputs').read_text(),
                             'source_commit=' + 'a' * 40 + '\nsource_schema=0059_task_page_indexes\n')


class MergedPushResolutionTests(SimpleTestCase):
    sha = 'a' * 40

    def merged_pr(self):
        return {'number': 34, 'state': 'closed', 'merged': True,
                'merged_at': '2026-11-04T21:30:00Z', 'merge_commit_sha': self.sha,
                'head': {'repo': {'full_name': REPO}},
                'base': {'ref': BRANCH, 'repo': {'full_name': REPO}}}

    def resolve(self, records, details=None, sha=None):
        def get(path):
            if '/commits/' in path:
                return records
            return details if details is not None else self.merged_pr()
        return channel_module().resolve_merged_pr(sha or self.sha, get)

    def test_exact_merged_same_repository_pr_resolves(self):
        self.assertEqual(self.resolve([{'number': 34}]), 34)

    def test_direct_push_foreign_open_wrong_branch_and_other_merge_are_rejected(self):
        cases = [[], [{'number': True}], [{'number': 34}, {'number': 34}],
                 [{'number': 34}, {'number': 35}]]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.resolve(rows)
        for change in ({'state': 'open'}, {'merged': False}, {'merge_commit_sha': 'b' * 40},
                       {'head': {'repo': {'full_name': 'foreign/repo'}}},
                       {'base': {'ref': 'main', 'repo': {'full_name': REPO}}},
                       {'base': {'ref': BRANCH, 'repo': {'full_name': 'foreign/repo'}}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.resolve([{'number': 34}], dict(self.merged_pr(), **change))
        with self.assertRaises(ValueError):
            self.resolve([], sha='../../private')

    def test_ambiguous_canonical_prs_and_boolean_identity_fail_closed(self):
        channel = channel_module()
        def ambiguous(path):
            if '/commits/' in path:
                return [{'number': 34}, {'number': 35}]
            return dict(self.merged_pr(), number=int(path.rsplit('/', 1)[1]))
        with self.assertRaises(ValueError):
            channel.resolve_merged_pr(self.sha, ambiguous)
        def boolean_identity(path):
            return [{'number': 1}] if '/commits/' in path else dict(self.merged_pr(), number=True)
        with self.assertRaises(ValueError):
            channel.resolve_merged_pr(self.sha, boolean_identity)

    def test_paginated_commit_associations_are_fully_checked(self):
        channel = channel_module()
        observed = []
        def get(path):
            observed.append(path)
            if '/commits/' in path:
                return [{'number': n} for n in range(1, 101)] if path.endswith('page=1') else []
            number = int(path.rsplit('/', 1)[1])
            return dict(self.merged_pr(), number=number,
                        merge_commit_sha=self.sha if number == 34 else 'b' * 40)
        self.assertEqual(channel.resolve_merged_pr(self.sha, get), 34)
        self.assertTrue(any(path.endswith('page=2') for path in observed))
        for invalid in ({'number': 34}, 'not-json-list', None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                channel.resolve_merged_pr(self.sha, lambda path: invalid)

    def test_cli_invalid_commit_never_writes_pr_output_or_logs_credentials(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'outputs'
            result = subprocess.run([sys.executable, str(ROOT / 'deploy/hostinger/channel.py'),
                                     'resolve-pr', '--commit', '../../untrusted',
                                     '--github-output', str(output)], capture_output=True, text=True,
                                    env=dict(os.environ, GITHUB_TOKEN='private-fixture-token'))
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
            self.assertNotIn('private-fixture-token', result.stdout + result.stderr)

    def test_real_http_fixture_delivers_json_and_errors_fail_without_token_disclosure(self):
        channel = channel_module()
        calls = []
        pr = self.merged_pr()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append((self.path, self.headers.get('Authorization')))
                if '/commits/' in self.path:
                    data = [{'number': 34}]
                elif self.path.endswith('/pulls/34'):
                    data = pr
                elif self.path.endswith('/malformed'):
                    self.send_response(200); self.end_headers(); self.wfile.write(b'{broken-json'); return
                else:
                    self.send_response(503); self.end_headers(); self.wfile.write(b'private-fixture-token'); return
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        def fixture_open(request, timeout):
            self.assertTrue(request.full_url.startswith('https://api.github.com/repos/' + REPO + '/'))
            self.assertLessEqual(timeout, 20)
            tail = request.full_url.removeprefix('https://api.github.com')
            local = urllib.request.Request('http://127.0.0.1:' + str(server.server_port) + tail,
                                           headers=dict(request.header_items()))
            return urllib.request.urlopen(local, timeout=timeout)
        try:
            reader = channel.GitHubReader('private-fixture-token', open_request=fixture_open)
            self.assertEqual(channel.resolve_merged_pr(self.sha, reader), 34)
            self.assertEqual(calls[0][0], '/repos/' + REPO + '/commits/' + self.sha + '/pulls?per_page=100&page=1')
            self.assertEqual(calls[1][0], '/repos/' + REPO + '/pulls/34')
            self.assertTrue(all(auth == 'Bearer private-fixture-token' for _, auth in calls))
            with self.assertRaises(ValueError) as failure:
                reader('/repos/' + REPO + '/unavailable')
            self.assertNotIn('private-fixture-token', str(failure.exception))
            with self.assertRaises(ValueError):
                reader('/repos/' + REPO + '/malformed')
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
