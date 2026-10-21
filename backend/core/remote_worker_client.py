"""Outbound HTTPS client. No inbound PC listener and no production DB connection."""
import base64
import hashlib
import json
import logging
import os
import getpass
import subprocess
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.core.exceptions import ValidationError
from . import local_ai, survey_evidence, survey_checklist_mapping
from .remote_worker_service import versions

logger = logging.getLogger(__name__)


class WorkerConnectionError(RuntimeError):
    pass


class WorkerAccessError(RuntimeError):
    pass


class WorkerRejectedError(WorkerAccessError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a scoped bearer token to a redirected host or login page.
        return None


def secure_private_path(path, directory=False):
    """Restrict new worker secrets/cache with native Windows ACLs or POSIX mode."""
    path = Path(path)
    if os.name == 'nt':
        account = (os.environ.get('USERDOMAIN', '') + '\\' + getpass.getuser()).lstrip('\\')
        permission = account + (':(OI)(CI)F' if directory else ':F')
        subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r', permission],
            check=True, capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    else:
        path.chmod(0o700 if directory else 0o600)


class RemoteSurveyClient:
    def __init__(self, base_url, token, cache_dir, timeout=60):
        parsed = urlsplit(base_url)
        if (parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname
                or parsed.scheme not in {'http', 'https'} or parsed.path not in {'', '/'}
                or parsed.scheme != 'https' and parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}):
            raise ValidationError('Use an HTTPS server origin, or loopback HTTP for isolated testing.')
        if not isinstance(token, str) or not token or any(char.isspace() for char in token):
            raise ValidationError('Read a scoped worker credential from the private configuration file.')
        self.base_url, self.token = base_url.rstrip('/') + '/api/survey-worker/v1/', token
        self.timeout = timeout
        self.cache = Path(cache_dir).resolve()
        self.cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        secure_private_path(self.cache, directory=True)
        self.opener = build_opener(NoRedirect())

    def request(self, path, payload=None, lease='', binary=False):
        headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'image/jpeg' if binary else 'application/json'}
        if lease:
            headers['X-Worker-Lease'] = lease
        data = None
        if payload is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(payload, allow_nan=False, separators=(',', ':')).encode()
        request = Request(self.base_url + path, data=data, headers=headers)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                limit = 4 * 1024 * 1024 if binary else 256 * 1024
                body = response.read(limit + 1)
                if len(body) > limit:
                    raise WorkerConnectionError('The worker server exceeded the bounded input size.')
                if binary:
                    if response.headers.get_content_type() != 'image/jpeg':
                        raise WorkerConnectionError('The worker server returned an invalid image input.')
                    return body
                if response.headers.get_content_type() != 'application/json':
                    raise WorkerConnectionError('The worker server returned a non-JSON response.')
                result = json.loads(body)
                if not isinstance(result, dict):
                    raise WorkerConnectionError('The worker server returned an invalid JSON response.')
                return result
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise WorkerAccessError('Worker credentials or lease expired/revoked. Ask the project Admin to check the scoped credential.') from None
            if exc.code == 409:
                raise WorkerRejectedError('The server rejected incompatible software or invalid structured results; saved checkpoints are preserved.') from None
            if exc.code in {400, 404, 405, 413}:
                raise WorkerAccessError('The server rejected this worker request. Check software versions, project assignment and immutable inputs; no results were replaced.') from None
            raise WorkerConnectionError('The survey server is temporarily unavailable; saved local results will be retried.') from None
        except (URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
            raise WorkerConnectionError('The survey server connection was interrupted; saved local results are preserved.') from None

    def model_identity(self):
        model = settings.OLLAMA_MODEL
        endpoint = getattr(settings, 'PHOTO_OLLAMA_BASE_URL', settings.OLLAMA_BASE_URL)
        survey_evidence._vision_check(model, endpoint)
        details = local_ai.ollama('/api/show', {'model': model}, base_url=endpoint)
        # Same pinned identity as the existing in-process survey worker.
        identity = hashlib.sha256(json.dumps({'model': model, 'details': details, 'pipeline': versions()['pipeline']},
            sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        return model, identity

    def _atomic_cache(self, path, value):
        if path.resolve().parent != self.cache:
            raise WorkerAccessError('The private worker cache path is invalid.')
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
        temporary = path.with_suffix('.partial')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

    def _read_cached(self, path, identity):
        if not path.exists():
            return None
        try:
            cached = json.loads(path.read_text(encoding='utf-8'))
            result_digest = hashlib.sha256(json.dumps(cached.get('result'), ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()
            if cached.get('identity') == identity and cached.get('result_digest') == result_digest:
                return cached['result']
        except (ValueError, TypeError, AttributeError):
            pass
        quarantine = path.with_suffix('.quarantined.json')
        if path.resolve().parent != self.cache or quarantine.resolve().parent != self.cache:
            raise WorkerAccessError('The private worker cache path is invalid.')
        os.replace(path, quarantine)
        logger.warning('A private worker result cache failed integrity verification; it was preserved separately and will be recomputed.')
        return None

    def process_job(self, job, model_digest):
        prefix, token = f'jobs/{job["job_id"]}/', job['lease']
        stopped, lost = threading.Event(), threading.Event()
        def heartbeat():
            while not stopped.wait(20):
                try:
                    self.request(prefix + 'heartbeat/', {}, lease=token)
                except (WorkerConnectionError, WorkerAccessError):
                    lost.set()
                    return
        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            while True:
                task = self.request(prefix + 'next/', {}, lease=token)
                if task.get('complete'):
                    return True
                if task.get('versions') != versions() or task.get('model') != job['model']:
                    raise WorkerAccessError('The server task is incompatible with this worker release.')
                identity = hashlib.sha256(json.dumps([self.base_url, job['snapshot_digest'], task['task_id'], task['input_digest'], model_digest, versions()],
                    sort_keys=True).encode()).hexdigest()
                cached_file = self.cache / (identity + '.json')
                result = self._read_cached(cached_file, identity)
                if result is None:
                    source = dict(task['input'])
                    if task.get('image_size'):
                        raw = self.request(prefix + f'tasks/{task["task_id"]}/image/', lease=token, binary=True)
                        if len(raw) != task['image_size'] or hashlib.sha256(raw).hexdigest() != task['image_sha256']:
                            raise WorkerConnectionError('A transferred image failed integrity verification; no inference was run.')
                        source['image_b64'] = base64.b64encode(raw).decode('ascii')
                    from .photo_queue import photo_inference_lease
                    with photo_inference_lease() as check:
                        endpoint = getattr(settings, 'PHOTO_OLLAMA_BASE_URL', settings.OLLAMA_BASE_URL)
                        result = (survey_evidence.analyse_source(source, job['model'], base_url=endpoint)
                            if task['kind'] == 'source' else survey_checklist_mapping.bind_batch(source, job['model'], base_url=endpoint))
                        check()
                    result_digest = hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()
                    self._atomic_cache(cached_file, {'identity': identity, 'result_digest': result_digest, 'result': result})
                if lost.is_set():
                    # Re-establish the server lease before delivering an inference
                    # completed while disconnected. A lost lease cannot overwrite.
                    self.request(prefix + 'heartbeat/', {}, lease=token)
                    lost.clear()
                try:
                    self.request(prefix + f'tasks/{task["task_id"]}/complete/',
                        {'versions': versions(), 'input_digest': task['input_digest'], 'result': result}, lease=token)
                except WorkerRejectedError:
                    # Preserve the rejected result for diagnosis, but do not let
                    # a poison cache silently loop on every authorised retry.
                    os.replace(cached_file, cached_file.with_suffix('.rejected.json'))
                    self.request(prefix + 'failure/', {'code': 'invalid_response', 'retryable': False}, lease=token)
                    raise
        finally:
            stopped.set()
            thread.join(timeout=self.timeout + 1)

    def process_once(self):
        model, identity = self.model_identity()
        response = self.request('claim/', {'versions': versions(), 'model': model, 'model_digest': identity})
        job = response.get('job')
        if not job:
            return False
        try:
            return self.process_job(job, identity)
        except (WorkerConnectionError, WorkerAccessError):
            # The server retains ownership/checkpoints until lease expiration.
            # Reconnection/restart reclaims safely and uses durable local results.
            raise
        except Exception as exc:
            code = 'local_busy' if isinstance(exc, local_ai.InferenceBusy) else 'local_unavailable' if isinstance(exc, (ConnectionError, TimeoutError, URLError)) else 'invalid_response'
            self.request(f'jobs/{job["job_id"]}/failure/', {'code': code, 'retryable': code == 'local_busy'}, lease=job['lease'])
            raise WorkerConnectionError('Local analysis could not finish. Server checkpoints are preserved; inspect the private worker log and retry.') from None
