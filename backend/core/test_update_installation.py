"""Optional Update Center mounts persist through the existing installer helper."""
import hashlib
import json
from pathlib import Path

from django.test import SimpleTestCase
from . import test_customer_package as fixtures

ROOT = fixtures.ROOT


class UpdateInstallationTests(SimpleTestCase):
    setUp = fixtures.CustomerPackageTests.setUp
    bundle = fixtures.CustomerPackageTests.bundle
    private_inputs = fixtures.CustomerPackageTests.private_inputs

    def prepared(self, *, updates=True, valid=True):
        package = self.bundle()
        target = package / 'release/deploy/customer/compose.updates.yaml'
        target.write_bytes((ROOT / 'deploy/customer/compose.updates.yaml').read_bytes())
        manifest = json.loads((package / 'manifest.json').read_text())
        manifest['files'][target.relative_to(package).as_posix()] = {'size': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
        (package / 'manifest.json').write_text(json.dumps(manifest))
        secret, tls = self.private_inputs()
        update_root = self.path / 'operator-updates'
        update_root.mkdir()
        if valid:
            (update_root / 'catalog.json').write_text('{"format":"isurvix-update-catalog-v1","releases":[]}')
            (update_root / 'receipts').mkdir()
        result = self.customer.prepare_runtime(package, self.path / 'runtime', host='customer.example.test',
            lan_ip='192.168.10.5', secret_file=secret, tls_directory=tls, acknowledge_draft=True,
            update_directory=update_root if updates else None)
        return package, update_root, result

    def test_configured_catalog_and_receipts_are_readonly_and_retained_in_compose_actions(self):
        package, update_root, _ = self.prepared()
        runtime = self.path / 'runtime'
        _, state = self.customer._runtime(package, runtime)
        self.assertEqual(state['values']['ISURVIX_UPDATE_DIRECTORY'], update_root.as_posix())
        command = self.customer._compose_base(package, runtime, state)
        self.assertIn(str(package / 'release/deploy/customer/compose.updates.yaml'), command)
        override = (ROOT / 'deploy/customer/compose.updates.yaml').read_text()
        self.assertIn('/catalog.json:/run/isurvix-updates/catalog.json:ro', override)
        self.assertIn('/receipts:/run/isurvix-updates/receipts:ro', override)
        mounts = [line.strip()[2:] for line in override.splitlines() if line.strip().startswith('- ')]
        self.assertEqual(len(mounts), 2)
        self.assertTrue(all(mount.endswith(':ro') for mount in mounts))
        self.assertFalse(any('docker.sock' in mount or 'journal' in mount for mount in mounts))
        before = (update_root / 'catalog.json').read_bytes()
        self.customer._runtime(package, runtime)
        self.assertEqual((update_root / 'catalog.json').read_bytes(), before)

    def test_unconfigured_installation_keeps_existing_compose_and_records(self):
        package, _, _ = self.prepared(updates=False)
        _, state = self.customer._runtime(package, self.path / 'runtime')
        self.assertNotIn('ISURVIX_UPDATE_DIRECTORY', state['values'])
        self.assertNotIn(str(package / 'release/deploy/customer/compose.updates.yaml'), self.customer._compose_base(package, self.path / 'runtime', state))

    def test_missing_operator_inputs_fail_before_creating_a_runtime(self):
        with self.assertRaises(ValueError):
            self.prepared(valid=False)
        self.assertFalse((self.path / 'runtime').exists())
