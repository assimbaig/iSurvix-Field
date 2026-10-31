"""Customer bundle tests use exact disposable Git sources and controlled Docker.

These ordinary tests do not claim a native Docker or second-device LAN install.
The explicit disposable Linux rehearsal is a separate acceptance gate.
"""
import hashlib
from contextlib import closing
import importlib.util
import json
import os
import sqlite3
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]


def module():
    spec = importlib.util.spec_from_file_location('customer_package', ROOT/'deploy/customer/customer.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class CustomerPackageTests(SimpleTestCase):
    def setUp(self):
        temp = ROOT/'.local/customer-package-tests'
        temp.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=temp)
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name)
        self.customer = module()
        self.release = 'a'*40
        self.app = 'sha256:'+'b'*64
        self.proxy = 'sha256:'+'c'*64

    def bundle(self):
        root = self.path/'bundle'
        root.mkdir()
        (root/'release').mkdir()
        (root/'release/RELEASE').write_text(self.release+'\n')
        (root/'images').mkdir()
        (root/'images/server-images.tar').write_bytes(b'controlled-image-archive')
        # The runtime reuses the exact shared staging helper/template.
        (root/'release/deploy/customer').mkdir(parents=True)
        for name in ('staging.py', 'nginx.conf.template'):
            (root/'release/deploy'/name).write_bytes((ROOT/'deploy'/name).read_bytes())
        for name in ('compose.yaml',):
            (root/'release/deploy/customer'/name).write_bytes((ROOT/'deploy/customer'/name).read_bytes())
        (root/'release/deploy/customer/customer.py').write_bytes((ROOT/'deploy/customer/customer.py').read_bytes())
        (root/'release/backend/core').mkdir(parents=True)
        (root/'release/backend/core/operations_backup.py').write_bytes((ROOT/'backend/core/operations_backup.py').read_bytes())
        files = {p.relative_to(root).as_posix(): {'size': p.stat().st_size,
                    'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                 for p in root.rglob('*') if p.is_file()}
        manifest = {'format': 'isurvix-customer-bundle-v1', 'status': 'draft-for-review',
            'release_id': self.release, 'target': {'os': 'linux', 'architecture': 'amd64'},
            'images': {'app': self.app, 'nginx': self.proxy}, 'files': files,
            'owner_release_approved': False}
        (root/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return root

    def private_inputs(self):
        secret = self.path/'private/key'
        secret.parent.mkdir()
        secret.write_text('synthetic-test-secret-value-'+'x'*60)
        tls = self.path/'tls'
        tls.mkdir()
        (tls/'fullchain.pem').write_text('SYNTHETIC certificate')
        (tls/'privkey.pem').write_text('SYNTHETIC private key')
        return secret, tls

    def prepare(self, **changes):
        bundle = self.bundle()
        secret, tls = self.private_inputs()
        values = {'host': 'customer.example.test', 'lan_ip': '192.168.10.5',
                  'secret_file': secret, 'tls_directory': tls, 'acknowledge_draft': True,
                  **changes}
        return bundle, self.customer.prepare_runtime(bundle, self.path/'runtime', **values)

    def test_lan_binding_accepts_only_explicit_rfc1918_addresses(self):
        for value in ('10.20.30.40', '172.16.4.5', '192.168.4.5'):
            self.assertEqual(self.customer.validate_lan_address(value), value)
        for value in ('0.0.0.0', '127.0.0.1', '8.8.8.8', '169.254.10.1',
                      '192.0.2.1', '::', '::1', 'localhost', '172.15.0.1', '192.168.1.1\n'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.customer.validate_lan_address(value)

    def test_manifest_requires_exact_inventory_and_digests(self):
        bundle = self.bundle()
        self.assertEqual(self.customer.verify_package(bundle)['release_id'], self.release)
        (bundle/'images/server-images.tar').write_bytes(b'corrupted')
        with self.assertRaises(ValueError):
            self.customer.verify_package(bundle)

    def test_required_installer_files_cannot_be_removed_by_rewriting_inventory(self):
        bundle = self.bundle()
        manifest = json.loads((bundle/'manifest.json').read_text())
        name = 'release/deploy/customer/compose.yaml'
        (bundle/name).unlink()
        del manifest['files'][name]
        (bundle/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(ValueError): self.customer.verify_package(bundle)

    def test_unknown_files_and_incomplete_bundles_fail_closed(self):
        bundle = self.bundle()
        (bundle/'unlisted').write_text('unknown')
        with self.assertRaises(ValueError): self.customer.verify_package(bundle)
        (bundle/'unlisted').unlink()
        (bundle/'INCOMPLETE').write_text('interrupted')
        with self.assertRaises(ValueError): self.customer.verify_package(bundle)

    def test_manifest_path_traversal_never_reads_external_file(self):
        bundle = self.bundle()
        payload = json.loads((bundle/'manifest.json').read_text())
        payload['files']['../outside'] = {'size': 1, 'sha256': 'd'*64}
        (bundle/'manifest.json').write_text(json.dumps(payload))
        with self.assertRaises(ValueError): self.customer.verify_package(bundle)
        self.assertFalse((self.path/'outside').exists())

    def test_release_in_source_must_match_manifest(self):
        bundle = self.bundle()
        payload = json.loads((bundle/'manifest.json').read_text())
        payload['release_id'] = 'e'*40
        (bundle/'manifest.json').write_text(json.dumps(payload))
        with self.assertRaises(ValueError): self.customer.verify_package(bundle)

    def test_manifest_out_of_band_digest_detects_replacement(self):
        bundle = self.bundle()
        with self.assertRaises(ValueError):
            self.customer.verify_package(bundle, expected_manifest_sha256='0'*64)
        actual = hashlib.sha256((bundle/'manifest.json').read_bytes()).hexdigest()
        self.customer.verify_package(bundle, expected_manifest_sha256=actual)

    def test_fresh_runtime_preserves_external_secrets_and_supplies_private_bind(self):
        bundle, result = self.prepare()
        runtime = self.path/'runtime'
        self.assertEqual(result['release_id'], self.release)
        if os.name == 'posix':
            self.assertEqual((runtime/'data').stat().st_mode & 0o777, 0o700)
            self.assertTrue(result['posix_permissions_verified'])
        else:
            self.assertFalse(result['posix_permissions_verified'])
        self.assertTrue((runtime/'data/media').is_dir())
        env = (runtime/'customer.env').read_text()
        values = {line.split('=', 1)[0]: json.loads(line.split('=', 1)[1]) for line in env.splitlines()}
        self.assertEqual(values['ISURVIX_LAN_IP'], '192.168.10.5')
        self.assertNotIn('synthetic-test-secret-value', env)
        self.assertIn('return 404', (runtime/'nginx.conf').read_text())
        self.assertFalse((runtime/'data/database.sqlite3').exists())

    def test_existing_runtime_is_preserved_and_never_becomes_empty_install(self):
        bundle = self.bundle()
        secret, tls = self.private_inputs()
        runtime = self.path/'runtime'
        runtime.mkdir()
        (runtime/'sentinel').write_text('preserve')
        with self.assertRaises(ValueError):
            self.customer.prepare_runtime(bundle, runtime, host='customer.example.test',
                lan_ip='192.168.1.5', secret_file=secret, tls_directory=tls,
                acknowledge_draft=True)
        self.assertEqual((runtime/'sentinel').read_text(), 'preserve')

    def test_candidate_cannot_silently_run_as_owner_approved_release(self):
        bundle = self.bundle()
        secret, tls = self.private_inputs()
        with self.assertRaises(ValueError):
            self.customer.prepare_runtime(bundle, self.path/'runtime',
                host='customer.example.test', lan_ip='192.168.1.5', secret_file=secret,
                tls_directory=tls)
        self.assertFalse((self.path/'runtime').exists())

    def test_load_uses_only_bundled_image_archive_and_no_pull(self):
        bundle = self.bundle()
        calls = []
        def docker(*args):
            calls.append(args)
            if args[:2] == ('image', 'inspect'):
                return json.dumps([{'Id': args[2], 'Os': 'linux', 'Architecture': 'amd64'}]).encode()
            return b'loaded'
        with patch.object(self.customer, '_docker', side_effect=docker):
            self.customer.load_images(bundle, acknowledge_draft=True)
        self.assertEqual(calls[0], ('image', 'load', '--input', str(bundle/'images/server-images.tar')))
        self.assertFalse(any('pull' in args for args in calls))

    def test_initialize_migrates_only_new_database_with_no_installer_download(self):
        bundle, _ = self.prepare()
        calls = []
        with patch.object(self.customer, '_docker', side_effect=lambda *args: calls.append(args) or b''):
            self.customer.run_action(bundle, self.path/'runtime', 'initialize', acknowledge_draft=True)
        text = str(calls)
        self.assertIn('migrate', text)
        self.assertIn('collectstatic', text)
        self.assertNotIn('pip', text)
        self.assertNotIn(' pull', text)
        self.assertNotIn('createsuperuser', text)
        self.assertTrue(all('--pull' not in args or 'never' in args for args in calls))

    def test_initialize_refuses_existing_database_without_invoking_docker(self):
        bundle, _ = self.prepare()
        database = self.path/'runtime/data/database.sqlite3'
        database.write_bytes(b'existing-evidence-records')
        with patch.object(self.customer, '_docker') as docker, self.assertRaises(ValueError):
            self.customer.run_action(bundle, self.path/'runtime', 'initialize', acknowledge_draft=True)
        docker.assert_not_called()
        self.assertEqual(database.read_bytes(), b'existing-evidence-records')

    def test_changed_runtime_configuration_prevents_start_before_docker(self):
        bundle, _ = self.prepare()
        (self.path/'runtime/customer.env').write_text('ISURVIX_LAN_IP=0.0.0.0\n')
        with patch.object(self.customer, '_docker') as docker, self.assertRaises(ValueError):
            self.customer.run_action(bundle, self.path/'runtime', 'start', acknowledge_draft=True)
        docker.assert_not_called()

    def test_failed_initialization_preserves_partial_database_and_prevents_blind_retry(self):
        bundle, _ = self.prepare()
        database = self.path/'runtime/data/database.sqlite3'
        def fail(*args):
            database.write_bytes(b'partial migration evidence')
            raise ValueError('controlled migration failure')
        with patch.object(self.customer, '_docker', side_effect=fail), self.assertRaises(ValueError):
            self.customer.run_action(bundle, self.path/'runtime', 'initialize', acknowledge_draft=True)
        with patch.object(self.customer, '_docker') as docker, self.assertRaises(ValueError):
            self.customer.run_action(bundle, self.path/'runtime', 'initialize', acknowledge_draft=True)
        docker.assert_not_called()
        self.assertEqual(database.read_bytes(), b'partial migration evidence')
        self.assertFalse((self.path/'runtime/initialized.json').exists())

    def test_stop_never_deletes_persistent_volumes_or_uses_down(self):
        bundle, _ = self.prepare()
        calls = []
        with patch.object(self.customer, '_docker', side_effect=lambda *args: calls.append(args) or b''):
            self.customer.run_action(bundle, self.path/'runtime', 'stop', acknowledge_draft=True)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][-1], 'stop')
        self.assertNotIn('down', calls[0])

    def test_immutable_bundle_is_not_changed_by_repeated_prepare_verification(self):
        bundle, _ = self.prepare()
        before = {name: self.customer._digest(path) for name, path in self.customer._files(bundle).items()}
        self.customer.verify_package(bundle)
        self.customer._runtime(bundle, self.path/'runtime')
        after = {name: self.customer._digest(path) for name, path in self.customer._files(bundle).items()}
        self.assertEqual(before, after)

    def test_verified_backup_restores_only_into_new_runtime_and_requires_explicit_migration(self):
        from core.operations_backup import create_backup
        bundle = self.bundle()
        secret, tls = self.private_inputs()
        original = self.path/'source.sqlite3'
        with closing(sqlite3.connect(original)) as db:
            db.execute('create table retained (value text)')
            db.execute("insert into retained values ('original-human-decision')")
            db.commit()
        media = self.path/'original-media'
        media.mkdir()
        (media/'evidence.jpg').write_bytes(b'original-evidence-bytes')
        backup = self.path/'verified-backup'
        create_backup(original, media, backup, release_id='d'*40, quiesced=True)
        source_hash = hashlib.sha256(original.read_bytes()).hexdigest()
        runtime = self.path/'restored-runtime'
        self.customer.prepare_runtime(bundle, runtime, host='customer.example.test', lan_ip='10.20.30.40',
            secret_file=secret, tls_directory=tls, acknowledge_draft=True, restore_backup=backup)
        self.assertEqual((runtime/'data/media/evidence.jpg').read_bytes(), b'original-evidence-bytes')
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), source_hash)
        self.assertFalse((runtime/'initialized.json').exists())
        with patch.object(self.customer, '_docker') as docker, self.assertRaises(ValueError):
            self.customer.run_action(bundle, runtime, 'start', acknowledge_draft=True)
        docker.assert_not_called()
        calls = []
        with patch.object(self.customer, '_docker', side_effect=lambda *args: calls.append(args) or b''):
            self.customer.run_action(bundle, runtime, 'migrate-restored', acknowledge_draft=True)
        self.assertTrue((runtime/'initialized.json').is_file())
        self.assertTrue(any('migrate' in args for args in calls))
        self.assertFalse(any('ISURVIX_INITIALIZE_DATABASE=yes' in args for args in calls))
        with patch.object(self.customer, '_docker') as docker, self.assertRaises(ValueError):
            self.customer.run_action(bundle, runtime, 'migrate-restored', acknowledge_draft=True)
        docker.assert_not_called()

    def test_remote_docker_environment_cannot_retarget_package_operations(self):
        with patch.dict(os.environ, {'DOCKER_HOST': 'ssh://foreign-host'}, clear=True), \
             patch.object(self.customer.subprocess, 'run') as run, self.assertRaises(ValueError):
            self.customer._docker('image', 'load', '--input', '/candidate/images.tar')
        run.assert_not_called()

    def test_remote_selected_docker_context_is_rejected_before_image_operation(self):
        from types import SimpleNamespace
        result = SimpleNamespace(returncode=0, stdout=b'ssh://foreign-host\n')
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(self.customer.subprocess, 'run', return_value=result) as run, self.assertRaises(ValueError):
            self.customer._docker('image', 'load', '--input', '/candidate/images.tar')
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][1:3], ['context', 'inspect'])

    def test_customer_compose_keeps_backend_internal_and_images_offline(self):
        text = (ROOT/'deploy/customer/compose.yaml').read_text()
        self.assertIn('${ISURVIX_LAN_IP', text)
        self.assertNotIn('127.0.0.1:8443', text)
        self.assertNotIn('0.0.0.0:8443', text)
        self.assertEqual(text.count('pull_policy: never'), 2)
        self.assertIn('internal: true', text)
        self.assertNotIn('11434:', text)


