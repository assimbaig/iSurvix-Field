"""Read local runtime metadata and collect private, redacted crash diagnostics.

These commands never download models, restart services, perform inference,
claim remote jobs, read survey originals or upload diagnostic information.
"""
import argparse
from datetime import datetime, timezone
import getpass
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import uuid


LOOPBACK = {'127.0.0.1', 'localhost', '::1'}
MODEL_LIMIT = 160


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def loopback_origin(value):
    if not isinstance(value, str) or len(value) > 256 or any(c.isspace() for c in value):
        raise ValueError('Choose an explicit HTTP loopback Ollama origin.')
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError:
        raise ValueError('Choose a valid local service port.') from None
    if (parsed.scheme != 'http' or parsed.hostname not in LOOPBACK or
            parsed.username or parsed.password or parsed.path not in {'', '/'} or
            parsed.query or parsed.fragment or port is not None and not 1 <= port <= 65535):
        raise ValueError('Use an HTTP loopback origin without credentials, paths or query strings.')
    return value.rstrip('/')


def _json(origin, path, payload=None):
    request = Request(origin + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    # Local metadata must never be sent through an environment-configured proxy
    # or forwarded to a redirected public service.
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=10) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('The local metadata response is too large.')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('The local service returned invalid metadata.')
    return value


def _model_name(model):
    if (not isinstance(model, str) or not model or len(model) > MODEL_LIMIT or
            any(c.isspace() for c in model) or any(alias in model.lower() for alias in (':cloud', '-cloud'))):
        raise ValueError('Choose an already installed local model.')
    return model


def local_metadata(model, service_url):
    model, origin = _model_name(model), loopback_origin(service_url)
    models = _json(origin, '/api/tags').get('models')
    installed = next((row for row in models if isinstance(row, dict) and row.get('name') == model), None) if isinstance(models, list) else None
    if not installed or installed.get('remote_host') or installed.get('remote_model'):
        raise ValueError('The selected model must already be installed locally; no download was attempted.')
    details = _json(origin, '/api/show', {'model': model})
    if ('vision' not in details.get('capabilities', []) or
            details.get('remote_host') or details.get('remote_model')):
        raise ValueError('The installed model must advertise local vision capability.')
    return {'service_url': origin, 'model': model, 'installed': True, 'vision': True,
        'check': 'installed_metadata_only', 'native_inference_performed': False}


def _private_config(path):
    path = Path(path)
    if path.stat().st_size > 65536:
        raise ValueError('Use the existing private worker configuration.')
    config = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(config, dict):
        raise ValueError('Use the existing private worker configuration.')
    server, token = config.get('server_url'), config.get('token')
    if not isinstance(server, str) or not isinstance(token, str) or not token or any(c.isspace() for c in token):
        raise ValueError('Use the scoped configuration created by the project Admin.')
    parsed = urlsplit(server)
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or
            parsed.path not in {'', '/'} or parsed.scheme not in {'https', 'http'}):
        raise ValueError('The worker server must be an HTTPS origin.')
    if parsed.scheme == 'http':
        loopback_origin(server)
    # Credentials are only checked in memory; never return, copy or print them.


def validate_startup(*, model, photo_url, text_url, config_path):
    photo_url, text_url = loopback_origin(photo_url), loopback_origin(text_url)
    _private_config(config_path)
    photo = local_metadata(model, photo_url)
    text = photo if text_url == photo_url else local_metadata(model, text_url)
    return {'photo': photo, 'text': text, 'worker_config_valid': True,
        'native_inference_performed': False, 'jobs_claimed': False}


def _secure(path, directory=False):
    if os.name == 'nt':
        account = (os.environ.get('USERDOMAIN', '') + '\\' + getpass.getuser()).lstrip('\\')
        permission = account + (':(OI)(CI)F' if directory else ':F')
        subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r', permission],
            check=True, capture_output=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    else:
        path.chmod(0o700 if directory else 0o600)


