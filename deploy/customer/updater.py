"""Operator-only, offline customer updates with an independent recovery journal.

The website never runs this helper or receives a Docker socket. A successful
request is not release approval: the operator must acknowledge the draft, stop
all external writers and use an independently trusted catalog/package inventory.
"""
import argparse
from contextlib import contextmanager
import hashlib
import hmac
from http.client import HTTPException, HTTPResponse
import json
import os
from pathlib import Path
import re
import socket
import ssl
import stat
import sys
import time
import types
import uuid


def _module(path, name):
    result = types.ModuleType(name)
    result.__file__ = str(path)
    exec(compile(Path(path).read_bytes(), str(path), 'exec'), result.__dict__)
    return result


# This is the installed/trusted host verifier, never the candidate's verifier.
customer = _module(Path(__file__).with_name('customer.py'), 'installed_customer_package')
REQUEST_FIELDS = {'format', 'request_id', 'request_key', 'source_release', 'target_release',
    'manifest_sha256', 'catalog_sha256', 'edition', 'nonce', 'maintenance_confirmed',
    'release_record_sha256', 'issued_at', 'expires_at'}
BINDINGS = ('request_id', 'source_release', 'target_release', 'manifest_sha256',
            'catalog_sha256', 'edition', 'nonce')
TERMINAL = {'completed', 'rolled_back', 'cancelled'}
REQUEST_STATE_SCRIPT = """# ISURVIX_REQUEST_STATE_V1: fixed read-only host recovery query
import django,json,sys
django.setup()
from core.update_models import ServerUpdateRequest
r=ServerUpdateRequest.objects.get(pk=sys.argv[1])
print(json.dumps({'request_id':str(r.pk),'source_release':r.source_release,
'target_release':r.target_release,'manifest_sha256':r.manifest_sha256,
'catalog_sha256':r.catalog_sha256,'edition':r.edition,'nonce':r.nonce,
'status':r.status,'error_code':r.error_code,'last_sequence':r.last_sequence},sort_keys=True))
"""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('utf-8')


def signature(secret, domain, payload):
    if domain not in ('request-v1', 'receipt-v1', 'host-terminal-v1'):
        raise ValueError('Unsupported update signing purpose.')
    key = hmac.new(secret.encode('utf-8'), b'isurvix-update-bridge-v1', hashlib.sha256).digest()
    return hmac.new(key, domain.encode('ascii')+b'\n'+canonical(payload), hashlib.sha256).hexdigest()


def _uuid(value):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Use the canonical saved update request identity.') from None
    return value


def _sha(value, count=40):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{%d}' % count, value):
        raise ValueError('An exact update content/version identity is required.')
    return value


def verify_request(signed, secret, request_id, *, check_expiry=True):
    if (not isinstance(signed, dict) or set(signed) != {'payload', 'signature'} or
            not isinstance(signed['payload'], dict) or set(signed['payload']) != REQUEST_FIELDS):
        raise ValueError('The signed update request is invalid.')
    payload = signed['payload']
    digest = _sha(signed['signature'], 64)
    if not hmac.compare_digest(signature(secret, 'request-v1', payload), digest):
        raise ValueError('The update request signature is invalid.')
    if (payload['format'] != 'isurvix-update-request-v1' or
            _uuid(payload['request_id']) != _uuid(request_id) or
            payload['edition'] not in ('customer', 'cloud') or payload['maintenance_confirmed'] is not True):
        raise ValueError('The update request does not authorize this maintenance operation.')
    _uuid(payload['request_key'])
    for name in ('source_release', 'target_release'):
        _sha(payload[name])
    for name in ('manifest_sha256', 'catalog_sha256'):
        _sha(payload[name], 64)
    if payload['release_record_sha256']:
        _sha(payload['release_record_sha256'], 64)
    _sha(payload['nonce'], 32)
    now = int(time.time())
    if (type(payload['issued_at']) is not int or type(payload['expires_at']) is not int or
            not 0 < payload['expires_at']-payload['issued_at'] <= 300 or
            payload['source_release'] == payload['target_release'] or
            (check_expiry and not payload['issued_at']-30 <= now <= payload['expires_at'])):
        raise ValueError('The update authorization expired or names an invalid version transition.')
    return payload


def _read(path, maximum=131072):
    path = customer._no_links(path)
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > maximum:
        raise ValueError('A bounded regular update configuration file is required.')
    value = customer._json(path)
    if len(canonical(value)) > maximum:
        raise ValueError('The update configuration exceeds its supported size.')
    return value


