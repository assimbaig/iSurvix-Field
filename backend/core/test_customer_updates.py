"""Host-updater tests: real disposable SQLite/media, controlled local Docker.

Actual Linux containers and a second physical customer device remain separate
acceptance gates. These tests never modify an operational database or account.
"""
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time
import uuid
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings


ROOT = Path(__file__).resolve().parents[2]


def module():
    spec = importlib.util.spec_from_file_location('customer_updater', ROOT/'deploy/customer/updater.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class CustomerUpdateTests(SimpleTestCase):
    def setUp(self):
        directory = ROOT/'.local/customer-update-tests'
        directory.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=directory)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.updater = module()
        self.source = 'a'*40
        self.target = 'b'*40
        self.request_id = str(uuid.uuid4())
        self.secret = 'synthetic-host-update-secret-'+'x'*60
        self.private = self.path/'private'
        self.private.mkdir()
        (self.private/'secret').write_text(self.secret)
        (self.private/'tls').mkdir()
        for name in ('privkey.pem', 'fullchain.pem'):
            (self.private/'tls'/name).write_text('SYNTHETIC test '+name)
        self.updates = self.path/'updates'
        self.updates.mkdir()
        (self.updates/'receipts').mkdir()
        (self.updates/'catalog.json').write_text(json.dumps({'format': 'isurvix-update-catalog-v1', 'releases': []}))
        self.packages = self.path/'approved'
        self.packages.mkdir()
        self.journals = self.path/'journals'
        self.journals.mkdir()
        self.source_package = self.bundle(self.path/'source-package', self.source)
        destination = self.packages/self.target
        destination.mkdir()
        self.target_package = self.bundle(destination/'package', self.target)
        self.source_runtime = self.path/'source-runtime'
        self.updater.customer.prepare_runtime(self.source_package, self.source_runtime,
            host='customer.example.test', lan_ip='192.168.10.5',
            secret_file=self.private/'secret', tls_directory=self.private/'tls', acknowledge_draft=True,
            update_directory=self.updates)
        self.target_runtime = self.path/'target-runtime'
        database = self.source_runtime/'data/database.sqlite3'
        with closing(sqlite3.connect(database)) as db:
            db.execute('create table retained (id integer primary key, human_answer text)')
            db.execute('insert into retained values (1, ?)', ('confirmed human answer',))
            db.commit()
        (self.source_runtime/'data/media/original.bin').write_bytes(b'Original evidence: preserve exact bytes.')
        (self.source_runtime/'initialized.json').write_text('{}')
        row = {'release_id': self.target,
               'manifest_sha256': self.updater.customer._digest(self.target_package/'manifest.json')['sha256'],
               'supported_from': [self.source], 'editions': ['customer']}
        self.catalog = {'format': 'isurvix-update-catalog-v1', 'releases': [row]}
        self.catalog_write()
        now = int(time.time())
        self.payload = {'format': 'isurvix-update-request-v1', 'request_id': self.request_id,
            'request_key': str(uuid.uuid4()), 'source_release': self.source, 'target_release': self.target,
            'manifest_sha256': row['manifest_sha256'], 'catalog_sha256': self.updater.customer._digest(self.updates/'catalog.json')['sha256'],
            'edition': 'customer', 'nonce': 'e'*32, 'maintenance_confirmed': True,
            'release_record_sha256': '', 'issued_at': now, 'expires_at': now+300}
        self.calls = []
        self.running = {}
        self.fail_migration = False
        self.fail_activation = False
        self.withdrawn = False
        self.bad_health = False
        self.change_legacy_row = False
        self.interrupt_migration = False
        self.revoke_after_image_load = False
        self.images_loaded = False

    def bundle(self, destination, release):
        (destination/'release/deploy/customer').mkdir(parents=True)
        (destination/'release/backend/core').mkdir(parents=True)
        (destination/'images').mkdir()
        (destination/'images/server-images.tar').write_bytes(b'Controlled image archive: not native Docker.')
        (destination/'release/RELEASE').write_text(release+'\n')
        for name in ('staging.py', 'nginx.conf.template'):
            shutil.copyfile(ROOT/'deploy'/name, destination/'release/deploy'/name)
        for name in ('customer.py', 'compose.yaml', 'compose.updates.yaml', 'upgrade_fixture.py'):
            shutil.copyfile(ROOT/'deploy/customer'/name, destination/'release/deploy/customer'/name)
        shutil.copyfile(ROOT/'backend/core/operations_backup.py', destination/'release/backend/core/operations_backup.py')
        files = {path.relative_to(destination).as_posix(): self.updater.customer._digest(path)
                 for path in destination.rglob('*') if path.is_file()}
        manifest = {'format': 'isurvix-customer-bundle-v1', 'status': 'draft-for-review',
            'release_id': release, 'target': {'os': 'linux', 'architecture': 'amd64'},
            'images': {'app': 'sha256:'+'c'*64, 'nginx': 'sha256:'+'d'*64},
            'files': files, 'owner_release_approved': False}
        (destination/'manifest.json').write_text(json.dumps(manifest))
        return destination

    def catalog_write(self):
        (self.updates/'catalog.json').write_text(json.dumps(self.catalog))

    def signed(self, payload=None):
        payload = self.payload if payload is None else payload
        return {'payload': payload, 'signature': self.updater.signature(self.secret, 'request-v1', payload)}

    def docker(self, *args):
        args = tuple(map(str, args))
        self.calls.append(args)
        if args[:2] == ('image', 'load'):
            self.images_loaded = True
            return b''
        if args[:2] == ('image', 'inspect'):
            return json.dumps([{'Id': args[2], 'Os': 'linux', 'Architecture': 'amd64'}]).encode()
        runtime = Path(args[args.index('--env-file')+1]).parent
        release = self.source if runtime == self.source_runtime else self.target
        if 'export' in args:
            if self.revoke_after_image_load and self.images_loaded:
                raise ValueError('Controlled requester revocation after package verification.')
            return json.dumps(self.signed()).encode()
        if 'receipt' in args:
            if self.withdrawn:
                raise ValueError('Controlled withdrawal: acknowledgement denied.')
            name = Path(args[args.index('--receipt-file')+1])
            receipt = json.loads((self.updates/'receipts'/name.parent.name/name.name).read_text())['payload']
            return json.dumps({'request_id': self.request_id, 'status': receipt['status'], 'sequence': receipt['sequence']}).encode()
        if 'stop' in args:
            self.running[runtime] = False
        if 'ps' in args:
            return json.dumps([{'Service': 'web', 'State': 'running' if self.running.get(runtime) else 'exited'}]).encode()
        if 'up' in args:
            if 'proxy' in args and self.fail_activation:
                raise ValueError('Controlled uncertain proxy activation.')
            self.running[runtime] = True
        if 'migrate' in args:
            if self.interrupt_migration:
                raise KeyboardInterrupt('Controlled process interruption.')
            if self.fail_migration:
                raise ValueError('Controlled migration failure.')
            with closing(sqlite3.connect(runtime/'data/database.sqlite3')) as db:
                db.execute('create table if not exists added_table (id integer primary key)')
                if self.change_legacy_row:
                    db.execute("update retained set human_answer='incorrect changed answer'")
                db.commit()
        if '/app/deploy/healthcheck.py' in args and self.bad_health and runtime != self.source_runtime:
            raise ValueError('Controlled health failure.')
        if '/app/RELEASE' in args:
            return (release+'\n').encode()
        return b''

    def apply(self, action='apply'):
        with patch.object(self.updater.customer, '_docker', side_effect=self.docker), patch.object(self.updater.time, 'sleep'):
            operation = self.updater.apply_update if action == 'apply' else self.updater.recover_update
            return operation(installed_package=self.source_package,
                installed_runtime=self.source_runtime, update_directory=self.updates,
                packages_root=self.packages, target_runtime=self.target_runtime,
                journal_root=self.journals, request_id=self.request_id,
                acknowledge_draft=True, maintenance_confirmed=True)

    def test_request_signature_expiry_and_binding_are_checked(self):
        self.assertEqual(self.updater.verify_request(self.signed(), self.secret, self.request_id)['target_release'], self.target)
        for changes in ({'request_id': str(uuid.uuid4())}, {'expires_at': 1},
                        {'maintenance_confirmed': False}, {'target_release': '../escape'}, {'nonce': 'bad'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.updater.verify_request(self.signed({**self.payload, **changes}), self.secret, self.request_id)
        malformed = self.signed()
        malformed['payload'] = {**self.payload, 'edition': 'cloud'}
        with self.assertRaises(ValueError):
            self.updater.verify_request(malformed, self.secret, self.request_id)

    def test_success_quiesces_backs_up_copies_migrates_and_activates_once(self):
        original = (self.source_runtime/'data/media/original.bin').read_bytes()
        result = self.apply()
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['release_id'], self.target)
        self.assertEqual((self.target_runtime/'data/media/original.bin').read_bytes(), original)
        self.assertEqual((self.source_runtime/'data/media/original.bin').read_bytes(), original)
        with closing(sqlite3.connect(self.target_runtime/'data/database.sqlite3')) as db:
            self.assertEqual(db.execute('select human_answer from retained').fetchone(), ('confirmed human answer',))
        receipt_paths = sorted((self.updates/'receipts'/self.request_id).glob('*.json'))
        states = [json.loads(path.read_text())['payload']['status'] for path in receipt_paths]
        self.assertEqual(states, ['verified', 'applying', 'completed'])
        first_stop = next(i for i, args in enumerate(self.calls) if 'stop' in args)
        acknowledgements = [args for args in self.calls[:first_stop] if 'receipt' in args]
        self.assertEqual(len(acknowledgements), 2)
        before = len(self.calls)
        self.assertEqual(self.apply(), result)
        self.assertEqual(len(self.calls), before, 'Completed replay must not run Docker or create another candidate.')
        self.assertTrue((self.journals/self.request_id/'backup/manifest.json').is_file())

    def test_withdrawn_or_unacknowledged_request_never_stops_writers(self):
        self.withdrawn = True
        with self.assertRaises(ValueError): self.apply()
        self.assertFalse(any('stop' in call for call in self.calls))
        self.assertFalse(self.target_runtime.exists())

    def test_modified_catalog_corrupt_candidate_and_unsupported_source_fail_before_stop(self):
        for kind in ('catalog', 'package', 'source'):
            with self.subTest(kind=kind):
                if kind == 'catalog':
                    self.catalog['releases'][0]['editions'] = ['cloud']
                    self.catalog_write()
                elif kind == 'package':
                    self.catalog['releases'][0]['editions'] = ['customer']
                    self.catalog_write()
                    self.payload['catalog_sha256'] = self.updater.customer._digest(self.updates/'catalog.json')['sha256']
                    (self.target_package/'images/server-images.tar').write_bytes(b'corrupt')
                else:
                    (self.target_package/'images/server-images.tar').write_bytes(b'Controlled image archive: not native Docker.')
                    self.catalog['releases'][0]['supported_from'] = ['f'*40]
                    self.catalog_write()
                    self.payload['catalog_sha256'] = self.updater.customer._digest(self.updates/'catalog.json')['sha256']
                with self.assertRaises(ValueError): self.apply()
                self.assertFalse(any('stop' in call for call in self.calls))
                self.assertFalse(self.target_runtime.exists())

    def test_migration_failure_rolls_back_without_reusing_or_overwriting_candidate(self):
        self.fail_migration = True
        result = self.apply()
        self.assertEqual(result['status'], 'rolled_back')
        self.assertEqual(result['error_code'], 'migration_failed')
        self.assertTrue(self.target_runtime.exists(), 'Preserve failed candidate for diagnosis.')
        self.assertTrue(self.running[self.source_runtime])
        self.assertEqual(self.apply(), result, 'Replay of failed transaction is terminal; request a new maintenance revision.')
        self.assertFalse(any('proxy' in call and 'up' in call for call in self.calls
                             if str(self.target_runtime/'customer.env') in call))

    def test_changed_human_rows_or_failed_health_prevent_proxy_activation(self):
        for changed in ('row', 'health'):
            # Separate transaction/runtime/request identities, preserving each
            # previous failed candidate rather than recycling its directory.
            with self.subTest(changed=changed):
                self.change_legacy_row = changed == 'row'
                self.bad_health = changed == 'health'
                self.request_id = str(uuid.uuid4())
                self.payload['request_id'] = self.request_id
                self.target_runtime = self.path/('target-'+changed)
                result = self.apply()
                self.assertEqual(result['status'], 'rolled_back')
                self.assertFalse(any('up' in call and 'proxy' in call
                                     for call in self.calls if str(self.target_runtime/'customer.env') in call))

    def test_activation_uncertainty_preserves_both_and_never_restarts_old_proxy(self):
        self.fail_activation = True
        result = self.apply()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error_code'], 'activation_uncertain')
        self.assertTrue(self.target_runtime.exists())
        self.assertFalse(self.running.get(self.source_runtime, False))
        first_stop = next(i for i, call in enumerate(self.calls) if 'stop' in call)
        self.assertFalse(any('up' in call and str(self.source_runtime/'customer.env') in call
                             for call in self.calls[first_stop+1:]))

    def test_existing_target_and_runtime_journal_overlap_are_rejected_without_writes(self):
        self.target_runtime.mkdir()
        sentinel = self.target_runtime/'preserve'
        sentinel.write_bytes(b'Existing bytes')
        with self.assertRaises(ValueError): self.apply()
        self.assertEqual(sentinel.read_bytes(), b'Existing bytes')
        self.assertFalse(any('stop' in call for call in self.calls))
        self.target_runtime = self.path/'another-target'
        self.journals = self.source_runtime/'data/journals'
        self.journals.mkdir()
        with self.assertRaises(ValueError): self.apply()
        self.assertFalse(any('stop' in call for call in self.calls))

    def test_interrupted_before_activation_requires_recovery_and_preserves_snapshot(self):
        # A killed operator process cannot release authority from a rolled-back
        # application DB. The independent journal remains the recovery anchor.
        self.fail_migration = True
        self.apply()
        journal = self.journals/self.request_id/'journal.json'
        value = json.loads(journal.read_text())
        value['phase'] = 'migrating'
        value.pop('result', None)
        journal.write_text(json.dumps(value))
        before = len(self.calls)
        with self.assertRaisesRegex(ValueError, 'recovery'):
            self.apply()
        self.assertEqual(len(self.calls), before)
        self.assertTrue((self.journals/self.request_id/'backup/database.sqlite3').is_file())

    def test_explicit_pre_activation_recovery_uses_independent_journal_and_preserves_partial_target(self):
        self.interrupt_migration = True
        with self.assertRaises(KeyboardInterrupt): self.apply()
        journal = self.journals/self.request_id/'journal.json'
        self.assertEqual(json.loads(journal.read_text())['phase'], 'migrating')
        self.assertFalse(self.running.get(self.source_runtime, False))
        self.assertTrue(self.target_runtime.exists())
        before = (self.target_runtime/'data/database.sqlite3').read_bytes()
        result = self.apply(action='recover')
        self.assertEqual(result['status'], 'rolled_back')
        self.assertEqual(result['error_code'], 'interrupted')
        self.assertTrue(self.running[self.source_runtime])
        self.assertEqual((self.target_runtime/'data/database.sqlite3').read_bytes(), before)
        self.assertEqual(self.apply(action='recover'), result)

    def test_post_activation_recovery_never_automatically_rolls_back_possible_new_writes(self):
        self.fail_activation = True
        self.apply()
        before = len(self.calls)
        with self.assertRaisesRegex(ValueError, 'activation'):
            self.apply(action='recover')
        self.assertEqual(len(self.calls), before)
        self.assertTrue(self.target_runtime.exists())

    def test_second_successive_upgrade_uses_current_package_from_approved_package_root(self):
        self.assertEqual(self.apply()['status'], 'completed')
        self.source, self.target = self.target, 'f'*40
        self.source_package, self.source_runtime = self.target_package, self.target_runtime
        self.request_id = str(uuid.uuid4())
        self.target_runtime = self.path/'second-target'
        destination = self.packages/self.target
        destination.mkdir()
        self.target_package = self.bundle(destination/'package', self.target)
        self.catalog['releases'] = [{'release_id': self.target,
            'manifest_sha256': self.updater.customer._digest(self.target_package/'manifest.json')['sha256'],
            'supported_from': [self.source], 'editions': ['customer']}]
        self.catalog_write()
        self.payload.update(request_id=self.request_id, request_key=str(uuid.uuid4()),
            source_release=self.source, target_release=self.target,
            manifest_sha256=self.catalog['releases'][0]['manifest_sha256'],
            catalog_sha256=self.updater.customer._digest(self.updates/'catalog.json')['sha256'])
        result = self.apply()
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['release_id'], self.target)
        with closing(sqlite3.connect(self.target_runtime/'data/database.sqlite3')) as db:
            self.assertEqual(db.execute('select human_answer from retained').fetchone(), ('confirmed human answer',))

    def test_signature_is_identical_to_real_application_bridge(self):
        from core.update_service import sign_payload
        with override_settings(SECRET_KEY=self.secret):
            for purpose in ('request-v1', 'receipt-v1'):
                value = {'unicode': 'SYNTHETIC \u00e9', 'sequence': 2}
                self.assertEqual(self.updater.signature(self.secret, purpose, value), sign_payload(purpose, value))

    def test_another_request_cannot_bypass_an_unrecovered_host_transaction(self):
        self.interrupt_migration = True
        with self.assertRaises(KeyboardInterrupt): self.apply()
        self.interrupt_migration = False
        self.request_id = str(uuid.uuid4())
        self.payload['request_id'] = self.request_id
        self.target_runtime = self.path/'second-request-target'
        before = len(self.calls)
        with self.assertRaisesRegex(ValueError, 'recovery'):
            self.apply()
        self.assertEqual(len(self.calls), before)
        self.assertFalse(self.target_runtime.exists())

    def test_disposable_hard_interruption_failpoint_retains_journal_for_explicit_recovery(self):
        with patch.dict('os.environ', {'ISURVIX_DISPOSABLE_REHEARSAL': 'yes',
                'ISURVIX_UPDATER_TEST_FAILPOINT': 'interrupt-after-migrate'}):
            with self.assertRaises(KeyboardInterrupt): self.apply()
        self.assertTrue(self.target_runtime.exists())
        result = self.apply(action='recover')
        self.assertEqual(result['status'], 'rolled_back')
        self.assertEqual(result['error_code'], 'interrupted')

    def test_authority_is_rechecked_after_slow_image_load_before_writer_stop(self):
        self.revoke_after_image_load = True
        with self.assertRaises(ValueError): self.apply()
        self.assertFalse(any('stop' in call for call in self.calls))
        self.assertFalse(self.target_runtime.exists())
