"""Optional mail process stays inside the existing, quiesced web writer boundary."""
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
import time
import unittest
from unittest.mock import patch

from django.test import SimpleTestCase

from . import test_hostinger_delivery as existing_delivery_tests

ROOT = Path(__file__).resolve().parents[2]
MAIL_TARGET = '/run/private/ifield-notification.json'
MAIL_SOURCE = '/etc/isurvix-staging/ifield-notification.json'


def runtime_module():
    spec = importlib.util.spec_from_file_location('ifield_web_runtime', ROOT/'deploy/web_runtime.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class NotificationRuntimePolicyTests(SimpleTestCase):
    def setUp(self):
        self.controller = existing_delivery_tests.module()
        self.config = existing_delivery_tests.RuntimePolicyTests().config()

    def enabled(self):
        self.config['services']['web']['environment'] = {
            'ISURVIX_NOTIFICATION_EMAIL_ENABLED': 'True',
            'ISURVIX_NOTIFICATION_CREDENTIALS_FILE': MAIL_TARGET,
            'ISURVIX_NOTIFICATION_PUBLIC_ORIGIN': 'https://app.isurvix.com',
        }
        self.config['services']['web']['volumes'].append({
            'type': 'bind', 'source': MAIL_SOURCE, 'target': MAIL_TARGET, 'read_only': True})
        return self.config

    def test_existing_disabled_runtime_does_not_need_mail_secret(self):
        self.controller.validate_compose(self.config)

    def test_exact_enabled_private_mail_mount_can_join_existing_two_services(self):
        config = self.enabled()
        self.controller.validate_compose(config)
        self.assertEqual(set(config['services']), {'web', 'proxy'})

    def test_enabled_sender_requires_its_approved_secret_mount(self):
        config = self.enabled()
        config['services']['web']['volumes'].pop()
        with self.assertRaises(ValueError):
            self.controller.validate_compose(config)

    def test_optional_secret_cannot_be_exposed_without_enabling_mail(self):
        config = self.enabled()
        config['services']['web']['environment']['ISURVIX_NOTIFICATION_EMAIL_ENABLED'] = 'False'
        with self.assertRaises(ValueError):
            self.controller.validate_compose(config)

    def test_wrong_source_target_writability_or_secret_setting_is_rejected(self):
        for mutate in [
            lambda c: c['services']['web']['volumes'][-1].update(source='/etc/shadow'),
            lambda c: c['services']['web']['volumes'][-1].update(target='/run/private/another.json'),
            lambda c: c['services']['web']['volumes'][-1].update(read_only=False),
            lambda c: c['services']['web']['environment'].update(ISURVIX_NOTIFICATION_CREDENTIALS_FILE='/data/media/mail.json'),
        ]:
            self.config = existing_delivery_tests.RuntimePolicyTests().config()
            config = self.enabled()
            mutate(config)
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    self.controller.validate_compose(config)

    def test_mail_does_not_admit_a_third_writer_or_proxy_secret_mount(self):
        config = self.enabled()
        config['services']['worker'] = copy.deepcopy(config['services']['web'])
        with self.assertRaises(ValueError):
            self.controller.validate_compose(config)
        config.pop('unused', None)
        del config['services']['worker']
        config['services']['proxy']['volumes'].append(config['services']['web']['volumes'][-1])
        with self.assertRaises(ValueError):
            self.controller.validate_compose(config)

    def test_optional_override_wires_existing_web_without_public_ports(self):
        override = json.loads((ROOT/'deploy/notification-email.override.yaml').read_text())
        self.assertEqual(set(override['services']), {'web'})
        web = override['services']['web']
        self.assertNotIn('ports', web)
        self.assertEqual(web['environment']['ISURVIX_NOTIFICATION_CREDENTIALS_FILE'], MAIL_TARGET)
        self.assertEqual(web['volumes'][0]['source'], MAIL_SOURCE)
        self.assertEqual(web['volumes'][0]['target'], MAIL_TARGET)
        self.assertIs(web['volumes'][0]['read_only'], True)
        self.assertIn('notification-egress', web['networks'])
        self.assertFalse(override['networks']['notification-egress']['internal'])


class NotificationRuntimeProcessTests(SimpleTestCase):
    def setUp(self):
        self.runtime = runtime_module()
        fixture_root = ROOT/'.local/test-fixtures'
        fixture_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='mail-runtime-', dir=fixture_root)
        self.root = Path(self.temporary.name)
        self.children = []

    def tearDown(self):
        for process in self.children:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
        self.temporary.cleanup()

    def spawn(self, *args, **kwargs):
        process = subprocess.Popen(*args, **kwargs)
        self.children.append(process)
        return process

    def command(self, code):
        return [sys.executable, '-c', code]

    def run_runtime(self, web, mail=None, **kwargs):
        return self.runtime.supervise(web, mail, poll_interval=0.02,
            retry_interval=0.12, shutdown_timeout=0.5, spawn=self.spawn, **kwargs)

    def test_disabled_mail_never_starts_a_worker_and_keeps_web_exit_code(self):
        result = self.run_runtime(self.command('raise SystemExit(7)'),
            self.command('raise SystemExit(99)'), mail_enabled=False, readiness=lambda: True)
        self.assertEqual(result, 7)
        self.assertEqual(len(self.children), 1)

    def test_private_candidate_cannot_start_mail_before_public_release_matches(self):
        marker = self.root/'mail-started'
        code = 'from pathlib import Path; Path('+repr(str(marker))+').write_text("started")'
        self.run_runtime(self.command('import time; time.sleep(.3)'), self.command(code),
                         mail_enabled=True, readiness=lambda: False)
        self.assertFalse(marker.exists())
        self.assertEqual(len(self.children), 1)

    def test_real_mail_child_is_stopped_when_the_web_process_exits(self):
        marker = self.root/'mail-started'
        code = ('from pathlib import Path; import time; Path('+repr(str(marker))+')'
                '.write_text("started"); time.sleep(60)')
        self.run_runtime(self.command('import time; time.sleep(.6)'), self.command(code),
                         mail_enabled=True, readiness=lambda: True)
        self.assertTrue(marker.exists())
        self.assertEqual(len(self.children), 2)
        self.assertTrue(all(child.poll() is not None for child in self.children))

    def test_missing_worker_configuration_does_not_stop_web_or_busy_restart(self):
        start = time.monotonic()
        self.run_runtime(self.command('import time; time.sleep(.55)'),
            self.command('raise SystemExit(2)'), mail_enabled=True, readiness=lambda: True)
        self.assertGreater(time.monotonic()-start, .4)
        self.assertGreaterEqual(len(self.children), 2)
        self.assertLessEqual(len(self.children), 7)

    def test_supervisor_stop_terminates_both_real_children(self):
        stop = threading.Event()
        timer = threading.Timer(.3, stop.set)
        timer.start()
        try:
            self.run_runtime(self.command('import time; time.sleep(60)'),
                self.command('import time; time.sleep(60)'), mail_enabled=True,
                readiness=lambda: True, stop_event=stop)
        finally:
            timer.cancel()
        self.assertEqual(len(self.children), 2)
        self.assertTrue(all(child.poll() is not None for child in self.children))

    @unittest.skipUnless(os.name == 'posix', 'Real POSIX process-group signal semantics run on Linux.')
    def test_sigterm_reaches_children_and_supervisor_exits_without_orphan_writer(self):
        marker = self.root/'child-stopped'
        ready = self.root/'child-handler-ready'
        fixture = self.root/'child.py'
        fixture.write_text('import signal,time,sys\nfrom pathlib import Path\n'
            'def stop(*a):\n Path('+repr(str(marker))+').write_text("stopped")\n sys.exit(0)\n'
            'signal.signal(signal.SIGTERM, stop)\nPath('+repr(str(ready))+').write_text("ready")\n'
            'while True: time.sleep(.05)\n')
        launcher = ('import sys;sys.path.insert(0,'+repr(str(ROOT/'deploy'))+');'
            'from web_runtime import supervise;raise SystemExit(supervise('
            +repr([sys.executable, str(fixture)])+',mail_enabled=False,poll_interval=.02,shutdown_timeout=1))')
        supervisor = subprocess.Popen(self.command(launcher))
        self.children.append(supervisor)
        deadline = time.monotonic() + 5
        while not ready.exists() and supervisor.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertIsNone(supervisor.poll(), 'Supervisor exited before the child became ready.')
        self.assertTrue(ready.exists(), 'Child must install its signal handler before testing signal forwarding.')
        supervisor.terminate()
        supervisor.wait(timeout=4)
        self.assertTrue(marker.exists())

    def test_docker_starts_the_supervisor_and_preserves_fixed_gunicorn_flags(self):
        lines = (ROOT/'deploy/Dockerfile').read_text().splitlines()
        command = json.loads(next(line[4:] for line in lines if line.startswith('CMD ')))
        self.assertEqual(command, ['python', '/app/deploy/web_runtime.py'])
        self.assertIn('gunicorn', self.runtime.WEB_COMMAND)
        self.assertIn('checklist.wsgi:application', self.runtime.WEB_COMMAND)
        self.assertEqual(self.runtime.MAIL_COMMAND[-1], 'run_invitation_email_worker')


