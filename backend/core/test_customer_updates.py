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
        (self.source_runtime/'initialized.json').write_text(json.dumps({'release_id': self.source}))
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
        self.running = {self.source_runtime: True}
        self.fail_migration = False
        self.fail_activation = False
        self.withdrawn = False
        self.bad_health = False
        self.change_legacy_row = False
        self.interrupt_migration = False
        self.revoke_after_image_load = False
        self.images_loaded = False
        self.bad_proxy_target = False
        self.bad_proxy_source = False
        self.bad_tls_target = False
        self.listener_probes = []
        self.request_state_overrides = {}

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
        if '-c' in args and 'ISURVIX_REQUEST_STATE_V1' in args[args.index('-c')+1]:
            value = {key: self.payload[key] for key in self.updater.BINDINGS}
            value.update(status='failed' if self.withdrawn else 'pending',
                         error_code='cancelled' if self.withdrawn else '',
                         last_sequence=1 if self.withdrawn else 0)
            value.update(self.request_state_overrides)
            return json.dumps(value).encode()
        if 'receipt' in args:
            if self.withdrawn:
                raise ValueError('Controlled withdrawal: acknowledgement denied.')
            name = Path(args[args.index('--receipt-file')+1])
            receipt = json.loads((self.updates/'receipts'/name.parent.name/name.name).read_text())['payload']
            return json.dumps({'request_id': self.request_id, 'status': receipt['status'], 'sequence': receipt['sequence']}).encode()
        if 'stop' in args:
            self.running[runtime] = False
        if 'ps' in args:
            active = self.running.get(runtime, False)
            bad_proxy = self.bad_proxy_source if runtime == self.source_runtime else self.bad_proxy_target
            rows = [{'Service': 'web', 'State': 'running' if active else 'exited',
                     'Health': 'healthy' if active else ''},
                    {'Service': 'proxy', 'State': 'running' if active and not bad_proxy else 'exited',
                     'Health': 'healthy' if active and not bad_proxy else 'unhealthy'}]
            return json.dumps(rows).encode()
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

    def probe(self, state, release):
        self.listener_probes.append(release)
        if self.bad_tls_target and release == self.target:
            raise ValueError('Controlled TLS listener failure.')

    def apply(self, action='apply'):
        with patch.object(self.updater.customer, '_docker', side_effect=self.docker), patch.object(self.updater.time, 'sleep'), \
                patch.object(self.updater, '_probe_listener', side_effect=self.probe, create=True):
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

    def test_unhealthy_or_exited_proxy_never_reports_completed_after_activation(self):
        self.bad_proxy_target = True
        result = self.apply()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error_code'], 'activation_uncertain')
        self.assertFalse(self.running.get(self.source_runtime, False))
        self.assertTrue(self.target_runtime.exists())
        records = sorted((self.updates/'receipts'/self.request_id).glob('*.json'))
        self.assertNotIn('completed', [json.loads(path.read_text())['payload']['status'] for path in records])

    def test_healthy_proxy_without_verified_tls_readiness_is_activation_uncertain(self):
        self.bad_tls_target = True
        result = self.apply()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error_code'], 'activation_uncertain')
        self.assertIn(self.target, self.listener_probes)
        self.assertFalse(self.running.get(self.source_runtime, False))

    def test_rollback_cannot_claim_recovery_when_original_proxy_is_unhealthy(self):
        self.fail_migration = True
        self.bad_proxy_source = True
        result = self.apply()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error_code'], 'recovery_required')
        records = sorted((self.updates/'receipts'/self.request_id).glob('*.json'))
        self.assertNotIn('rolled_back', [json.loads(path.read_text())['payload']['status'] for path in records])

    def test_ack1_withdrawal_recovers_as_authoritative_cancelled_noop_then_allows_new_request(self):
        self.withdrawn = True
        with self.assertRaises(ValueError): self.apply()
        receipt = self.updates/'receipts'/self.request_id/'000001.json'
        original_receipt = receipt.read_bytes()
        original_database = (self.source_runtime/'data/database.sqlite3').read_bytes()
        before = len(self.calls)
        result = self.apply(action='recover')
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(result['error_code'], 'cancelled')
        self.assertEqual(result['release_id'], self.source)
        self.assertEqual(receipt.read_bytes(), original_receipt, 'Preserve the immutable conflict receipt for audit.')
        self.assertEqual((self.source_runtime/'data/database.sqlite3').read_bytes(), original_database)
        self.assertFalse(any('stop' in command or 'up' in command for command in self.calls[before:]))
        self.assertFalse(self.target_runtime.exists())
        replay_before = len(self.calls)
        self.assertEqual(self.apply(action='recover'), result)
        self.assertEqual(len(self.calls), replay_before)
        self.withdrawn = False
        self.request_id = str(uuid.uuid4())
        self.payload['request_id'] = self.request_id
        self.payload['request_key'] = str(uuid.uuid4())
        self.assertEqual(self.apply()['status'], 'completed')

    def test_pre_ack_recovery_rejects_unknown_or_mismatched_application_state(self):
        self.withdrawn = True
        with self.assertRaises(ValueError): self.apply()
        self.withdrawn = False  # A timeout is not evidence of cancellation.
        before = len(self.calls)
        with self.assertRaises(ValueError): self.apply(action='recover')
        self.assertFalse(any('stop' in command or 'up' in command for command in self.calls[before:]))
        state = json.loads((self.journals/self.request_id/'journal.json').read_text())
        self.assertEqual(state['phase'], 'verified-package')
        self.assertFalse(self.target_runtime.exists())
        self.withdrawn = True
        self.request_state_overrides = {'nonce': 'f'*32}
        with self.assertRaises(ValueError): self.apply(action='recover')
        self.assertFalse(any('stop' in command or 'up' in command for command in self.calls[before:]))

    def test_cancelled_noop_requires_healthy_current_source_without_starting_it(self):
        self.withdrawn = True
        with self.assertRaises(ValueError): self.apply()
        self.bad_proxy_source = True
        before = len(self.calls)
        with self.assertRaises(ValueError): self.apply(action='recover')
        self.assertFalse(any('stop' in command or 'up' in command for command in self.calls[before:]))
        state = json.loads((self.journals/self.request_id/'journal.json').read_text())
        self.assertEqual(state['phase'], 'verified-package')
        self.assertFalse((self.journals/self.request_id/'cancellation-proof.json').exists())

    def test_UP1_foreign_signed_terminal_journal_is_rejected_by_apply_and_recover(self):
        paths = self.updater._paths(installed_package=self.source_package, installed_runtime=self.source_runtime,
            update_directory=self.updates, packages_root=self.packages, target_runtime=self.target_runtime,
            journal_root=self.journals)
        foreign_id = str(uuid.uuid4())
        foreign = {**self.payload, 'request_id': foreign_id}
        transaction = self.journals/self.request_id
        transaction.mkdir()
        journal = {'format': 'isurvix-host-update-journal-v1', 'phase': 'completed',
            'paths': {key: str(value) for key, value in paths.items()}, 'request': self.signed(foreign),
            'sequence': 3, 'last_status': 'completed',
            'result': {'request_id': foreign_id, 'status': 'completed', 'release_id': self.target}}
        path = transaction/'journal.json'
        path.write_text(json.dumps(journal))
        original = path.read_bytes()
        for action in ('apply', 'recover'):
            with self.subTest(action=action), self.assertRaises(ValueError): self.apply(action)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.target_runtime.exists())
        self.assertEqual(path.read_bytes(), original)

    def test_UP1_terminal_result_tampering_or_missing_retained_target_is_rejected_without_docker(self):
        self.apply()
        path = self.journals/self.request_id/'journal.json'
        original = path.read_bytes()
        journal = json.loads(original)
        before = len(self.calls)
        for key, value in (('request_id', str(uuid.uuid4())), ('status', 'rolled_back'),
                           ('release_id', self.source), ('owner_release_approved', True)):
            altered = {**journal, 'result': {**journal['result'], key: value}}
            path.write_text(json.dumps(altered))
            for action in ('apply', 'recover'):
                with self.subTest(key=key, action=action), self.assertRaises(ValueError): self.apply(action)
        path.write_bytes(original)
        absent = self.path/'preserved-target-moved'
        self.target_runtime.rename(absent)
        for action in ('apply', 'recover'):
            with self.subTest(missing_target=action), self.assertRaises(ValueError): self.apply(action)
        self.assertEqual(len(self.calls), before)
        self.assertEqual(path.read_bytes(), original)
        self.assertTrue(absent.is_dir())

    def test_UP1_backup_and_retention_proof_corruption_cannot_report_historical_success(self):
        self.apply()
        transaction = self.journals/self.request_id
        before = len(self.calls)
        for name in ('backup/media/original.bin', 'retention-proof.json', 'retained-records.json'):
            path = transaction/name
            original = path.read_bytes()
            path.write_bytes(b'Corrupt immutable synthetic historical proof')
            for action in ('apply', 'recover'):
                with self.subTest(name=name, action=action), self.assertRaises(ValueError): self.apply(action)
            self.assertEqual(path.read_bytes(), b'Corrupt immutable synthetic historical proof')
            path.write_bytes(original)
        self.assertEqual(len(self.calls), before)

    def test_UP1_historical_replay_preserves_later_human_writes_without_uptime_or_fresh_token(self):
        result = self.apply()
        with closing(sqlite3.connect(self.target_runtime/'data/database.sqlite3')) as db:
            db.execute("update retained set human_answer='later legitimate human correction'")
            db.commit()
        (self.target_runtime/'data/media/later-upload.bin').write_bytes(b'Later legitimate original')
        database_before = (self.target_runtime/'data/database.sqlite3').read_bytes()
        self.running = {}  # A historical release may intentionally be stopped.
        before = len(self.calls)
        with patch.object(self.updater.time, 'time', return_value=int(time.time())+86400):
            self.assertEqual(self.apply(), result)
            self.assertEqual(self.apply('recover'), result)
        self.assertEqual(len(self.calls), before)
        self.assertEqual((self.target_runtime/'data/database.sqlite3').read_bytes(), database_before)
        self.assertEqual((self.target_runtime/'data/media/later-upload.bin').read_bytes(), b'Later legitimate original')