def _log_hints(local):
    candidates = []
    for pattern, kind in [('app.log', 'application'), ('worker-*.stderr.log', 'photo_worker'),
            ('photo-search-*.stderr.log', 'search_worker'),
            ('survey-processing-*.stderr.log', 'survey_worker'), ('photo-ai-*.stderr.log', 'photo_runtime')]:
        for path in local.glob(pattern):
            if not path.is_symlink() and path.is_file():
                candidates.append((path.stat().st_mtime, path, kind))
    signals = {'segmentation_fault': r'segmentation fault|SIGSEGV|exit(?:\s+code)?\s+139',
        'access_violation': r'0xc0000005|access violation', 'onnxruntime': r'onnxruntime',
        'opencv': r'cv2|opencv', 'out_of_memory': r'out of memory|MemoryError|CUDA.*memory',
        'missing_runner': r'runner.*(?:missing|not found)|(?:missing|not found).*runner'}
    hints = []
    for modified, path, kind in sorted(candidates, reverse=True)[:8]:
        with path.open('rb') as handle:
            handle.seek(max(0, path.stat().st_size - 65536))
            tail = handle.read(65536).decode('utf-8', errors='replace')
        hints.append({'log_kind': kind, 'size_bytes': path.stat().st_size,
            'modified_utc': datetime.fromtimestamp(modified, timezone.utc).isoformat(),
            'signals': [name for name, pattern in signals.items() if re.search(pattern, tail, re.I)],
            'raw_content_retained': False})
    return hints


def collect_diagnostics(*, project_root, model, photo_url, text_url, powershell_version=''):
    photo_url, text_url = loopback_origin(photo_url), loopback_origin(text_url)
    model = _model_name(model)
    project_root = Path(project_root).resolve()
    health = {}
    for name, origin in [('photo', photo_url), ('text', text_url)]:
        try:
            health[name] = local_metadata(model, origin)
        except Exception as error:
            health[name] = {'service_url': origin, 'ready': False,
                'error_type': type(error).__name__, 'native_inference_performed': False}
    versions = {}
    for distribution in ['Django', 'Pillow', 'PyMuPDF', 'opencv-python',
            'rapidocr-onnxruntime', 'onnxruntime', 'fastembed', 'numpy']:
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = 'not_installed'
    commit = 'not_available'
    try:
        candidate = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=project_root,
            stderr=subprocess.DEVNULL, timeout=5, text=True).strip()
        if re.fullmatch(r'[0-9a-f]{40}', candidate):
            commit = candidate
    except (OSError, subprocess.SubprocessError):
        pass
    local = project_root / '.local'
    directory = local / 'diagnostics'
    if local.is_symlink() or directory.is_symlink():
        raise ValueError('Choose the existing project directory for private diagnostics.')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    _secure(directory, directory=True)
    data = {'created_utc': datetime.now(timezone.utc).isoformat(), 'commit': commit,
        'platform': {'system': platform.system(), 'release': platform.release(),
            'machine': platform.machine(), 'python': platform.python_version(),
            'powershell': powershell_version if re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}', powershell_version) else 'not_recorded'},
        'package_versions': versions, 'runtime_metadata': health,
        'crash_log_hints': _log_hints(local), 'raw_logs_copied': False,
        'credentials_collected': False, 'native_inference_performed': False, 'uploaded': False,
        'a12_status': 'Open: metadata and crash hints do not establish or repair the native crash root cause.'}
    filename = 'runtime-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8] + '.json'
    path = directory / filename
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
        json.dump(data, output, indent=2)
        output.write('\n')
    _secure(path)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['check', 'diagnostics'])
    parser.add_argument('--model', required=True)
    parser.add_argument('--photo-url', required=True)
    parser.add_argument('--text-url', required=True)
    parser.add_argument('--config')
    parser.add_argument('--project-root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--powershell-version', default='')
    args = parser.parse_args()
    try:
        if args.operation == 'check':
            result = validate_startup(model=args.model, photo_url=args.photo_url,
                text_url=args.text_url, config_path=args.config)
            print(json.dumps(result))
        else:
            print(collect_diagnostics(project_root=args.project_root, model=args.model,
                photo_url=args.photo_url, text_url=args.text_url, powershell_version=args.powershell_version))
    except Exception:
        print('Local runtime metadata could not be verified. Check the explicit loopback origins, installed vision model and private configuration; no service was changed.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