class NotificationPublicReleaseGateTests(SimpleTestCase):
    def setUp(self):
        self.runtime = runtime_module()
        self.env = {'ISURVIX_NOTIFICATION_PUBLIC_ORIGIN': 'https://app.isurvix.com',
                    'ISURVIX_RELEASE_ID': 'a'*40, 'DJANGO_ALLOWED_HOSTS': 'app.isurvix.com'}

    def check(self, body=None, status=200):
        from types import SimpleNamespace
        with patch.object(self.runtime, 'deadline_request') as request:
            request.return_value = SimpleNamespace(status_code=status, body=json.dumps(body).encode())
            answer = self.runtime.public_release_ready(self.env)
            call = request.call_args
            self.assertEqual(call.kwargs['total_timeout'], 5)
            self.assertEqual(call.kwargs['max_bytes'], 4096)
            self.assertEqual(call.args, ('GET', 'https://app.isurvix.com/ops/health/ready/'))
        return answer

    def test_public_readiness_must_identify_our_own_immutable_release(self):
        self.assertTrue(self.check({'status': 'ready', 'release': 'a'*40}))
        self.assertFalse(self.check({'status': 'ready', 'release': 'b'*40}))
        self.assertFalse(self.check({'status': 'starting', 'release': 'a'*40}))

    def test_redirect_unknown_or_oversized_responses_do_not_open_mail_gate(self):
        self.assertFalse(self.check({'status': 'ready', 'release': 'a'*40}, status=302))
        self.assertFalse(self.check(['ready', 'a'*40]))
        with patch.object(self.runtime, 'deadline_request', side_effect=self.runtime.RequestError()):
            self.assertFalse(self.runtime.public_release_ready(self.env))

    def test_unsafe_origins_and_missing_release_never_make_a_request(self):
        for origin in ('http://app.isurvix.com', 'https://foreign.example.test',
                       'https://secret@app.isurvix.com', 'https://app.isurvix.com/path',
                       'https://app.isurvix.com?token=private'):
            self.env['ISURVIX_NOTIFICATION_PUBLIC_ORIGIN'] = origin
            with self.subTest(origin=origin), patch.object(self.runtime, 'deadline_request') as request:
                self.assertFalse(self.runtime.public_release_ready(self.env))
                request.assert_not_called()
        self.env['ISURVIX_NOTIFICATION_PUBLIC_ORIGIN'] = 'https://app.isurvix.com'
        self.env.pop('ISURVIX_RELEASE_ID')
        with patch.object(self.runtime, 'deadline_request') as request:
            self.assertFalse(self.runtime.public_release_ready(self.env))
            request.assert_not_called()


