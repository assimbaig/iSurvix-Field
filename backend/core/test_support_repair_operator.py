"""Operator repair tests use disposable Git sources and controlled Docker I/O.

Actual OS isolation and real PR publication are separate disposable-CI gates.
No operational database, media, secret or model is used by this module.
"""
from contextlib import contextmanager
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]


def module():
    spec = importlib.util.spec_from_file_location('support_repair_operator', ROOT / 'scripts/support_repair.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class SupportRepairOperatorTests(SimpleTestCase):
    def setUp(self):
        runs = ROOT / '.local/support-repair-tests'
        runs.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=runs)
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)
        self.tool = module()
        self.case_id = str(uuid.uuid4())
        self.repository = self.path / 'source'
        self.repository.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        self.git('config', 'user.name', 'Synthetic support repair')
        self.git('config', 'core.autocrlf', 'false')
        (self.repository / '.gitignore').write_text('.local/\n')
        fixture = self.repository / 'tests/fixtures/support_repair'
        fixture.mkdir(parents=True)
        counter = ('import json,sys\nfrom pathlib import Path\n'
                   'def count_unique(values):\n    return len(values)\n'
                   'if __name__=="__main__":\n'
                   ' source=Path(sys.argv[1]);target=Path(sys.argv[2]);data=json.loads(source.read_text())\n'
                   ' values=[item["photo_id"] for item in data["links"]]\n'
                   ' target.write_text(json.dumps({"unique_photos":count_unique(values),"links":len(data["links"])}))\n')
        (fixture / 'counter.py').write_text(counter)
        self.git('add', '.')
        self.git('commit', '-qm', 'TEST ONLY: synthetic duplicate-count defect')
        self.base = self.git('rev-parse', 'HEAD')
        snapshot = {'format': 'isurvix-support-health-v1', 'release': self.base,
                    'scope': {'kind': 'platform', 'company_id': None, 'project_id': None}}
        raw = self.tool.canonical(snapshot)
        manifest = {'format': 'isurvix-support-diagnostics-v1', 'case_id': self.case_id,
                    'report_sha256': hashlib.sha256(raw).hexdigest(), 'source_release': self.base}
        (fixture / 'manifest.json').write_bytes(self.tool.canonical(manifest))
        (fixture / 'diagnostics.json').write_bytes(raw)
        test = ('import sys,unittest\nfrom pathlib import Path\n'
                'sys.path.insert(0,str(Path(__file__).resolve().parent))\n'
                'from counter import count_unique\n'
                'class CounterTests(unittest.TestCase):\n'
                ' def test_repeated_evidence_is_counted_once(self):\n'
                '  self.assertEqual(count_unique(["photo-1","photo-1"]),1)\n')
        (fixture / 'test_unit.py').write_text(test)
        integration = ('import json,subprocess,sys,tempfile,unittest\nfrom pathlib import Path\n'
                       'class IntegrationTests(unittest.TestCase):\n'
                       ' def test_json_links_are_read_and_unique_count_is_saved(self):\n'
                       '  with tempfile.TemporaryDirectory() as directory:\n'
                       '   source=Path(directory)/"input.json";target=Path(directory)/"output.json"\n'
                       '   source.write_text(json.dumps({"links":[{"photo_id":"photo-1","field_id":"a"},{"photo_id":"photo-1","field_id":"b"},{"photo_id":"photo-2","field_id":"b"}]}))\n'
                       '   original=source.read_bytes()\n'
                       '   subprocess.run([sys.executable,str(Path(__file__).with_name("counter.py")),str(source),str(target)],check=True)\n'
                       '   self.assertEqual(json.loads(target.read_text()),{"unique_photos":2,"links":3})\n'
                       '   self.assertEqual(source.read_bytes(),original)\n')
        (fixture / 'test_integration.py').write_text(integration)
        self.git('add', '.')
        self.git('commit', '-qm', 'TEST ONLY: regression and integration checks')
        self.regression_commit = self.git('rev-parse', 'HEAD')
        self.regression = self.path / 'regression.patch'
        self.regression.write_bytes(self.git_bytes('diff', '--binary', self.base, self.regression_commit))
        (fixture / 'counter.py').write_text(counter.replace('return len(values)', 'return len(set(values))'))
        self.git('add', '.')
        self.git('commit', '-qm', 'TEST ONLY: preserve unique evidence count')
        self.target = self.git('rev-parse', 'HEAD')
        self.repair = self.path / 'repair.patch'
        self.repair.write_bytes(self.git_bytes('diff', '--binary', self.regression_commit, self.target))
        self.bundle = self.path / 'diagnostics.zip'
        self.write_bundle()
        self.image = 'sha256:' + 'a' * 64

    def git(self, *args):
        return self.git_bytes(*args).decode().strip()

    def git_bytes(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repository, stderr=subprocess.PIPE)

    def write_bundle(self, *, extra=None, wrong_digest=False):
        diagnostics = {'format': 'isurvix-support-health-v1', 'release': self.base,
                       'scope': {'kind': 'platform', 'company_id': None, 'project_id': None}}
        raw = json.dumps(diagnostics, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
        self.report_hash = hashlib.sha256(raw).hexdigest()
        manifest = {'format': 'isurvix-support-diagnostics-v1', 'case_id': self.case_id,
                    'report_sha256': '0' * 64 if wrong_digest else self.report_hash, 'source_release': self.base}
        with ZipFile(self.bundle, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(manifest))
            archive.writestr('diagnostics.json', raw)
            if extra:
                archive.writestr(*extra)

    def prepare(self, output=None, **changes):
        arguments = dict(repository=self.repository, output=output or self.path / 'prepared',
                         bundle=self.bundle, base_commit=self.base, tested_commit=self.target,
                         regression_patch=self.regression, repair_patch=self.repair,
                         profile='synthetic-stdlib', unit_labels=(), integration_labels=())
        arguments.update(changes)
        return self.tool.prepare(**arguments)

    def test_actual_pinned_git_snapshots_and_patch_tree_are_prepared_without_private_data(self):
        private = self.repository / '.local'
        private.mkdir()
        original = private / 'survey.sqlite3'
        original.write_bytes(b'ORIGINAL DATA NEVER COPY')
        before = original.read_bytes(), self.git('rev-parse', 'HEAD'), self.git('status', '--porcelain')
        result = self.prepare()
        self.assertEqual(result['case_id'], self.case_id)
        self.assertEqual(result['base_commit'], self.base)
        self.assertEqual(result['tested_commit'], self.target)
        self.assertEqual(result['report_sha256'], self.report_hash)
        for name in ('baseline.zip', 'candidate.zip'):
            with ZipFile(self.path / 'prepared' / name) as archive:
                self.assertTrue(any(n.endswith('test_integration.py') for n in archive.namelist()))
                self.assertFalse(any('.local' in n or '.git/' in n for n in archive.namelist()))
        self.assertEqual(before, (original.read_bytes(), self.git('rev-parse', 'HEAD'), self.git('status', '--porcelain')))

    def test_diagnostic_archive_rejects_extra_members_wrong_hash_duplicate_and_symlink(self):
        self.write_bundle(extra=('../outside', 'never extract'))
        with self.assertRaises(ValueError): self.tool.read_bundle(self.bundle)
        self.write_bundle(wrong_digest=True)
        with self.assertRaises(ValueError): self.tool.read_bundle(self.bundle)
        self.write_bundle()
        with ZipFile(self.bundle, 'a') as archive:
            member = ZipInfo('unexpected-link')
            member.external_attr = 0o120777 << 16
            archive.writestr(member, 'outside')
        with self.assertRaises(ValueError): self.tool.read_bundle(self.bundle)

    def test_case_report_and_exact_source_bindings_are_required(self):
        self.write_bundle()
        with self.assertRaises(ValueError): self.prepare(base_commit='b' * 40)
        self.write_bundle(wrong_digest=True)
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse((self.path / 'prepared').exists())

    def test_existing_destination_is_never_reused_or_overwritten(self):
        output = self.path / 'prepared'
        output.mkdir()
        sentinel = output / 'original.bin'
        sentinel.write_bytes(b'preserve')
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(sentinel.read_bytes(), b'preserve')

    def test_candidate_must_equal_the_two_reviewed_patches_not_an_unrelated_commit(self):
        fixture = self.repository / 'tests/fixtures/support_repair'
        (fixture / 'unrelated.py').write_text('UNRELATED = True\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Unapproved extra change')
        with self.assertRaises(ValueError): self.prepare(tested_commit=self.git('rev-parse', 'HEAD'))

    def test_patch_paths_cannot_modify_workflow_secrets_or_runtime_files(self):
        for destination in ('../outside.py', '.local/secret', '.github/workflows/run.yml', 'backend/media/data.txt'):
            with self.subTest(destination=destination):
                self.repair.write_text('diff --git a/' + destination + ' b/' + destination + '\n'
                                       'new file mode 100644\n--- /dev/null\n+++ b/' + destination + '\n@@ -0,0 +1 @@\n+unsafe\n')
                with self.assertRaises(ValueError): self.prepare()

    def test_source_with_a_tracked_private_artifact_is_refused_before_export(self):
        (self.repository / 'private-key.key').write_text('SYNTHETIC private artifact')
        self.git('add', '.')
        self.git('commit', '-qm', 'Synthetic forbidden artifact')
        target = self.git('rev-parse', 'HEAD')
        with self.assertRaises(ValueError): self.prepare(tested_commit=target)

    def test_docker_command_has_no_network_no_production_mount_no_credentials_and_no_pull(self):
        self.prepare()
        command = self.tool.docker_command(self.path / 'prepared', self.image, 'isurvix-support-' + uuid.uuid4().hex, uid=1001, gid=1001)
        text = ' '.join(command)
        self.assertIn('--network=none', command)
        self.assertIn('--read-only', command)
        self.assertIn('--pull=never', command)
        self.assertIn('--cap-drop=ALL', command)
        self.assertIn('--security-opt=no-new-privileges:true', command)
        self.assertIn('--user=1001:1001', command)
        self.assertNotIn(str(self.repository), text)
        self.assertNotIn('GITHUB_TOKEN', text)
        self.assertNotIn('docker.sock', text)
        self.assertNotIn('privileged', text)
        self.assertTrue(all('readonly' in part for part in command if part.startswith('type=bind,')))

    def test_unavailable_docker_stops_before_candidate_execution_or_false_receipt(self):
        self.prepare()
        with patch.object(self.tool, 'docker_preflight', side_effect=ValueError('Unavailable')):
            with self.assertRaises(ValueError): self.tool.run(self.path / 'prepared', self.image)
        self.assertFalse((self.path / 'prepared' / 'repair-receipt.json').exists())

    def test_mutable_images_and_modified_prepared_input_are_rejected(self):
        self.prepare()
        for image in ('python:3.12', 'sha256:short', 'other@latest'):
            with self.subTest(image=image), self.assertRaises(ValueError):
                self.tool.docker_command(self.path / 'prepared', image, 'isurvix-support-' + uuid.uuid4().hex, uid=1001, gid=1001)
        (self.path / 'prepared' / 'candidate.zip').write_bytes(b'changed after preparation')
        with self.assertRaises(ValueError): self.tool.validate_plan(self.path / 'prepared')

    def test_structured_receipt_is_case_bound_operator_attestation_and_never_approval(self):
        plan = self.prepare()
        proof = {'baseline_failed': True, 'patched_passed': True, 'unit_passed': True,
                 'integration_passed': True, 'isolation': 'docker-no-network', 'execution_id': str(uuid.uuid4())}
        receipt = self.tool.receipt(plan, proof)
        self.assertEqual(receipt['format'], 'isurvix-support-repair-v1')
        self.assertEqual(receipt['case_id'], self.case_id)
        self.assertEqual(receipt['tested_commit'], self.target)
        self.assertEqual(receipt['provenance'], 'operator-attested')
        self.assertEqual(receipt['pr_url'], '')
        self.assertIs(receipt['owner_release_approved'], False)
        with self.assertRaises(ValueError): self.tool.receipt(plan, {**proof, 'baseline_failed': False})

    def test_linking_real_pr_preserves_all_test_evidence_and_rejects_foreign_urls(self):
        plan = self.prepare()
        proof = {'baseline_failed': True, 'patched_passed': True, 'unit_passed': True,
                 'integration_passed': True, 'isolation': 'docker-no-network', 'execution_id': str(uuid.uuid4())}
        saved = self.tool.receipt(plan, proof)
        path = self.path / 'receipt.json'
        path.write_text(json.dumps(saved))
        target = self.path / 'linked.json'
        linked = self.tool.link_pr(path, 'https://github.com/assimbaig/iSurvix-Field/pull/123', target)
        self.assertEqual(linked, {**saved, 'pr_url': 'https://github.com/assimbaig/iSurvix-Field/pull/123'})
        for url in ('https://evil.invalid/pull/1', 'https://github.com/foreign/repo/pull/1',
                    'https://github.com/assimbaig/iSurvix-Field/pull/1?token=private'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.tool.link_pr(path, url, self.path / 'wrong.json')

    def test_real_trusted_synthetic_tests_reproduce_assertion_failure_then_pass_after_fix(self):
        # Functional parser/process integration only: this known test fixture is
        # not a Docker isolation proof and does not execute a user-uploaded patch.
        plan = self.prepare()
        with tempfile.TemporaryDirectory(dir=self.path) as tmp:
            workspace = Path(tmp)
            self.tool.extract_source(self.path / 'prepared' / 'baseline.zip', workspace / 'baseline')
            self.tool.extract_source(self.path / 'prepared' / 'candidate.zip', workspace / 'candidate')
            baseline = self.explicit_fixture_suite(workspace / 'baseline', 'unit', require_failure=True)
            candidate = self.explicit_fixture_suite(workspace / 'candidate', 'unit')
            integration = self.explicit_fixture_suite(workspace / 'candidate', 'integration')
        self.assertGreaterEqual(baseline['failures'], 1)
        self.assertEqual(baseline['errors'], 0)
        self.assertFalse(baseline['passed'])
        self.assertTrue(candidate['passed'])
        self.assertTrue(integration['passed'])

    def test_empty_or_broken_regression_does_not_count_as_reproduced_bug(self):
        for output, code in [('Ran 0 tests in 0.0s\nOK\n', 0),
                             ('Ran 1 test in 0.0s\nFAILED (errors=1)\n', 1),
                             ('Traceback: import failed\n', 1)]:
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.tool.test_result(output, code, require_failure=True)

    def test_claimed_container_success_without_real_isolation_probes_is_rejected(self):
        plan = self.prepare()
        proof = {'baseline_failed': True, 'patched_passed': True, 'unit_passed': True,
                 'integration_passed': True, 'isolation': 'docker-no-network', 'execution_id': str(uuid.uuid4())}
        evidence = {'receipt': self.tool.receipt(plan, proof), 'stages': {
            key: {'tests': 1, 'passed': key.startswith('candidate')} for key in
            ('baseline_unit', 'baseline_integration', 'candidate_unit', 'candidate_integration')}}
        with patch.object(self.tool, 'docker_preflight'), \
                patch.object(self.tool.os, 'getuid', return_value=1001, create=True), \
                patch.object(self.tool.os, 'getgid', return_value=1001, create=True), \
                patch.object(self.tool, 'bounded_process', return_value=(json.dumps(evidence), 0)), \
                patch.object(self.tool.subprocess, 'run', return_value=SimpleNamespace(returncode=0)):
            with self.assertRaises(ValueError):
                self.tool.run(self.path / 'prepared', self.image)
        self.assertFalse((self.path / 'prepared' / 'repair-receipt.json').exists())

    def test_published_fixture_rehearsal_uses_real_exact_commits_and_no_product_change(self):
        spec = importlib.util.spec_from_file_location('support_repair_rehearsal', ROOT / 'scripts/support_repair_rehearsal.py')
        rehearsal = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rehearsal)
        before = self.git('rev-parse', 'HEAD'), self.git('status', '--porcelain')
        result = rehearsal.prepare_rehearsal(self.repository, self.path / 'rehearsal', published_fixture=True)
        self.assertEqual(result['base_commit'], self.base)
        self.assertEqual(result['tested_commit'], self.target)
        self.assertEqual(result['profile'], 'synthetic-stdlib')
        self.assertEqual(result['case_id'], self.case_id)
        self.assertEqual(result['report_sha256'], self.report_hash)
        self.assertEqual(before, (self.git('rev-parse', 'HEAD'), self.git('status', '--porcelain')))

    def test_reviewed_runner_imports_from_its_actual_shallow_container_mount(self):
        # The real Docker command mounts this trusted script at /repair-tool.py.
        # Importing it must not assume the host repository's scripts/ depth.
        source = (ROOT / 'scripts/support_repair.py').read_text(encoding='utf-8')
        container_name = str(Path(ROOT.anchor) / 'repair-tool.py')
        namespace = {'__file__': container_name, '__name__': 'trusted_container_import_probe'}
        exec(compile(source, container_name, 'exec'), namespace)
        self.assertIn('container_run', namespace)

    def explicit_fixture_suite(self, workspace, stage, *, require_failure=False):
        # Version bridge for the SS1 RED: old code trusts its own candidate's
        # framework text. Fixed code receives an explicit known-fixture executor;
        # production has no host-execution fallback.
        plan = {'profile': 'synthetic-stdlib', 'unit_labels': [], 'integration_labels': []}
        if hasattr(self.tool, 'business_probe'):
            plan = self.tool.suite_plan(workspace)
            return self.tool.run_suite(workspace, plan, stage, require_failure=require_failure,
                probe_executor=lambda request: self.tool.business_probe(workspace, request))
        return self.tool.run_suite(workspace, plan, stage, require_failure=require_failure)

    def test_SS1_candidate_application_cannot_counterfeit_unchanged_regression_completion(self):
        self.prepare()
        with tempfile.TemporaryDirectory(dir=self.path) as temporary:
            workspace = self.tool.extract_source(self.path / 'prepared/candidate.zip', Path(temporary) / 'candidate')
            test = workspace / 'tests/fixtures/support_repair/test_unit.py'
            before = test.read_bytes()
            (test.parent / 'counter.py').write_text(
                'import os,sys\nsys.stdout.write("Ran 1 test in 0.001s\\n\\nOK\\n")\nsys.stdout.flush()\nos._exit(0)\n')
            result = self.explicit_fixture_suite(workspace, 'unit')
            self.assertFalse(result['passed'], 'Candidate console claims must not become the trusted verdict.')
            self.assertEqual(test.read_bytes(), before)

    def test_SS1_no_console_summary_can_be_used_as_authoritative_test_evidence(self):
        with self.assertRaises(ValueError):
            self.tool.test_result('Ran 1 test in 0.001s\n\nOK\n', 0)

    def test_SS1_generic_django_profile_is_refused_without_protected_blackbox_adapter(self):
        with self.assertRaises(ValueError):
            self.prepare(profile='django', unit_labels=['core.test_support'], integration_labels=['core.test_support'])
        self.assertFalse((self.path / 'prepared').exists())

    def test_SS1_candidate_cannot_change_regression_tests_and_keep_their_identity(self):
        test = self.repository / 'tests/fixtures/support_repair/test_unit.py'
        test.write_text(test.read_text().replace('class CounterTests', '@unittest.skip("ignore")\nclass CounterTests'))
        self.git('add', '.')
        self.git('commit', '-qm', 'Synthetic candidate attempts to skip the unchanged regression')
        target = self.git('rev-parse', 'HEAD')
        self.repair.write_bytes(self.git_bytes('diff', '--binary', self.regression_commit, target))
        with self.assertRaises(ValueError):
            self.prepare(tested_commit=target)

    def test_SS1_fake_json_early_exit_and_interrupted_application_are_rejected(self):
        self.prepare()
        with tempfile.TemporaryDirectory(dir=self.path) as temporary:
            workspace = self.tool.extract_source(self.path / 'prepared/candidate.zip', Path(temporary) / 'candidate')
            module = workspace / 'tests/fixtures/support_repair/counter.py'
            for source in ('import os\nos._exit(0)\n', 'import os\nos._exit(130)\n',
                           'import json,os\nprint(json.dumps({"tests":1,"passed":True}));os._exit(0)\n',
                           'MISSING_FUNCTION = True\n'):
                module.write_text(source)
                for stage in ('unit', 'integration'):
                    with self.subTest(source=source, stage=stage):
                        result = self.explicit_fixture_suite(workspace, stage)
                        self.assertFalse(result['passed'])
                        self.assertGreater(result['errors'], 0)
                        with self.assertRaises(ValueError):
                            self.explicit_fixture_suite(workspace, stage, require_failure=True)

    def test_SS1_host_oracle_rejects_fake_verdict_fields_types_and_replayed_identity(self):
        self.prepare()
        with tempfile.TemporaryDirectory(dir=self.path) as temporary:
            workspace = self.tool.extract_source(self.path / 'prepared/candidate.zip', Path(temporary) / 'candidate')
            plan = self.tool.suite_plan(workspace)
            request = self.tool.probe_request('unit', plan['test_identities']['unit'])
            genuine = self.tool.business_probe(workspace, request)
            self.assertTrue(self.tool.evaluate_probe(request, genuine)['passed'])
            variants = []
            variants.append({**genuine, 'probe_id': str(uuid.uuid4())})
            variants.append({**genuine, 'passed': True})
            for business in ({'value': True}, {'value': '1'}, {'value': 0, 'passed': True}, {'tests': 1, 'passed': True}):
                changed = json.loads(json.dumps(genuine))
                changed['observations'][0]['business'] = business
                variants.append(changed)
            for changed in variants:
                with self.subTest(response=changed):
                    self.assertFalse(self.tool.evaluate_probe(request, changed)['passed'])

    def test_SS1_zero_skipped_changed_regressions_and_changed_controller_fail_closed(self):
        self.prepare()
        with tempfile.TemporaryDirectory(dir=self.path) as temporary:
            workspace = self.tool.extract_source(self.path / 'prepared/candidate.zip', Path(temporary) / 'candidate')
            plan = self.tool.suite_plan(workspace)
            with self.assertRaises(ValueError):
                self.tool.run_suite(workspace, plan, 'unit')
            for key in ('controller_sha256', 'runner_sha256'):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    self.tool.run_suite(workspace, {**plan, key: '0' * 64}, 'unit',
                        probe_executor=lambda _request: self.fail('Changed controller must not execute a candidate'))
            unit = workspace / 'tests/fixtures/support_repair/test_unit.py'
            original = unit.read_text()
            for text in ('NO_TESTS = True\n', original.replace('class CounterTests', '@unittest.skip("skip")\nclass CounterTests')):
                unit.write_text(text)
                with self.assertRaises(ValueError):
                    self.tool.suite_plan(workspace)
            unit.write_text(original + '\n# changed regression identity\n')
            with self.assertRaises(ValueError):
                self.tool.run_suite(workspace, plan, 'unit',
                    probe_executor=lambda _request: self.fail('Changed regression must not execute a candidate'))

    def test_SS1_interrupted_external_probe_does_not_become_success(self):
        self.prepare()
        with tempfile.TemporaryDirectory(dir=self.path) as temporary:
            workspace = self.tool.extract_source(self.path / 'prepared/candidate.zip', Path(temporary) / 'candidate')
            plan = self.tool.suite_plan(workspace)
            def interrupted(_request):
                raise ValueError('Controlled interrupted probe')
            with self.assertRaises(ValueError):
                self.tool.run_suite(workspace, plan, 'unit', probe_executor=interrupted)
