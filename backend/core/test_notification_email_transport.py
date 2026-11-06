"""Private Graph configuration and real HTTP fixture delivery, never live mail."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from unittest.mock import patch
from urllib.parse import parse_qs

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from .http_deadline import Response, RequestError, DeadlineExceeded


TENANT = '11111111-2222-4333-8444-555555555555'
CLIENT = '66666666-7777-4888-8999-aaaaaaaaaaaa'
SECRET = 'SYNTHETIC-CLIENT-SECRET'
TOKEN = 'synthetic-access-token'


def response(status=200, payload=None, raw=None):
    return Response(status, raw if raw is not None else json.dumps(payload or {}).encode())


@contextmanager
def graph_fixture(*, token_status=200, send_status=202, token_raw=None):
    records = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            raw = self.rfile.read(int(self.headers['Content-Length']))
            records.append({'path': self.path, 'raw': raw, 'authorization': self.headers.get('Authorization')})
            token_request = self.path.startswith('/token/')
            status = token_status if token_request else send_status
            body = (token_raw if token_raw is not None else json.dumps({
                'access_token': TOKEN, 'token_type': 'Bearer', 'expires_in': 3600,
            }).encode()) if token_request else b''
            self.send_response(status)
            if status in (301, 302, 307, 308):
                self.send_header('Location', '/redirect-must-not-be-followed')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        from . import notification_email as mail
        origin = f'http://127.0.0.1:{server.server_port}'
        with patch.object(mail, 'TOKEN_URL_TEMPLATE', origin + '/token/{tenant_id}'), patch.object(mail, 'SEND_MAIL_URL', origin + '/send'):
            yield records
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class GraphConfigurationTests(SimpleTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=settings.FILE_UPLOAD_TEMP_DIR)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / 'private' / 'graph.json'
        self.path.parent.mkdir()
        self.write_config()
        self.override = override_settings(NOTIFICATION_EMAIL_CREDENTIALS_FILE=str(self.path),
            MEDIA_ROOT=self.root / 'media', STATIC_ROOT=self.root / 'static')
        self.override.enable()
        self.addCleanup(self.override.disable)

    def write_config(self, **changes):
        value = {'tenant_id': TENANT, 'client_id': CLIENT, 'client_secret': SECRET}
        value.update(changes)
        self.path.write_text(json.dumps(value), encoding='utf-8')
        self.path.chmod(0o600)

    def test_private_file_loads_identity_without_disclosing_secret_in_repr(self):
        from .notification_email import load_config
        config = load_config()
        self.assertEqual(config.tenant_id, TENANT)
        self.assertEqual(config.client_id, CLIENT)
        self.assertEqual(config.client_secret, SECRET)
        self.assertNotIn(SECRET, repr(config))

    def assert_bad_config(self, code='configuration_invalid'):
        from .notification_email import NotificationEmailError, load_config
        with self.assertRaises(NotificationEmailError) as caught:
            load_config()
        self.assertEqual(caught.exception.code, code)
        self.assertFalse(caught.exception.retryable or caught.exception.uncertain)
        self.assertNotIn(SECRET, str(caught.exception))
        self.assertNotIn(str(self.path), str(caught.exception))

    def test_missing_credentials_are_an_honest_configuration_error(self):
        with override_settings(NOTIFICATION_EMAIL_CREDENTIALS_FILE=''):
            self.assert_bad_config('configuration_missing')

    def test_relative_path_is_rejected(self):
        with override_settings(NOTIFICATION_EMAIL_CREDENTIALS_FILE='graph.json'):
            self.assert_bad_config()

    def test_missing_file_is_not_a_successful_connection(self):
        self.path.unlink()
        self.assert_bad_config()

    def test_uploaded_or_static_credentials_are_rejected(self):
        for root_name in ('MEDIA_ROOT', 'STATIC_ROOT'):
            with self.subTest(root_name=root_name), override_settings(**{root_name: self.path.parent}):
                self.assert_bad_config()

    def test_malformed_and_oversized_files_are_rejected(self):
        for raw in ('{broken-' + SECRET, '[' + ' ' * 20000 + ']'):
            with self.subTest(length=len(raw)):
                self.path.write_text(raw, encoding='utf-8')
                self.assert_bad_config()

    def test_tenant_client_and_secret_have_valid_types_and_values(self):
        for change in ({'tenant_id': 'https://attacker.example'}, {'client_id': '../escape'},
                       {'client_secret': ''}, {'client_secret': 44}, {'client_secret': 'secret\r\nvalue'}):
            with self.subTest(fields=list(change)):
                self.write_config(**change)
                self.assert_bad_config()

    def test_unknown_configuration_keys_are_not_accepted(self):
        self.write_config(token_endpoint='https://attacker.example')
        self.assert_bad_config()

    def test_directory_is_not_a_credential_file(self):
        with override_settings(NOTIFICATION_EMAIL_CREDENTIALS_FILE=str(self.path.parent)):
            self.assert_bad_config()

    def test_public_posix_permissions_are_rejected(self):
        if os.name == 'nt':
            self.skipTest('POSIX mode bits do not implement Windows file ACLs.')
        self.path.chmod(0o644)
        self.assert_bad_config()

    def test_symlinked_file_is_rejected_when_supported(self):
        link = self.path.with_name('link.json')
        try:
            link.symlink_to(self.path)
        except OSError as error:
            if os.name == 'nt' and getattr(error, 'winerror', None) == 1314:
                self.skipTest('Creating native Windows symlinks requires a privilege unavailable here.')
            raise
        with override_settings(NOTIFICATION_EMAIL_CREDENTIALS_FILE=str(link)):
            self.assert_bad_config()


class GraphTransportTests(SimpleTestCase):
    def config(self):
        return {'tenant_id': TENANT, 'client_id': CLIENT, 'client_secret': SECRET}

    def send(self):
        from .notification_email import GraphMailClient
        return GraphMailClient(self.config()).send('recipient@example.test', 'Your iField invitation', 'Synthetic invitation body')

    def transport(self, *responses):
        context = patch('core.notification_email.bounded_request')
        transport = context.start()
        self.addCleanup(context.stop)
        transport.side_effect = responses
        return transport

    def token_response(self, **changes):
        payload = {'access_token': TOKEN, 'token_type': 'Bearer', 'expires_in': 3600}
        payload.update(changes)
        return response(payload=payload)

    def failure(self, code, *, retryable=False, uncertain=False):
        from .notification_email import NotificationEmailError
        with self.assertRaises(NotificationEmailError) as caught:
            self.send()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.retryable, retryable)
        self.assertEqual(caught.exception.uncertain, uncertain)
        for hidden in (SECRET, TOKEN, 'recipient@example.test'):
            self.assertNotIn(hidden, str(caught.exception))

    def test_acceptance_requires_graph_202_and_uses_canonical_sender(self):
        from .notification_email import SENDER, DISPLAY_NAME
        transport = self.transport(self.token_response(), response(status=202))
        self.assertIsNone(self.send())
        self.assertEqual(transport.call_count, 2)
        auth_call, send_call = transport.call_args_list
        self.assertEqual(auth_call.args[:2], ('POST', f'https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token'))
        self.assertEqual(auth_call.kwargs['data']['scope'], 'https://graph.microsoft.com/.default')
        self.assertEqual(send_call.args[:2], ('POST', 'https://graph.microsoft.com/v1.0/users/ifield.notify%40isurvix.com/sendMail'))
        self.assertEqual(send_call.kwargs['headers']['Authorization'], 'Bearer ' + TOKEN)
        message = send_call.kwargs['json']['message']
        self.assertEqual(message['from']['emailAddress'], {'address': SENDER, 'name': DISPLAY_NAME})
        self.assertEqual(message['body']['contentType'], 'Text')
        self.assertEqual(message['toRecipients'], [{'emailAddress': {'address': 'recipient@example.test'}}])
        for call in (auth_call, send_call):
            self.assertEqual(call.kwargs['timeout'], (5, 15))
            self.assertEqual(call.kwargs['total_timeout'], 20)
        self.assertEqual(auth_call.kwargs['max_bytes'], 65536)
        self.assertFalse(send_call.kwargs['read_body'])
        self.assertEqual(send_call.kwargs['max_bytes'], 0)

    def test_authentication_failure_never_attempts_email(self):
        transport = self.transport(response(status=400, payload={'error_description': SECRET}))
        self.failure('authentication_rejected')
        self.assertEqual(transport.call_count, 1)

    def test_authentication_timeout_can_retry_without_duplicate_mail(self):
        self.transport(DeadlineExceeded())
        self.failure('authentication_unavailable', retryable=True)

    def test_send_timeout_has_uncertain_outcome_and_must_not_auto_retry(self):
        self.transport(self.token_response(), DeadlineExceeded())
        self.failure('send_outcome_unknown', uncertain=True)

    def test_send_connection_failure_is_also_uncertain(self):
        self.transport(self.token_response(), RequestError())
        self.failure('send_outcome_unknown', uncertain=True)

    def test_rate_limit_is_an_explicit_retryable_rejection(self):
        self.transport(self.token_response(), response(status=429))
        self.failure('send_rate_limited', retryable=True)

    def test_permission_denial_is_permanent_and_not_reported_as_sent(self):
        self.transport(self.token_response(), response(status=403))
        self.failure('send_not_authorized')

    def test_unexpected_success_is_not_accepted_or_blindly_retried(self):
        self.transport(self.token_response(), response(status=200))
        self.failure('send_outcome_unknown', uncertain=True)

    def test_send_redirect_is_not_followed_or_reported_as_accepted(self):
        transport = self.transport(self.token_response(), response(status=307))
        self.failure('send_rejected')
        self.assertEqual(transport.call_count, 2)

    def test_invalid_or_oversized_token_response_does_not_attempt_send(self):
        values = [response(raw=b'{broken'), response(raw=b' ' * 70000),
                  self.token_response(access_token='bad\r\nheader'), self.token_response(token_type='Basic'),
                  self.token_response(expires_in=0)]
        for value in values:
            with self.subTest(value=value.status_code), patch('core.notification_email.bounded_request') as transport:
                transport.return_value = value
                self.failure('authentication_invalid_response')
                self.assertEqual(transport.call_count, 1)

    def test_input_validation_happens_before_any_network_request(self):
        from .notification_email import GraphMailClient, NotificationEmailError
        with patch('core.notification_email.bounded_request') as transport:
            client = GraphMailClient(self.config())
            for recipient, subject, body in [('a@example.test\r\nBcc: b@example.test', 'title', 'body'),
                                             ('a@example.test', 'title\nInjected', 'body'),
                                             ('a@example.test', 'title', 'x' * 100000)]:
                with self.subTest(recipient=recipient), self.assertRaises(NotificationEmailError):
                    client.send(recipient, subject, body)
            transport.assert_not_called()


class GraphHTTPIntegrationTests(SimpleTestCase):
    def mail_client(self):
        from .notification_email import GraphMailClient
        return GraphMailClient({'tenant_id': TENANT, 'client_id': CLIENT, 'client_secret': SECRET})

    def test_actual_form_token_exchange_and_json_mail_reach_http_server(self):
        with graph_fixture() as records:
            self.assertIsNone(self.mail_client().send('recipient@example.test', 'Invitation', 'Open https://example.test/invitation-fixture'))
        self.assertEqual(len(records), 2)
        form = parse_qs(records[0]['raw'].decode())
        self.assertEqual(form['grant_type'], ['client_credentials'])
        self.assertEqual(form['client_id'], [CLIENT])
        self.assertEqual(form['client_secret'], [SECRET])
        self.assertIsNone(records[0]['authorization'])
        self.assertEqual(records[1]['authorization'], 'Bearer ' + TOKEN)
        mail = json.loads(records[1]['raw'])
        self.assertEqual(mail['message']['toRecipients'][0]['emailAddress']['address'], 'recipient@example.test')
        self.assertEqual(mail['message']['from']['emailAddress']['address'], 'ifield.notify@isurvix.com')
        self.assertEqual(mail['message']['body']['content'], 'Open https://example.test/invitation-fixture')

    def test_real_authentication_redirect_does_not_leak_credentials_to_target(self):
        from .notification_email import NotificationEmailError
        with graph_fixture(token_status=307) as records:
            with self.assertRaises(NotificationEmailError):
                self.mail_client().send('recipient@example.test', 'Invitation', 'Synthetic')
        self.assertEqual(len(records), 1)

    def test_real_send_redirect_does_not_forward_bearer_to_target(self):
        from .notification_email import NotificationEmailError
        with graph_fixture(send_status=307) as records:
            with self.assertRaises(NotificationEmailError):
                self.mail_client().send('recipient@example.test', 'Invitation', 'Synthetic')
        self.assertEqual(len(records), 2)

    def test_real_malformed_auth_response_preserves_clear_failure(self):
        from .notification_email import NotificationEmailError
        with graph_fixture(token_raw=b'{broken') as records:
            with self.assertRaises(NotificationEmailError) as caught:
                self.mail_client().send('recipient@example.test', 'Invitation', 'Synthetic')
        self.assertEqual(caught.exception.code, 'authentication_invalid_response')
        self.assertEqual(len(records), 1)


@contextmanager
def graph_deadline_fixture(*, phase='token', mode='body'):
    records = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            records.append(self.path)
            token_request = self.path == '/token'
            delayed = token_request == (phase == 'token')
            body = json.dumps({'access_token': TOKEN, 'token_type': 'Bearer', 'expires_in': 3600}).encode() if token_request else b''
            status = 200 if token_request else 202
            try:
                if delayed and mode == 'headers':
                    raw = f'HTTP/1.1 {status} OK\r\nX-Fixture: '.encode() + b'a' * 100 + b'\r\nContent-Length: 0\r\n\r\n'
                    for byte in raw:
                        self.wfile.write(bytes([byte])); self.wfile.flush(); time.sleep(.015)
                    return
                self.send_response(status)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                if delayed:
                    for byte in body:
                        self.wfile.write(bytes([byte])); self.wfile.flush(); time.sleep(.015)
                else:
                    self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    from . import notification_email as mail
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        with patch.object(mail, 'TOKEN_URL_TEMPLATE', origin + '/token'), patch.object(mail, 'SEND_MAIL_URL', origin + '/send'), patch.object(mail, '_REQUEST_DEADLINE', .2, create=True):
            yield records
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


class GraphTotalDeadlineTests(SimpleTestCase):
    def mail_client(self):
        from .notification_email import GraphMailClient
        return GraphMailClient({'tenant_id': TENANT, 'client_id': CLIENT, 'client_secret': SECRET})

    def test_auth_body_drip_is_retryable_but_never_proceeds_to_send(self):
        from .notification_email import NotificationEmailError
        with graph_deadline_fixture() as records:
            start = time.monotonic()
            with self.assertRaises(NotificationEmailError) as caught:
                self.mail_client().send('recipient@example.test', 'Invitation', 'Synthetic')
            elapsed = time.monotonic() - start
        self.assertLess(elapsed, .7)
        self.assertEqual(caught.exception.code, 'authentication_unavailable')
        self.assertTrue(caught.exception.retryable)
        self.assertFalse(caught.exception.uncertain)
        self.assertEqual(records, ['/token'])

    def test_auth_header_drip_is_also_interrupted(self):
        from .notification_email import NotificationEmailError
        with graph_deadline_fixture(mode='headers') as records:
            start = time.monotonic()
            with self.assertRaises(NotificationEmailError) as caught:
                self.mail_client().send('recipient@example.test', 'Invitation', 'Synthetic')
            elapsed = time.monotonic() - start
        self.assertLess(elapsed, .7)
        self.assertEqual(caught.exception.code, 'authentication_unavailable')
        self.assertTrue(caught.exception.retryable)
        self.assertEqual(records, ['/token'])

    def test_send_header_drip_is_uncertain_and_cannot_be_blindly_retried(self):
        from .notification_email import NotificationEmailError
        with graph_deadline_fixture(phase='send', mode='headers') as records:
            start = time.monotonic()
            with self.assertRaises(NotificationEmailError) as caught:
                self.mail_client().send('recipient@example.test', 'Invitation', 'Synthetic')
            elapsed = time.monotonic() - start
        self.assertLess(elapsed, .7)
        self.assertEqual(caught.exception.code, 'send_outcome_unknown')
        self.assertTrue(caught.exception.uncertain)
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(records, ['/token', '/send'])