def _atomic(path, value):
    path = customer._no_links(path)
    temporary = path.with_name(path.name+'.new')
    # A leftover temporary file is retained as evidence of an interrupted write;
    # choose another transaction/recover explicitly instead of replacing it.
    with temporary.open('xb') as stream:
        stream.write(canonical(value)+b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(0o600)
    os.replace(temporary, path)
    if os.name == 'posix':
        descriptor = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


@contextmanager
def _lock(root):
    root = customer._no_links(root)
    if not root.is_dir():
        raise ValueError('Use an existing private independent operator journal directory.')
    if os.name == 'posix' and (root.stat().st_uid != os.geteuid() or root.stat().st_mode & 0o022):
        raise ValueError('The operator journal must be owned by this operator and not group/world writable.')
    path = customer._no_links(root/'.update.lock')
    with path.open('a+b') as stream:
        path.chmod(0o600)
        try:
            if os.name == 'posix':
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                import msvcrt
                stream.seek(0)
                if not stream.read(1):
                    stream.write(b'0')
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except (OSError, BlockingIOError):
            raise ValueError('Another host update/recovery operation holds the independent journal lock.') from None
        try:
            yield
        finally:
            if os.name == 'posix':
                fcntl.flock(stream, fcntl.LOCK_UN)
            else:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def _compose(package, runtime, state):
    return customer._compose_base(package, runtime, state)


def _container(package, runtime, state, *args):
    return customer._docker(*_compose(package, runtime, state), 'exec', '-T', 'web', *args)


def _cancelled_request(package, runtime, state, payload):
    # Only the fixed installed-app ORM query runs; the UUID is a separate argv
    # value, never interpolated as Python or shell text. No write is performed.
    raw = _container(package, runtime, state, 'python', '-c', REQUEST_STATE_SCRIPT, payload['request_id'])
    if len(raw) > 16384:
        raise ValueError('The installed application returned an oversized request state.')
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError('The installed application could not establish terminal cancellation.') from None
    expected = {key: payload[key] for key in BINDINGS}
    expected.update(status='failed', error_code='cancelled', last_sequence=1)
    if value != expected:
        raise ValueError('The installed request is not the exact terminal owner cancellation; preserve the journal for recovery.')
    return value


def _catalog(update_directory, payload):
    path = Path(update_directory)/'catalog.json'
    if customer._digest(path)['sha256'] != payload['catalog_sha256']:
        raise ValueError('The trusted catalog changed; no candidate was executed.')
    value = _read(path)
    if not isinstance(value, dict) or set(value) != {'format', 'releases'} or value['format'] != 'isurvix-update-catalog-v1':
        raise ValueError('The trusted catalog format is invalid.')
    rows = value['releases']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 128:
        raise ValueError('The trusted catalog release list is invalid.')
    seen = set()
    selected = None
    for row in rows:
        required = {'release_id', 'manifest_sha256', 'supported_from', 'editions'}
        if not isinstance(row, dict) or not required <= set(row) or set(row)-required-{'release_record_sha256'}:
            raise ValueError('The trusted catalog entry is invalid.')
        release = _sha(row['release_id'])
        _sha(row['manifest_sha256'], 64)
        if release in seen:
            raise ValueError('The trusted catalog repeats a release identity.')
        seen.add(release)
        sources, editions = row['supported_from'], row['editions']
        if (not isinstance(sources, list) or not 1 <= len(sources) <= 128 or len(set(sources)) != len(sources)
                or any(not isinstance(value, str) or not re.fullmatch('[a-f0-9]{40}', value) for value in sources)
                or not isinstance(editions, list) or not editions or len(set(editions)) != len(editions)
                or any(value not in ('customer', 'cloud') for value in editions)):
            raise ValueError('The trusted catalog support/edition rules are invalid.')
        if row.get('release_record_sha256'):
            _sha(row['release_record_sha256'], 64)
        if release == payload['target_release']:
            selected = row
    if (selected is None or selected['manifest_sha256'] != payload['manifest_sha256'] or
            selected.get('release_record_sha256', '') != payload['release_record_sha256'] or
            payload['source_release'] not in selected['supported_from'] or payload['edition'] not in selected['editions']):
        raise ValueError('The catalog does not support this exact source, target, artifact and edition.')
    return selected


def _package(packages_root, payload):
    release = customer._no_links(Path(packages_root)/payload['target_release'])
    package = release/'package'
    manifest = customer.verify_package(package, expected_manifest_sha256=payload['manifest_sha256'])
    if manifest['release_id'] != payload['target_release']:
        raise ValueError('The candidate package names another source release.')
    if payload['release_record_sha256']:
        record_path = release/'shared/release.json'
        if customer._digest(record_path)['sha256'] != payload['release_record_sha256']:
            raise ValueError('The shared release record failed its independent digest check.')
        record = _read(record_path)
        if (record.get('format') != 'isurvix-shared-release-v1' or
                record.get('source_commit') != payload['target_release'] or
                record.get('manifest_sha256') != payload['manifest_sha256'] or
                record.get('images') != manifest['images'] or
                payload['source_release'] not in record.get('supported_from', []) or
                payload['edition'] not in record.get('editions', []) or
                record.get('candidate_only') is not True or record.get('owner_release_approved') is not False):
            raise ValueError('The gated shared release record does not bind this candidate path.')
    return package, manifest


def _health(package, runtime, state, release):
    # Compose web is started without a proxy/listener. Poll only bounded local
    # readiness; this never contacts the PC/model or an external host.
    for attempt in range(30):
        try:
            observed = _container(package, runtime, state, 'cat', '/app/RELEASE').decode('ascii').strip()
            if observed != release:
                raise ValueError('The running container differs from the requested immutable release.')
            _container(package, runtime, state, 'python', '/app/deploy/healthcheck.py')
            return
        except ValueError:
            if attempt == 29:
                raise
            time.sleep(1)


def _probe_listener(state, release):
    """Check the actual private-LAN TLS listener, host identity and app release.

    Connecting directly to the validated LAN IP avoids DNS/proxy redirection;
    SNI and certificate hostname validation still use the configured host. Only
    this process trusts the operator-provided certificate chain. No system trust
    store, certificate, server configuration or uploaded evidence is modified.
    """
    values = state['values']
    address = customer.validate_lan_address(values['ISURVIX_LAN_IP'])
    host = values['STAGING_HOST']
    if not isinstance(host, str) or not re.fullmatch(r'[A-Za-z0-9.-]{1,253}', host):
        raise ValueError('The private listener host is invalid.')
    certificate = customer._private_input(Path(values['ISURVIX_TLS_DIRECTORY'])/'fullchain.pem')
    try:
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_verify_locations(cafile=str(certificate))
        if hasattr(ssl, 'VERIFY_X509_PARTIAL_CHAIN'):
            context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
        with socket.create_connection((address, 8443), timeout=3) as raw:
            with context.wrap_socket(raw, server_hostname=host) as secured:
                secured.sendall(('GET /ops/health/ready/ HTTP/1.1\r\nHost: '+host+
                                 ':8443\r\nConnection: close\r\n\r\n').encode('ascii'))
                response = HTTPResponse(secured)
                response.begin()
                body = response.read(16385)
                if response.status != 200 or len(body) > 16384:
                    raise ValueError()
                value = json.loads(body)
                if not isinstance(value, dict) or value.get('status') != 'ready' or value.get('release') != release:
                    raise ValueError()
    except (OSError, HTTPException, ValueError, UnicodeError):
        raise ValueError('The private TLS listener did not confirm readiness for this exact release.') from None


def _proxy_health(package, runtime, state, release):
    """A healthy backend alone is not a reachable customer service."""
    for attempt in range(30):
        try:
            raw = customer._docker(*_compose(package, runtime, state), 'ps', '--all', '--format', 'json', 'proxy').decode('utf-8').strip()
            rows = json.loads(raw) if raw.startswith('[') else [json.loads(line) for line in raw.splitlines() if line]
            proxies = [row for row in rows if isinstance(row, dict) and row.get('Service') == 'proxy']
            if len(proxies) != 1 or proxies[0].get('State') != 'running' or proxies[0].get('Health') != 'healthy':
                raise ValueError('The proxy is absent, stopped or unhealthy.')
            _probe_listener(state, release)
            return
        except (ValueError, OSError, UnicodeError, TypeError):
            if attempt == 29:
                raise ValueError('The private proxy/TLS listener did not become ready within the bounded wait.') from None
            time.sleep(1)


def _receipt(transaction, state, secret, status, release, error_code='', *, acknowledge=None):
    payload = state['request']['payload']
    sequence = state['sequence']+1
    record = {'format': 'isurvix-update-receipt-v1', **{key: payload[key] for key in BINDINGS},
        'sequence': sequence, 'status': status, 'release_id': release,
        'error_code': error_code, 'at': int(time.time())}
    for key in ('backup_manifest_sha256', 'evidence_inventory_sha256'):
        if state.get(key):
            record[key] = state[key]
    signed = {'payload': record, 'signature': signature(secret, 'receipt-v1', record)}
    receipt = Path(state['paths']['update_directory'])/'receipts'/payload['request_id']/('%06d.json' % sequence)
    receipt.parent.mkdir(mode=0o755, exist_ok=True)
    if receipt.exists():
        raise ValueError('An unexpected receipt already occupies this immutable sequence; preserve it for recovery.')
    _atomic(receipt, signed)
    receipt.chmod(0o644)  # Contains version/digest/state only, never operator secrets.
    state['sequence'] = sequence
    state['last_status'] = status
    _atomic(transaction/'journal.json', state)
    if acknowledge is not None:
        package, runtime, runtime_state = acknowledge
        remote = '/run/isurvix-updates/receipts/'+payload['request_id']+'/'+receipt.name
        raw = _container(package, runtime, runtime_state, 'python', 'manage.py', 'update_bridge', 'receipt', '--receipt-file', remote)
        try:
            ack = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ValueError('The installed application did not acknowledge the signed update receipt.') from None
        if ack != {'request_id': payload['request_id'], 'status': status, 'sequence': sequence}:
            raise ValueError('The installed application rejected or advanced beyond this expected update phase.')
    return record


def _paths(**values):
    resolved = {name: customer._no_links(value) for name, value in values.items()}
    if any(any(char in str(path) for char in '\r\n\0$`\"') for path in resolved.values()):
        raise ValueError('Use directive-safe operator update paths.')
    # Target/journal/update spool must never be part of source data, package
    # bytes or each other; rolling back the DB cannot roll back host authority.
    keys = ('installed_package', 'installed_runtime', 'update_directory', 'packages_root', 'target_runtime', 'journal_root')
    for index, first in enumerate(keys):
        for second in keys[index+1:]:
            if (first, second) == ('installed_package', 'packages_root'):
                relative = resolved[first].relative_to(resolved[second]) if resolved[first].is_relative_to(resolved[second]) else None
                if relative is not None and len(relative.parts) == 2 and re.fullmatch('[a-f0-9]{40}', relative.parts[0]) and relative.parts[1] == 'package':
                    continue  # A completed previous target is the next source.
            if resolved[first].is_relative_to(resolved[second]) or resolved[second].is_relative_to(resolved[first]):
                raise ValueError('Package, source, target, update spool and journal roots must be separate non-overlapping directories.')
    return resolved


def _result(state, status, release, error_code=''):
    return {'request_id': state['request']['payload']['request_id'], 'status': status,
        'release_id': release, 'error_code': error_code, 'source_preserved': True,
        'target_runtime': state['paths']['target_runtime'], 'journal': state['paths']['journal_root'],
        'automatic_downloads': 0, 'owner_release_approved': False}


def _retained_runtime(package, runtime, release, *, initialized=False):
    manifest, state = customer._runtime(package, runtime)
    if manifest['release_id'] != release:
        raise ValueError('Retained runtime/package identity differs from the historical update.')
    database = customer._no_links(Path(runtime)/'data/database.sqlite3')
    if not database.is_file() or not stat.S_ISREG(database.stat().st_mode):
        raise ValueError('The historical runtime database is no longer retained.')
    for name in ('media', 'static', 'upload-tmp'):
        if not customer._no_links(Path(runtime)/'data'/name).is_dir():
            raise ValueError('The historical runtime data directories are no longer retained.')
    proof = {'manifest': customer._digest(Path(package)/'manifest.json'),
             'install': customer._digest(Path(runtime)/'install.json'),
             'env': customer._digest(Path(runtime)/'customer.env'),
             'nginx': customer._digest(Path(runtime)/'nginx.conf')}
    initialized_file = Path(runtime)/'initialized.json'
    if initialized or initialized_file.exists():
        if _read(initialized_file).get('release_id') != release:
            raise ValueError('The retained initialization identity is invalid.')
        proof['initialized'] = customer._digest(initialized_file)
    return proof, state


def _terminal_receipts(state, paths, secret, payload):
    sequence = state.get('sequence')
    if type(sequence) is not int or not 1 <= sequence <= 1000:
        raise ValueError('The historical receipt sequence is invalid.')
    root = customer._no_links(paths['update_directory']/'receipts'/payload['request_id'])
    expected = {'%06d.json' % index for index in range(1, sequence+1)}
    if not root.is_dir() or {path.name for path in root.iterdir()} != expected:
        raise ValueError('The historical receipt chain is incomplete or inconsistent.')
    transitions = {'pending': {'verified'}, 'verified': {'verified', 'applying', 'failed'},
                   'applying': {'applying', 'failed', 'completed', 'rolled_back'},
                   'failed': {'rolled_back'}, 'completed': set(), 'rolled_back': set()}
    required = {'format', *BINDINGS, 'sequence', 'status', 'release_id', 'error_code', 'at'}
    optional = {'backup_manifest_sha256', 'evidence_inventory_sha256'}
    current, last, hashes = 'pending', None, {}
    for index in range(1, sequence+1):
        name = '%06d.json' % index
        signed = _read(root/name, 16384)
        if not isinstance(signed, dict) or set(signed) != {'payload', 'signature'}:
            raise ValueError('The historical receipt wrapper is invalid.')
        value = signed['payload']
        if (not isinstance(value, dict) or not required <= set(value) or set(value)-required-optional or
                value['format'] != 'isurvix-update-receipt-v1' or value['sequence'] != index or
                any(value[key] != payload[key] for key in BINDINGS) or
                not isinstance(signed['signature'], str) or
                not hmac.compare_digest(signature(secret, 'receipt-v1', value), signed['signature'])):
            raise ValueError('The historical receipt HMAC or request binding is invalid.')
        if (value['status'] not in transitions.get(current, set()) or
                value['release_id'] not in (payload['source_release'], payload['target_release'])):
            raise ValueError('The historical receipt state is invalid.')
        for key in optional & set(value):
            if value[key] != state.get(key) or not re.fullmatch('[a-f0-9]{64}', str(value[key])):
                raise ValueError('Historical backup/evidence receipt identities changed.')
        current, last = value['status'], value
        hashes[name] = customer._digest(root/name)
    if current != state.get('last_status'):
        raise ValueError('The historical terminal status differs from its receipt chain.')
    return last, hashes


def _terminal_record(transaction, state, paths, request_id, secret):
    """Derive immutable historical proof without reading mutable human rows.

    Current DB/media contents and server uptime are deliberately excluded. The
    original verified backup and signed immutable proof remain the historical
    basis after legitimate later user writes or subsequent upgrades.
    """
    if (state.get('format') != 'isurvix-host-update-journal-v1' or
            state.get('paths') != {key: str(value) for key, value in paths.items()} or
            state.get('phase') not in TERMINAL):
        raise ValueError('The terminal journal format, paths or phase is invalid.')
    payload = verify_request(state.get('request'), secret, request_id, check_expiry=False)
    phase = state['phase']
    result = state.get('result')
    if not isinstance(result, dict):
        raise ValueError('The terminal result is unavailable.')
    release = payload['target_release'] if phase == 'completed' else payload['source_release']
    error_code = '' if phase == 'completed' else ('cancelled' if phase == 'cancelled' else result.get('error_code'))
    if (phase == 'rolled_back' and error_code not in {'backup_failed', 'migration_failed', 'health_failed', 'interrupted'} or
            result != _result(state, phase, release, error_code)):
        raise ValueError('The terminal result does not match the signed request and actual phase.')
    source, _ = _retained_runtime(paths['installed_package'], paths['installed_runtime'],
                                  payload['source_release'], initialized=True)
    last, receipts = _terminal_receipts(state, paths, secret, payload)
    if phase == 'cancelled':
        if state['sequence'] != 1 or last['status'] != 'verified':
            raise ValueError('The terminal cancellation receipt sequence is invalid.')
        expected = {key: payload[key] for key in BINDINGS}
        expected.update(status='failed', error_code='cancelled', last_sequence=1)
        if _read(transaction/'cancellation-proof.json') != expected:
            raise ValueError('The retained cancellation proof differs from this request.')
    elif (last['status'] != phase or last['release_id'] != release or last['error_code'] != error_code):
        raise ValueError('The terminal result differs from its last signed receipt.')
    artifacts = {}
    for name in ('backup/manifest.json', 'retained-records.json', 'retention-proof.json', 'cancellation-proof.json'):
        path = customer._no_links(transaction/name)
        if path.exists():
            artifacts[name] = customer._digest(path)
    if phase == 'completed':
        required = {'backup/manifest.json', 'retained-records.json', 'retention-proof.json'}
        if not required <= set(artifacts) or not {'backup_manifest_sha256', 'evidence_inventory_sha256'} <= set(last):
            raise ValueError('Historical completion lacks backup/retention evidence.')
    if state.get('backup_manifest_sha256'):
        backup = _module(paths['installed_package']/'release/backend/core/operations_backup.py', 'retained_update_backup')
        manifest = backup.validate_backup(transaction/'backup')
        evidence = {key: value for key, value in manifest['files'].items() if key.startswith('media/')}
        if (manifest['release_id'] != payload['source_release'] or
                customer._digest(transaction/'backup/manifest.json')['sha256'] != state['backup_manifest_sha256'] or
                hashlib.sha256(canonical(evidence)).hexdigest() != state.get('evidence_inventory_sha256')):
            raise ValueError('Historical backup integrity differs from the signed receipt.')
    target = None
    if phase == 'completed':
        candidate = paths['packages_root']/payload['target_release']/'package'
        manifest = customer.verify_package(candidate, expected_manifest_sha256=payload['manifest_sha256'])
        if manifest['release_id'] != payload['target_release']:
            raise ValueError('The retained candidate package belongs to another release.')
        target, _ = _retained_runtime(candidate, paths['target_runtime'], payload['target_release'], initialized=True)
    return {'format': 'isurvix-host-terminal-proof-v1', 'request_id': request_id,
        'phase': phase, 'request_sha256': hashlib.sha256(canonical(state['request'])).hexdigest(),
        'paths_sha256': hashlib.sha256(canonical(state['paths'])).hexdigest(),
        'result_sha256': hashlib.sha256(canonical(result)).hexdigest(),
        'sequence': state['sequence'], 'last_status': state['last_status'],
        'source': source, 'target': target, 'receipts': receipts, 'artifacts': artifacts}


def _finish_terminal(transaction, state, secret, phase):
    paths = {name: Path(value) for name, value in state['paths'].items()}
    terminal = {**state, 'phase': phase}
    record = _terminal_record(transaction, terminal, paths, state['request']['payload']['request_id'], secret)
    proof = transaction/'terminal-proof.json'
    if proof.exists():
        raise ValueError('An immutable terminal proof already exists; preserve it for reconciliation.')
    _atomic(proof, {'payload': record, 'signature': signature(secret, 'host-terminal-v1', record)})
    _phase(transaction, state, phase)


def _terminal_replay(transaction, state, paths, request_id):
    # Validate source static identity and recover its original external signing
    # key before accepting even a no-op historical success. No Docker is called.
    _, source_state = customer._runtime(paths['installed_package'], paths['installed_runtime'])
    secret = customer._private_input(source_state['values']['ISURVIX_SECRET_FILE']).read_text(encoding='utf-8').strip()
    expected = _terminal_record(transaction, state, paths, request_id, secret)
    proof = _read(transaction/'terminal-proof.json', 524288)
    if (not isinstance(proof, dict) or set(proof) != {'payload', 'signature'} or
            proof['payload'] != expected or not isinstance(proof['signature'], str) or
            not hmac.compare_digest(signature(secret, 'host-terminal-v1', expected), proof['signature'])):
        raise ValueError('The terminal historical proof is missing, corrupt or belongs to another request.')
    return state['result']


def _phase(transaction, state, phase):
    state['phase'] = phase
    _atomic(transaction/'journal.json', state)


def _stopped(package, runtime, runtime_state):
    base = _compose(package, runtime, runtime_state)
    customer._docker(*base, 'stop')
    raw = customer._docker(*base, 'ps', '--all', '--format', 'json').decode('utf-8').strip()
    try:
        rows = json.loads(raw) if raw.startswith('[') else [json.loads(line) for line in raw.splitlines() if line]
        if not isinstance(rows, list) or any(row.get('State') not in ('exited', 'stopped', 'dead', 'created') for row in rows):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Not every managed web/worker writer is stopped; no backup was declared quiescent.') from None


def apply_update(*, installed_package, installed_runtime, update_directory, packages_root,
                 target_runtime, journal_root, request_id, acknowledge_draft=False,
                 maintenance_confirmed=False):
    customer._draft(acknowledge_draft)
    _uuid(request_id)
    if maintenance_confirmed is not True:
        raise ValueError('Confirm the maintenance window and stop all external writers before applying.')
    paths = _paths(installed_package=installed_package, installed_runtime=installed_runtime,
        update_directory=update_directory, packages_root=packages_root, target_runtime=target_runtime,
        journal_root=journal_root)
    source_package, source_runtime = paths['installed_package'], paths['installed_runtime']
    transaction = paths['journal_root']/request_id
    with _lock(paths['journal_root']):
        for other in paths['journal_root'].iterdir():
            if not other.is_dir() or other.name == request_id:
                continue
            customer._no_links(other)
            if (other/'journal.json').exists():
                if _read(other/'journal.json', 262144).get('phase') not in TERMINAL:
                    raise ValueError('Another interrupted transaction requires recovery before a new request can run.')
        if transaction.exists():
            previous = _read(transaction/'journal.json', 262144)
            if previous.get('paths') != {key: str(value) for key, value in paths.items()}:
                raise ValueError('This request already belongs to other immutable operator inputs.')
            if previous.get('phase') in TERMINAL and isinstance(previous.get('result'), dict):
                return _terminal_replay(transaction, previous, paths, request_id)
            raise ValueError('An interrupted update requires explicit operator recovery; preserve both runtimes and the independent journal.')
        source_manifest, source_state = customer._runtime(source_package, source_runtime)
        if source_state['values'].get('ISURVIX_UPDATE_DIRECTORY') != paths['update_directory'].as_posix():
            raise ValueError('The installed runtime must have this exact read-only catalog/receipt bridge configured.')
        if paths['target_runtime'].exists() or not paths['target_runtime'].parent.is_dir():
            raise ValueError('Use a NEW target runtime; existing and partial data is never overwritten.')
        secret = customer._private_input(source_state['values']['ISURVIX_SECRET_FILE']).read_text(encoding='utf-8').strip()
        raw = _container(source_package, source_runtime, source_state, 'python', 'manage.py', 'update_bridge', 'export', request_id)
        if len(raw) > 16384:
            raise ValueError('The installed bridge returned an oversized request.')
        try:
            signed = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ValueError('The installed bridge did not return a signed update request.') from None
        payload = verify_request(signed, secret, request_id)
        if payload['source_release'] != source_manifest['release_id']:
            raise ValueError('The installed source release changed; no candidate was executed.')
        _catalog(paths['update_directory'], payload)
        candidate, target_manifest = _package(paths['packages_root'], payload)
        # Load only the integrity-checked local archive. No image pull/network
        # fetch is attempted, even when a digest is missing from the daemon.
        customer.load_images(candidate, acknowledge_draft=True)
        # Loading a large offline archive can outlive the original short TTL.
        # Obtain current authority again, keeping every immutable binding fixed.
        fresh_raw = _container(source_package, source_runtime, source_state, 'python', 'manage.py', 'update_bridge', 'export', request_id)
        if len(fresh_raw) > 16384:
            raise ValueError('The installed bridge returned an oversized request.')
        fresh_signed = json.loads(fresh_raw)
        fresh_payload = verify_request(fresh_signed, secret, request_id)
        fixed = REQUEST_FIELDS-{'issued_at', 'expires_at'}
        if any(fresh_payload[key] != payload[key] for key in fixed):
            raise ValueError('The update authority changed while verifying the offline artifact.')
        signed, payload = fresh_signed, fresh_payload
        _catalog(paths['update_directory'], payload)
        transaction.mkdir(mode=0o700)
        state = {'format': 'isurvix-host-update-journal-v1', 'request': signed, 'phase': 'verified-package',
            'paths': {key: str(value) for key, value in paths.items()}, 'sequence': 0, 'last_status': ''}
        _atomic(transaction/'journal.json', state)
        # Both acknowledgements must complete before stopping any writer. In
        # particular an owner withdrawal racing with export safely fails here.
        _receipt(transaction, state, secret, 'verified', payload['source_release'],
                 acknowledge=(source_package, source_runtime, source_state))
        _receipt(transaction, state, secret, 'applying', payload['source_release'],
                 acknowledge=(source_package, source_runtime, source_state))
        _phase(transaction, state, 'stopping-writers')
        candidate_state = None
        error_code = 'backup_failed'
        try:
            _stopped(source_package, source_runtime, source_state)
            _phase(transaction, state, 'backing-up')
            backup_helper = _module(source_package/'release/backend/core/operations_backup.py', 'installed_backup')
            backup = transaction/'backup'
            backup_helper.create_backup(source_runtime/'data/database.sqlite3', source_runtime/'data/media',
                backup, release_id=payload['source_release'], quiesced=True)
            backup_manifest = backup_helper.validate_backup(backup)
            state['backup_manifest_sha256'] = customer._digest(backup/'manifest.json')['sha256']
            evidence = {key: value for key, value in backup_manifest['files'].items() if key.startswith('media/')}
            state['evidence_inventory_sha256'] = hashlib.sha256(canonical(evidence)).hexdigest()
            retention = _module(source_package/'release/deploy/customer/upgrade_fixture.py', 'installed_retention')
            before = retention.snapshot(backup/'database.sqlite3')
            _atomic(transaction/'retained-records.json', before)
            error_code = 'migration_failed'
            _phase(transaction, state, 'restoring')
            options = {'host': source_state['values']['STAGING_HOST'],
                'lan_ip': source_state['values']['ISURVIX_LAN_IP'],
                'secret_file': source_state['values']['ISURVIX_SECRET_FILE'],
                'tls_directory': source_state['values']['ISURVIX_TLS_DIRECTORY'],
                'restore_backup': backup, 'acknowledge_draft': True}
            options['update_directory'] = paths['update_directory']
            customer.prepare_runtime(candidate, paths['target_runtime'], **options)
            _phase(transaction, state, 'migrating')
            customer.run_action(candidate, paths['target_runtime'], 'migrate-restored', acknowledge_draft=True)
            _, candidate_state = customer._runtime(candidate, paths['target_runtime'])
            # The original DB and its backup remain intact. Migrations run only
            # against this copied target, and retained human rows/evidence must
            # still match before any candidate listener is exposed.
            proof = retention.assert_retained(before, paths['target_runtime']/'data/database.sqlite3')
            _atomic(transaction/'retention-proof.json', proof)
            actual_media = customer._files(paths['target_runtime']/'data/media')
            if {'media/'+key: customer._digest(value) for key, value in actual_media.items()} != evidence:
                raise ValueError('Candidate evidence changed during migration; activation is blocked.')
            failpoint = os.environ.get('ISURVIX_UPDATER_TEST_FAILPOINT', '')
            if failpoint:
                if os.environ.get('ISURVIX_DISPOSABLE_REHEARSAL') != 'yes' or failpoint not in ('after-migrate', 'interrupt-after-migrate'):
                    raise ValueError('Test failpoints are available only in the explicit disposable rehearsal.')
                if failpoint == 'interrupt-after-migrate':
                    raise KeyboardInterrupt('Disposable process interruption; preserve the journal and run explicit recovery.')
                raise ValueError('Disposable rehearsal stopped after migration, before activation.')
            error_code = 'health_failed'
            _phase(transaction, state, 'checking-candidate')
            customer._docker(*_compose(candidate, paths['target_runtime'], candidate_state),
                             'up', '-d', '--no-deps', '--pull', 'never', '--no-build', 'web')
            _health(candidate, paths['target_runtime'], candidate_state, payload['target_release'])
            # Persist BEFORE attempting proxy startup. A process kill/timeout
            # can occur after the listener accepted writes: never auto-rollback
            # or discard target data after this durable boundary.
            _phase(transaction, state, 'activation_started')
            customer._docker(*_compose(candidate, paths['target_runtime'], candidate_state),
                             'up', '-d', '--pull', 'never', '--no-build', 'proxy')
            _health(candidate, paths['target_runtime'], candidate_state, payload['target_release'])
            _proxy_health(candidate, paths['target_runtime'], candidate_state, payload['target_release'])
            # The backup was taken after applying2 ACK. Candidate DB contains
            # that sequence/nonce, so completed3 cannot skip status history.
            _receipt(transaction, state, secret, 'completed', payload['target_release'],
                     acknowledge=(candidate, paths['target_runtime'], candidate_state))
            state['result'] = _result(state, 'completed', payload['target_release'])
            _finish_terminal(transaction, state, secret, 'completed')
            return state['result']
        except (ValueError, OSError, KeyError, UnicodeError):
            if state['phase'] == 'activation_started':
                # Target may now contain writes. Do not restart the old proxy.
                state['result'] = _result(state, 'failed', payload['target_release'], 'activation_uncertain')
                _phase(transaction, state, 'activation_uncertain')
                if state.get('last_status') != 'completed':
                    _receipt(transaction, state, secret, 'failed', payload['target_release'], 'activation_uncertain')
                return state['result']
            # Every failed/partial candidate is retained, never overwritten or
            # deleted. Only the pre-activation path may restart the old source.
            if paths['target_runtime'].exists():
                try:
                    if candidate_state is None:
                        _, candidate_state = customer._runtime(candidate, paths['target_runtime'])
                    _stopped(candidate, paths['target_runtime'], candidate_state)
                except (ValueError, OSError, KeyError):
                    state['result'] = _result(state, 'failed', payload['source_release'], 'recovery_required')
                    _phase(transaction, state, 'recovery_required')
                    _receipt(transaction, state, secret, 'failed', payload['source_release'], 'recovery_required')
                    return state['result']
            try:
                customer.run_action(source_package, source_runtime, 'start', acknowledge_draft=True)
                _health(source_package, source_runtime, source_state, payload['source_release'])
                _proxy_health(source_package, source_runtime, source_state, payload['source_release'])
            except (ValueError, OSError, KeyError, UnicodeError):
                state['result'] = _result(state, 'failed', payload['source_release'], 'recovery_required')
                _phase(transaction, state, 'recovery_required')
                _receipt(transaction, state, secret, 'failed', payload['source_release'], 'recovery_required',
                         acknowledge=(source_package, source_runtime, source_state))
                return state['result']
            _receipt(transaction, state, secret, 'failed', payload['source_release'], error_code,
                     acknowledge=(source_package, source_runtime, source_state))
            _receipt(transaction, state, secret, 'rolled_back', payload['source_release'], error_code,
                     acknowledge=(source_package, source_runtime, source_state))
            state['result'] = _result(state, 'rolled_back', payload['source_release'], error_code)
            _finish_terminal(transaction, state, secret, 'rolled_back')
            return state['result']


def recover_update(*, installed_package, installed_runtime, update_directory, packages_root,
                   target_runtime, journal_root, request_id, acknowledge_draft=False,
                   maintenance_confirmed=False):
    """Explicitly recover a transaction that never began listener activation.

    Post-activation recovery is deliberately refused: a human must first
    reconcile possible new writes and select the authoritative runtime.
    """
    customer._draft(acknowledge_draft)
    _uuid(request_id)
    if maintenance_confirmed is not True:
        raise ValueError('Confirm the maintenance window and external writers before recovery.')
    paths = _paths(installed_package=installed_package, installed_runtime=installed_runtime,
        update_directory=update_directory, packages_root=packages_root, target_runtime=target_runtime,
        journal_root=journal_root)
    transaction = paths['journal_root']/request_id
    with _lock(paths['journal_root']):
        state = _read(transaction/'journal.json', 262144)
        if (state.get('format') != 'isurvix-host-update-journal-v1' or
                state.get('paths') != {key: str(value) for key, value in paths.items()}):
            raise ValueError('The independent recovery journal belongs to different operator inputs.')
        if state.get('phase') in TERMINAL and isinstance(state.get('result'), dict):
            return _terminal_replay(transaction, state, paths, request_id)
        if state.get('phase') in ('activation_started', 'activation_uncertain'):
            raise ValueError('Possible activation writes require explicit data reconciliation; automatic rollback is refused.')
        if state.get('phase') not in {'verified-package', 'stopping-writers', 'backing-up', 'restoring', 'migrating', 'checking-candidate', 'recovery_required'}:
            raise ValueError('This journal phase needs manual receipt/authority reconciliation before recovery.')
        source_package, source_runtime = paths['installed_package'], paths['installed_runtime']
        source_manifest, source_state = customer._runtime(source_package, source_runtime)
        secret = customer._private_input(source_state['values']['ISURVIX_SECRET_FILE']).read_text(encoding='utf-8').strip()
        payload = verify_request(state['request'], secret, request_id, check_expiry=False)
        if payload['source_release'] != source_manifest['release_id']:
            raise ValueError('The preserved source differs from the independent journal.')
        if state['phase'] == 'verified-package':
            # Withdrawal can occupy application sequence1 after host export but
            # before verified1 ACK. No writer-stop phase has been entered. The
            # conflicting host receipt is retained; no replacement or invented
            # completed/rolled-back application event is produced.
            if state.get('sequence') != 1 or state.get('last_status') != 'verified' or paths['target_runtime'].exists():
                raise ValueError('Pre-ACK recovery requires an exact untouched cancellation; other authority states need reconciliation.')
            proof = _cancelled_request(source_package, source_runtime, source_state, payload)
            _health(source_package, source_runtime, source_state, payload['source_release'])
            _proxy_health(source_package, source_runtime, source_state, payload['source_release'])
            _atomic(transaction/'cancellation-proof.json', proof)
            state['result'] = _result(state, 'cancelled', payload['source_release'], 'cancelled')
            _finish_terminal(transaction, state, secret, 'cancelled')
            return state['result']
        if paths['target_runtime'].exists():
            candidate, _ = _package(paths['packages_root'], payload)
            _, candidate_state = customer._runtime(candidate, paths['target_runtime'])
            _stopped(candidate, paths['target_runtime'], candidate_state)
        customer.run_action(source_package, source_runtime, 'start', acknowledge_draft=True)
        _health(source_package, source_runtime, source_state, payload['source_release'])
        _proxy_health(source_package, source_runtime, source_state, payload['source_release'])
        # Replay every immutable receipt in order. The backend may already be
        # ahead of an earlier replay, but only a matching later journaled state
        # is accepted; a withdrawal/cancelled event cannot silently authorize it.
        receipt_root = paths['update_directory']/'receipts'/request_id
        for sequence in range(1, state['sequence']+1):
            prior = _read(receipt_root/('%06d.json' % sequence), 16384)
            prior_payload = prior.get('payload', {})
            if (prior_payload.get('sequence') != sequence or
                    any(prior_payload.get(key) != payload[key] for key in BINDINGS) or
                    not hmac.compare_digest(signature(secret, 'receipt-v1', prior_payload), prior.get('signature', ''))):
                raise ValueError('The recovery receipt chain does not match the independent journal.')
            remote = '/run/isurvix-updates/receipts/'+request_id+('/%06d.json' % sequence)
            raw = _container(source_package, source_runtime, source_state, 'python', 'manage.py',
                             'update_bridge', 'receipt', '--receipt-file', remote)
            ack = json.loads(raw)
            actual_sequence = ack.get('sequence')
            if (ack.get('request_id') != request_id or type(actual_sequence) is not int or
                    not sequence <= actual_sequence <= state['sequence']):
                raise ValueError('Recovery receipt reconciliation did not reach a journaled state.')
            latest = _read(receipt_root/('%06d.json' % actual_sequence), 16384)['payload']
            if ack.get('status') != latest['status']:
                raise ValueError('The application state differs from the independent recovery receipt chain.')
        if state.get('last_status') != 'failed':
            _receipt(transaction, state, secret, 'failed', payload['source_release'], 'interrupted',
                     acknowledge=(source_package, source_runtime, source_state))
        _receipt(transaction, state, secret, 'rolled_back', payload['source_release'], 'interrupted',
                 acknowledge=(source_package, source_runtime, source_state))
        state['result'] = _result(state, 'rolled_back', payload['source_release'], 'interrupted')
        _finish_terminal(transaction, state, secret, 'rolled_back')
        return state['result']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['apply', 'recover'])
    for name in ('installed-package', 'installed-runtime', 'update-directory', 'packages-root',
                 'target-runtime', 'journal-root'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--request-id', required=True)
    parser.add_argument('--acknowledge-draft', action='store_true')
    parser.add_argument('--maintenance-confirmed', action='store_true')
    args = parser.parse_args(argv)
    try:
        operation = apply_update if args.action == 'apply' else recover_update
        result = operation(**{key: value for key, value in vars(args).items() if key != 'action'})
        print(json.dumps(result, sort_keys=True))
        return 0 if result['status'] == 'completed' else 2
    except (ValueError, OSError, KeyError, UnicodeError):
        # Never echo container output, source data, filenames or secret bytes.
        parser.exit(2, 'The host update stopped. Preserve both runtimes and the independent journal; inspect the saved phase and trusted operator inputs.\n')


if __name__ == '__main__':
    sys.exit(main())