class NotificationReadinessDeadlineTests(SimpleTestCase):
    def test_real_slow_headers_and_body_cannot_outlive_readiness_total_budget(self):
        runtime = runtime_module()
        body = json.dumps({'status': 'ready', 'release': 'a'*40}).encode()
        records = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                records.append(self.path)
                try:
                    if self.path == '/headers':
                        raw = b'HTTP/1.1 200 OK\r\nX-Padding: '+b'x'*100+b'\r\nContent-Length: 0\r\n\r\n'
                        for byte in raw:
                            self.wfile.write(bytes([byte])); self.wfile.flush(); time.sleep(.01)
                    else:
                        self.send_response(200)
                        self.send_header('Content-Length', str(len(body)))
                        self.end_headers()
                        for byte in body:
                            self.wfile.write(bytes([byte])); self.wfile.flush(); time.sleep(.01)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            original = runtime.deadline_request
            env = {'ISURVIX_NOTIFICATION_PUBLIC_ORIGIN': 'https://app.isurvix.com',
                   'ISURVIX_RELEASE_ID': 'a'*40, 'DJANGO_ALLOWED_HOSTS': 'app.isurvix.com'}
            for path in ('/headers', '/body'):
                def fixture_request(method, url, **kwargs):
                    self.assertEqual(url, 'https://app.isurvix.com/ops/health/ready/')
                    return original(method, 'http://127.0.0.1:'+str(server.server_port)+path, **kwargs)
                with self.subTest(path=path), patch.object(runtime, 'deadline_request', fixture_request), \
                        patch.object(runtime, '_READINESS_TOTAL_TIMEOUT', .2):
                    started = time.monotonic()
                    self.assertFalse(runtime.public_release_ready(env))
                    self.assertLess(time.monotonic()-started, .8)
        finally:
            server.shutdown(); server.server_close(); thread.join(2)
        self.assertEqual(records, ['/headers', '/body'])
