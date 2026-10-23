r"""Run ordinary Django tests without operational data, private models or network.

From the repository root:
    .local\venv\Scripts\python.exe scripts\run_backend_tests.py
Pass Django test labels/options to run a focused subset. Native Ollama checks
belong to the separate check_local_vision.py / explicit integration workflows.
"""
import copy
import json
import logging
import os
from pathlib import Path
import socket
import sys
import tempfile
from contextlib import ExitStack, contextmanager
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def network_isolation(attempts, fixture_connections):
    """Guard Python networking during Django startup as well as test execution."""
    listeners = {}
    original_bind, original_close = socket.socket.bind, socket.socket.close
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def fixture_bind(sock, address):
        result = original_bind(sock, address)
        if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1', 'localhost'):
            listeners[id(sock)] = sock.getsockname()[:2]
        return result

    def fixture_close(sock):
        listeners.pop(id(sock), None)
        return original_close(sock)

    def guarded_connect(sock, address, operation=original_connect):
        # Only listeners created inside this guard are fixtures; an independently
        # running user Ollama instance (including loopback) remains out of scope.
        if isinstance(address, tuple) and address[:2] in listeners.values():
            fixture_connections.append(str(address))
            return operation(sock, address)
        attempts.append(str(address))
        raise OSError('Ordinary tests cannot connect to external services; use an explicit integration check.')

    with ExitStack() as guard:
        guard.enter_context(patch.object(socket.socket, 'bind', fixture_bind))
        guard.enter_context(patch.object(socket.socket, 'close', fixture_close))
        guard.enter_context(patch.object(socket.socket, 'connect', guarded_connect))
        guard.enter_context(patch.object(socket.socket, 'connect_ex',
            lambda sock, address: guarded_connect(sock, address, original_connect_ex)))
        yield


def main():
    # Native ONNX telemetry is outside Python's socket monkeypatches. Its
    # documented opt-out must precede Django setup and any native imports.
    os.environ['ORT_DISABLE_TELEMETRY'] = '1'
    sys.path.insert(0, str(ROOT / 'backend'))
    os.environ['DJANGO_SETTINGS_MODULE'] = 'checklist.settings_local'
    runs = ROOT / '.local' / 'test-runs'
    runs.mkdir(parents=True, exist_ok=True)
    attempts = []
    fixture_connections = []
    exit_code = 0
    with network_isolation(attempts, fixture_connections), tempfile.TemporaryDirectory(prefix='ordinary-', dir=runs) as temporary:
        state = Path(temporary)
        for key in ('HF_HOME', 'HF_HUB_CACHE', 'FASTEMBED_CACHE_PATH', 'TRANSFORMERS_CACHE'):
            os.environ[key] = str(state / key.lower())
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        from django.conf import settings

        # Isolate defaults before app setup as well as the test database which
        # Django creates. Fixtures may still use their own temporary directories.
        databases = copy.deepcopy(settings.DATABASES)
        databases['default']['NAME'] = state / 'unpopulated.sqlite3'
        databases['default']['TEST'] = {'NAME': ':memory:'}
        settings.DATABASES = databases
        settings.MEDIA_ROOT = state / 'media'
        settings.MEDIA_ROOT.mkdir()
        settings.FILE_UPLOAD_TEMP_DIR = temporary
        logging_config = copy.deepcopy(settings.LOGGING)
        if 'file' in logging_config.get('handlers', {}):
            logging_config['handlers']['file']['filename'] = state / 'tests.log'
        settings.LOGGING = logging_config
        settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': temporary}}
        import django
        django.setup()
        from django.core.management import execute_from_command_line
        from django.core.management.commands.test import Command as TestCommand
        from core import photo_search, evidence_pipeline

        test_arguments = sys.argv[1:]
        parsed = TestCommand().create_parser('manage.py', 'test').parse_args(test_arguments)
        if not parsed.args:
            test_arguments = ['core', *test_arguments]

        with ExitStack() as stack:
            stack.enter_context(patch.object(photo_search, 'MODELS', state / 'photo-search-models'))
            stack.enter_context(patch.object(photo_search, 'STATE', state / 'photo-search-state'))
            stack.enter_context(patch.object(evidence_pipeline, 'CACHE', state / 'embedding-models'))
            try:
                execute_from_command_line(['manage.py', 'test', *test_arguments, '--noinput'])
            except SystemExit as error:
                exit_code = error.code or 0
        if attempts:
            print('FAIL: ordinary tests attempted external connections: ' + json.dumps(attempts), file=sys.stderr)
            exit_code = exit_code or 1
        else:
            print('Isolation: temporary database/media/model cache; zero external network attempts; '
                  f'{len(fixture_connections)} connections to in-process HTTP fixtures.')
        # Windows requires every handle to be closed before TemporaryDirectory
        # removes its files. Do not leave a test logger holding tests.log open.
        from django.db import connections
        connections.close_all()
        logging.shutdown()
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
