"""Startup metadata and private diagnostic tools use synthetic loopback HTTP."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from unittest import skipUnless
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]
MODEL = 'qwen3.5:4b'
POWERSHELL = (os.environ.get('ISURVIX_TEST_POWERSHELL') or
    shutil.which('powershell.exe') or shutil.which('pwsh'))


class WorkerRuntimeToolTests(SimpleTestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('isolated_worker_runtime_tools',
            ROOT / 'scripts' / 'worker_runtime_tools.py')
        self.tools = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tools)
        self.temporary = tempfile.TemporaryDirectory(prefix='isurvix-runtime-tool-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.config = self.directory / 'remote-worker.json'
        self.secret = 'PRIVATE-SYNTHETIC-WORKER-TOKEN-DO-NOT-LOG'
        self.config.write_text(json.dumps({'server_url': 'https://example.invalid',
            'token': self.secret}))
        self.calls = []
        self.mode = 'healthy'
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self, value):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(value).encode())

            def do_GET(self):
                outer.calls.append(('GET', self.path, None))
                if outer.mode == 'redirect':
                    self.send_response(302)
                    self.send_header('Location', 'https://example.invalid/never-request-this')
                    self.end_headers()
                    return
                name = 'other-model' if outer.mode == 'missing-model' else MODEL
                row = {'name': name}
                if outer.mode == 'remote':
                    row['remote_host'] = 'https://example.invalid'
                self.respond({'models': [row]})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                outer.calls.append(('POST', self.path, body))
                self.respond({'capabilities': ['completion'] if outer.mode == 'no-vision'
                    else ['vision', 'completion']})

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def startup(self, **changes):
        return self.tools.validate_startup(model=MODEL, photo_url=self.url,
            text_url=changes.get('text_url', self.url), config_path=self.config)

    def test_readiness_uses_installed_local_metadata_without_inference_or_secrets(self):
        result = self.startup()
        self.assertEqual(self.calls, [('GET', '/api/tags', None),
            ('POST', '/api/show', {'model': MODEL})])
        self.assertTrue(result['photo']['vision'])
        self.assertNotIn(self.secret, json.dumps(result))

    def test_non_loopback_credentials_paths_and_ambiguous_urls_are_rejected(self):
        for url in ['http://192.168.1.2:11434', 'https://127.0.0.1:11434',
                'http://user:password@127.0.0.1:11434', self.url + '/other',
                self.url + '?token=private', self.url + '#fragment', self.url + '\n']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.tools.loopback_origin(url)
        self.assertEqual(self.calls, [])

    def test_missing_installed_model_is_not_downloaded(self):
        self.mode = 'missing-model'
        with self.assertRaises(ValueError):
            self.startup()
        self.assertEqual(self.calls, [('GET', '/api/tags', None)])

    def test_remote_alias_and_nonvision_metadata_are_rejected(self):
        for mode in ['remote', 'no-vision']:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.mode = mode
                self.startup()
        self.assertFalse(any(path in {'/api/chat', '/api/generate', '/api/pull'}
            for _, path, _ in self.calls))

    def test_metadata_redirect_is_not_followed(self):
        self.mode = 'redirect'
        with self.assertRaises(Exception):
            self.startup()
        self.assertEqual(self.calls, [('GET', '/api/tags', None)])

    def test_invalid_private_configuration_is_rejected_without_probing_a_service(self):
        self.config.write_text(json.dumps({'server_url': 'http://example.invalid', 'token': self.secret}))
        with self.assertRaises(ValueError):
            self.startup()
        self.assertEqual(self.calls, [])

    def test_diagnostics_keep_only_bounded_symbolic_crash_hints_in_a_private_file(self):
        local = self.directory / '.local'
        local.mkdir()
        (local / 'worker-synthetic.stderr.log').write_text(
            f'Authorization: Bearer {self.secret}\nPRIVATE-SITE-NAME-DO-NOT-LOG\n'
            'Fatal Python error: Segmentation fault\nonnxruntime native exit 139\n')
        (local / 'django-secret').write_text(self.secret)
        result = self.tools.collect_diagnostics(project_root=self.directory, model=MODEL,
            photo_url=self.url, text_url=self.url, powershell_version='7.6.9')
        path = Path(result)
        self.assertEqual(path.parent, local / 'diagnostics')
        raw = path.read_text()
        self.assertNotIn(self.secret, raw)
        self.assertNotIn('PRIVATE-SITE-NAME', raw)
        self.assertIn('segmentation_fault', raw)
        self.assertIn('onnxruntime', raw)
        data = json.loads(raw)
        self.assertFalse(data['native_inference_performed'])
        self.assertFalse(data['uploaded'])
        if os.name != 'nt':
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

    def test_invalid_diagnostic_endpoint_does_not_write_a_report(self):
        with self.assertRaises(ValueError):
            self.tools.collect_diagnostics(project_root=self.directory, model=MODEL,
                photo_url='http://example.invalid', text_url=self.url)
        self.assertFalse((self.directory / '.local' / 'diagnostics').exists())

    @skipUnless(POWERSHELL, 'PowerShell wrapper integration requires powershell.exe or pwsh.')
    def test_remote_worker_check_only_runs_real_metadata_checks_without_claiming_jobs(self):
        result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive',
            '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'scripts' / 'Start-RemoteSurveyWorker.ps1'),
            '-PhotoOllamaUrl', self.url, '-TextOllamaUrl', self.url, '-Model', MODEL,
            '-PythonPath', sys.executable, '-ConfigPath', str(self.config), '-CheckOnly'],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn(self.secret, result.stdout + result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertFalse(payload['jobs_claimed'])
        self.assertFalse(payload['native_inference_performed'])
        self.assertEqual(self.calls, [('GET', '/api/tags', None),
            ('POST', '/api/show', {'model': MODEL})])

    @skipUnless(POWERSHELL, 'PowerShell wrapper integration requires powershell.exe or pwsh.')
    def test_diagnostics_wrapper_writes_only_to_its_isolated_project(self):
        scripts = self.directory / 'scripts'
        scripts.mkdir()
        for name in ['worker_runtime_tools.py', 'Collect-iSurvixDiagnostics.ps1']:
            shutil.copyfile(ROOT / 'scripts' / name, scripts / name)
        result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive',
            '-ExecutionPolicy', 'Bypass', '-File', str(scripts / 'Collect-iSurvixDiagnostics.ps1'),
            '-PhotoOllamaUrl', self.url, '-TextOllamaUrl', self.url, '-Model', MODEL,
            '-PythonPath', sys.executable], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        path = Path(result.stdout.strip().splitlines()[-1])
        self.assertEqual(path.parent, self.directory / '.local' / 'diagnostics')
        data = json.loads(path.read_text())
        self.assertFalse(data['credentials_collected'])
        self.assertIn('Open:', data['a12_status'])
        self.assertNotIn(self.secret, path.read_text())
