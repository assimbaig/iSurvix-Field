"""Worker compatibility covers numerical semantics in the shared helper."""
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from . import measurement_units, remote_worker_service as bridge


class MeasurementUnitWorkerPinTests(SimpleTestCase):
    def helper_source(self, transform):
        original = Path.read_bytes
        helper = Path(measurement_units.__file__).resolve()

        def read_bytes(path):
            source = original(path)
            return transform(source) if path.resolve() == helper else source

        return patch.object(Path, 'read_bytes', read_bytes)

    def changed_voltage_factor(self, source):
        self.assertIn(b"'mV': ('voltage', Decimal('.001'))", source)
        return source.replace(b"'mV': ('voltage', Decimal('.001'))",
                              b"'mV': ('voltage', Decimal('.002'))", 1)

    def test_helper_only_semantic_change_alters_implementation_fingerprint(self):
        reviewed = bridge.versions()
        with self.helper_source(self.changed_voltage_factor):
            changed = bridge.versions()
        self.assertNotEqual(changed['implementation'], reviewed['implementation'])
        for key in ('protocol', 'pipeline', 'evidence', 'mapping'):
            self.assertEqual(changed[key], reviewed[key])

    def test_helper_only_semantic_change_rejects_previous_worker_identity(self):
        reviewed = bridge.versions()
        with self.helper_source(self.changed_voltage_factor), self.assertRaises(ValidationError):
            bridge._compatible({'versions': reviewed})

    def test_helper_only_lf_crlf_difference_retains_compatibility(self):
        reviewed = bridge.versions()
        with self.helper_source(lambda source: source.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')):
            self.assertEqual(bridge.versions(), reviewed)
            bridge._compatible({'versions': reviewed})

    def test_all_shared_sources_lf_crlf_difference_retains_compatibility(self):
        reviewed = bridge.versions()
        original = Path.read_bytes
        with patch.object(Path, 'read_bytes', lambda path: original(path).replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')):
            self.assertEqual(bridge.versions(), reviewed)
            bridge._compatible({'versions': reviewed})

    def test_current_worker_implementation_remains_compatible(self):
        bridge._compatible({'versions': bridge.versions()})
