"""Telemetry opt-out is applied before native OCR/embedding imports."""
import os
import importlib.util
from pathlib import Path
import subprocess
import socket
import sys

from django.test import SimpleTestCase


class NativeRuntimePrivacyTests(SimpleTestCase):
    @staticmethod
    def runner():
        path = Path(__file__).resolve().parents[2] / 'scripts' / 'run_backend_tests.py'
        spec = importlib.util.spec_from_file_location('isolated_backend_runner', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_fresh_core_import_sets_process_optout_without_loading_native_model(self):
        backend = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, '-c',
             "import os, sys; os.environ['ORT_DISABLE_TELEMETRY']='0'; "
             "import core; assert os.environ['ORT_DISABLE_TELEMETRY']=='1'; "
             "assert 'onnxruntime' not in sys.modules; print('privacy opt-out active')"],
            cwd=backend, env={**os.environ, 'PYTHONPATH': str(backend)},
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('privacy opt-out active', result.stdout)

    def test_startup_guard_rejects_external_and_unowned_loopback_connections(self):
        attempts, fixtures = [], []
        with self.runner().network_isolation(attempts, fixtures):
            for address in [('203.0.113.20', 443), ('127.0.0.1', 11434)]:
                with self.subTest(address=address), socket.socket() as client:
                    with self.assertRaisesMessage(OSError, 'Ordinary tests cannot connect'):
                        client.connect(address)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(fixtures, [])

    def test_startup_guard_allows_only_its_own_in_process_http_listener(self):
        attempts, fixtures = [], []
        with self.runner().network_isolation(attempts, fixtures):
            with socket.socket() as server:
                server.bind(('127.0.0.1', 0))
                server.listen(1)
                with socket.socket() as client:
                    client.settimeout(2)
                    client.connect(server.getsockname())
                    peer, _ = server.accept()
                    peer.close()
        self.assertEqual(attempts, [])
        self.assertEqual(len(fixtures), 1)
