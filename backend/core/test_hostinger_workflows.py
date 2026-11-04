"""Release-channel and actual workflow contracts; no credentials/network required."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

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
        self.assertNotIn('push', workflow['on'])
        self.assertEqual(workflow['on']['pull_request']['types'], ['closed'])
        self.assertEqual(workflow['on']['pull_request']['branches'], [BRANCH])
        job = workflow['jobs']['deliver']
        self.assertIn('github.event.pull_request.merged == true', job['if'])
        self.assertIn('github.event.pull_request.head.repo.full_name == github.repository', job['if'])
        self.assertEqual(workflow['concurrency']['cancel-in-progress'], 'false')
        self.assertEqual(job['environment']['name'], 'hostinger-beta')
        self.assertEqual(job['permissions'].get('pull-requests'), 'read',
                         'The receiver independently reads the approved PR and owner review')
        text = (ROOT / '.github/workflows/hostinger-approved-deploy.yml').read_text()
        self.assertIn('StrictHostKeyChecking=yes', text)
        self.assertNotIn('ssh-keyscan', text)
        self.assertNotIn('git pull', text)

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
