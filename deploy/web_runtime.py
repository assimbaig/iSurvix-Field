"""Supervise web and optional mail processes inside one managed writer boundary.

The trusted deployment controller already quiesces this container before backup
or recovery. Mail must not run in the private verification candidate: it starts
only after public HTTPS readiness identifies this exact immutable release.
No Django import, database initialization, OAuth request or mail send happens in
this supervisor. Only the independent management command performs mail work.
"""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

# The supervisor is executed as a script from deploy/. Import only the pure HTTP
# helper; neither Django setup nor the mail worker is imported into this process.
_backend_path = str(Path(__file__).resolve().parents[1]/'backend')
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)
from core.http_deadline import RequestError, request as deadline_request

_READINESS_TOTAL_TIMEOUT = 5


WEB_COMMAND = ['gunicorn', 'checklist.wsgi:application', '--bind', '0.0.0.0:8000',
    '--workers', '1', '--worker-class', 'gthread', '--threads', '4', '--timeout', '120',
    '--worker-tmp-dir', '/tmp', '--access-logfile', '/dev/null', '--error-logfile', '-']
MAIL_COMMAND = [sys.executable, 'manage.py', 'run_invitation_email_worker']


def public_release_ready(environment=None):
    """Check a public, credential-free endpoint without redirects or proxy env."""
    environment = os.environ if environment is None else environment
    origin = environment.get('ISURVIX_NOTIFICATION_PUBLIC_ORIGIN', '').strip()
    release = environment.get('ISURVIX_RELEASE_ID', '')
    allowed = {item.strip().lower() for item in environment.get('DJANGO_ALLOWED_HOSTS', '').split(',')
               if item.strip() and '*' not in item and not item.strip().startswith('.')}
    try:
        parts = urlsplit(origin)
        port = parts.port
        if (parts.scheme != 'https' or not parts.hostname or parts.hostname.lower() not in allowed
                or parts.username or parts.password or parts.path or parts.query or parts.fragment
                or port is not None and not 1 <= port <= 65535
                or not re.fullmatch('[0-9a-f]{40}', release)):
            return False
        response = deadline_request('GET', origin + '/ops/health/ready/',
            total_timeout=_READINESS_TOTAL_TIMEOUT, timeout=(2, 3), max_bytes=4096)
        if response.status_code != 200 or len(response.body) > 4096:
            return False
        result = json.loads(response.body)
        return isinstance(result, dict) and result.get('status') == 'ready' and result.get('release') == release
    except (ValueError, TypeError, RequestError):
        return False


def _signal_process(process, hard=False):
    try:
        if os.name == 'posix':
            # Signal the group even if its leader exited, so Gunicorn children
            # cannot outlive a crashed leader during a deployment backup.
            os.killpg(process.pid, signal.SIGKILL if hard else signal.SIGTERM)
        elif process.poll() is None:
            process.kill() if hard else process.terminate()
    except (ProcessLookupError, PermissionError, OSError):
        pass


def _stop_children(children, timeout):
    children = list(reversed(children))
    for process in children:
        _signal_process(process)
    deadline = time.monotonic() + timeout
    for process in children:
        try:
            process.wait(timeout=max(0.01, deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            _signal_process(process, hard=True)
            process.wait(timeout=5)
    # A group may still contain a descendant after its leader has been reaped.
    # It is a private session created by us, never the operator's process group.
    if os.name == 'posix':
        for process in children:
            _signal_process(process, hard=True)


def supervise(web_command, mail_command=None, *, mail_enabled=False,
              readiness=public_release_ready, poll_interval=0.25, retry_interval=30,
              shutdown_timeout=50, spawn=subprocess.Popen, stop_event=None):
    """Preserve web availability; optional worker failure never restarts the web."""
    if not 0 < poll_interval <= 5 or not 0.1 <= retry_interval <= 300 or not 0 < shutdown_timeout <= 50:
        raise ValueError('Invalid process supervision interval.')
    stop = threading.Event() if stop_event is None else stop_event
    old_handlers = {}
    if threading.current_thread() is threading.main_thread():
        for number in (signal.SIGTERM, signal.SIGINT):
            old_handlers[number] = signal.getsignal(number)
            signal.signal(number, lambda *_: stop.set())
    children = []
    result = 0
    try:
        web = spawn(web_command, start_new_session=os.name == 'posix')
        children.append(web)
        mail = None
        next_mail_attempt = 0.0
        while not stop.is_set():
            exited = web.poll()
            if exited is not None:
                result = exited if exited >= 0 else 128-exited
                break
            if mail is not None and mail.poll() is not None:
                # The outbox retains attempts and uncertain sends. Do not
                # reconstruct links or reset jobs when a worker process exits.
                _signal_process(mail)
                _signal_process(mail, hard=True)
                children.remove(mail)
                next_mail_attempt = time.monotonic() + retry_interval
                mail = None
            if mail_enabled and mail_command and mail is None and time.monotonic() >= next_mail_attempt:
                next_mail_attempt = time.monotonic() + retry_interval
                try:
                    active = readiness()
                except Exception:
                    active = False
                if active:
                    try:
                        mail = spawn(mail_command, start_new_session=os.name == 'posix')
                        children.append(mail)
                    except OSError:
                        # Report neither command arguments nor secret paths.
                        print('Invitation email worker could not start; queued invitations retained.', file=sys.stderr)
            stop.wait(poll_interval)
    except OSError:
        print('Application runtime could not start.', file=sys.stderr)
        result = 1
    finally:
        _stop_children(children, shutdown_timeout)
        for number, previous in old_handlers.items():
            signal.signal(number, previous)
    return result


def main():
    return supervise(WEB_COMMAND, MAIL_COMMAND,
                     mail_enabled=os.environ.get('ISURVIX_NOTIFICATION_EMAIL_ENABLED') == 'True')


if __name__ == '__main__':
    raise SystemExit(main())
