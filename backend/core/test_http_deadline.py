"""Actual header/body/DNS deadline regressions on isolated loopback services."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import subprocess
import threading
import time
from unittest.mock import patch

from django.test import SimpleTestCase


@contextmanager
def slow_http_fixture(*, mode='normal', status=200, delay=.015):
    records = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.reply()

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            records.append((self.path, raw))
            self.reply()

        def reply(self):
            body = json.dumps({'access_token': 'synthetic.token', 'token_type': 'Bearer', 'expires_in': 3600}).encode()
            try:
                if mode == 'headers':
                    raw = b'HTTP/1.1 200 OK\r\nX-Fixture: ' + b'a' * 150 + b'\r\nContent-Length: 0\r\n\r\n'
                    for byte in raw:
                        self.wfile.write(bytes([byte])); self.wfile.flush(); time.sleep(delay)
                    return
                self.send_response(status)
                self.send_header('Content-Length', str(len(body)))
                if status == 307:
                    self.send_header('Location', '/must-not-follow')
                self.end_headers()
                if mode == 'body':
                    for byte in body:
                        self.wfile.write(bytes([byte])); self.wfile.flush(); time.sleep(delay)
                else:
                    self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                # Cancellation deliberately closes the fixture connection.
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', records
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


class TotalHTTPDeadlineTests(SimpleTestCase):
    def test_repeated_body_bytes_do_not_extend_absolute_request_deadline(self):
        from .http_deadline import request, DeadlineExceeded
        with slow_http_fixture(mode='body') as (origin, _):
            start = time.monotonic()
            with self.assertRaises(DeadlineExceeded):
                request('GET', origin, total_timeout=.25, timeout=(1, 1), max_bytes=4096)
            elapsed = time.monotonic() - start
        self.assertLess(elapsed, .7)

    def test_repeated_header_bytes_do_not_extend_absolute_request_deadline(self):
        from .http_deadline import request, DeadlineExceeded
        with slow_http_fixture(mode='headers') as (origin, _):
            start = time.monotonic()
            with self.assertRaises(DeadlineExceeded):
                request('GET', origin, total_timeout=.25, timeout=(1, 1), max_bytes=4096)
            elapsed = time.monotonic() - start
        self.assertLess(elapsed, .7)

    def test_dns_child_is_killed_and_reaped_within_the_same_deadline(self):
        from . import http_deadline
        created = []
        original_popen = subprocess.Popen

        def capture(*args, **kwargs):
            process = original_popen(*args, **kwargs)
            created.append(process)
            return process

        with patch.object(http_deadline, '_DNS_CODE', 'import time;time.sleep(10)'), patch.object(http_deadline.subprocess, 'Popen', side_effect=capture):
            start = time.monotonic()
            with self.assertRaises(http_deadline.DeadlineExceeded):
                http_deadline.request('GET', 'https://synthetic.example.test', total_timeout=.25, timeout=(1, 1), max_bytes=4096)
            elapsed = time.monotonic() - start
        self.assertLess(elapsed, .7)
        self.assertEqual(len(created), 1)
        self.assertIsNotNone(created[0].poll())

    def test_response_size_is_bounded_and_not_returned_as_truncated_success(self):
        from .http_deadline import request, ResponseTooLarge
        with slow_http_fixture() as (origin, _):
            with self.assertRaises(ResponseTooLarge):
                request('GET', origin, total_timeout=2, timeout=(1, 1), max_bytes=8)

    def test_successful_response_and_redirect_policy_are_preserved(self):
        from .http_deadline import request
        with slow_http_fixture() as (origin, _):
            result = request('GET', origin, total_timeout=2, timeout=(1, 1), max_bytes=4096)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(json.loads(result.body)['access_token'], 'synthetic.token')
        with slow_http_fixture(status=307) as (origin, records):
            result = request('POST', origin, data={'fixture': 'synthetic'}, total_timeout=2, timeout=(1, 1), max_bytes=4096)
        self.assertEqual(result.status_code, 307)
        self.assertEqual(len(records), 1)

    def test_environment_proxies_cannot_capture_request_payloads(self):
        from .http_deadline import request
        with slow_http_fixture() as (origin, records), patch.dict(os.environ, {
                'HTTP_PROXY': 'http://127.0.0.1:9', 'HTTPS_PROXY': 'http://127.0.0.1:9',
                'ALL_PROXY': 'http://127.0.0.1:9', 'NO_PROXY': ''}):
            result = request('POST', origin, data={'fixture': 'synthetic'},
                total_timeout=2, timeout=(1, 1), max_bytes=4096)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(records), 1)

    def test_cancellation_leaves_no_per_request_background_threads(self):
        from .http_deadline import request, DeadlineExceeded
        with slow_http_fixture(mode='body') as (origin, _):
            before = {thread.ident for thread in threading.enumerate()}
            for _ in range(3):
                with self.assertRaises(DeadlineExceeded):
                    request('GET', origin, total_timeout=.1, timeout=(1, 1), max_bytes=4096)
            time.sleep(.1)
            extra = [thread.name for thread in threading.enumerate()
                     if thread.ident not in before and 'process_request_thread' not in thread.name]
        self.assertEqual(extra, [])