class CustomerBuilderIntegrationTests(SimpleTestCase):
    def test_exact_clean_git_export_and_baked_image_release_are_required(self):
        customer = module()
        base = ROOT/'.local/customer-package-tests'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            path = Path(temporary)
            repo = path/'repo'
            repo.mkdir()
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()
            git('init', '-q')
            git('config', 'user.email', 'synthetic@example.invalid')
            git('config', 'user.name', 'Synthetic package test')
            (repo/'tracked.txt').write_text('included')
            (repo/'deploy/customer').mkdir(parents=True)
            (repo/'backend/core').mkdir(parents=True)
            for source, target in [('deploy/customer/customer.py', 'deploy/customer/customer.py'),
                                   ('deploy/customer/compose.yaml', 'deploy/customer/compose.yaml'),
                                   ('deploy/staging.py', 'deploy/staging.py'),
                                   ('deploy/nginx.conf.template', 'deploy/nginx.conf.template'),
                                   ('backend/core/operations_backup.py', 'backend/core/operations_backup.py')]:
                (repo/target).write_bytes((ROOT/source).read_bytes())
            git('add', '.')
            git('commit', '-qm', 'synthetic source')
            release = git('rev-parse', 'HEAD')
            app, proxy = 'sha256:'+'b'*64, 'sha256:'+'c'*64
            def docker(*args):
                if args[:2] == ('image', 'inspect'):
                    return json.dumps([{'Id': args[2], 'Os': 'linux', 'Architecture': 'amd64'}]).encode()
                if args[:2] == ('image', 'save'):
                    Path(args[3]).write_bytes(b'controlled image transfer fixture')
                    return b''
                if args[-1] == '/app/RELEASE': return (release+'\n').encode()
                if args[-1] in ('/app/DEPENDENCIES.lock', '/app/OS-PACKAGES.lock'): return b'synthetic-inventory\n'
                return b'[]'
            with patch.object(customer, '_docker', side_effect=docker):
                result = customer.build_package(repo, path/'bundle', release, app, proxy)
            self.assertEqual(result['release_id'], release)
            self.assertEqual((path/'bundle/release/tracked.txt').read_text(), 'included')
            customer.verify_package(path/'bundle')
            (repo/'untracked-private.txt').write_text('never distribute')
            with patch.object(customer, '_docker') as invoke, self.assertRaises(ValueError):
                customer.build_package(repo, path/'other', release, app, proxy)
            invoke.assert_not_called()
            self.assertFalse((path/'other').exists())
