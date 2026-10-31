"""Explicit customer-server bundle preparation and offline install operations.

This stdlib-only helper never pulls an image, installs a package, downloads a
model, creates a certificate or approves a release. Run only trusted packages.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import types
from zipfile import ZipFile


FORMAT = 'isurvix-customer-bundle-v1'
HOLD_IDS = ['A12', 'BR1', 'D1', 'D2', 'L1', 'CS1', 'CS2', 'AI1', 'UP1']
REPAIRED_FINDINGS = ['CP1', 'CP2']
REQUIRED_FILES = {'release/RELEASE', 'release/deploy/staging.py',
    'release/deploy/nginx.conf.template', 'release/deploy/customer/customer.py',
    'release/deploy/customer/compose.yaml', 'release/backend/core/operations_backup.py',
    'images/server-images.tar'}
LICENSE_SCRIPT = """import importlib.metadata as m,json
print(json.dumps([{'name':d.metadata.get('Name'),'version':d.version,
'license_expression':d.metadata.get('License-Expression') or 'NOASSERTION',
'license_metadata':d.metadata.get('License') or 'NOASSERTION',
'license_classifiers':[c for c in d.metadata.get_all('Classifier',[]) if c.startswith('License ::')],
'license_files':[str(p) for p in (d.files or []) if any(t in str(p).lower() for t in ('license','copying','notice'))]}
for d in m.distributions()],sort_keys=True))"""


def _json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate manifest/configuration keys are not supported.')
            result[key] = value
        return result
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('The package or runtime manifest cannot be read.') from None


def _no_links(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
            raise ValueError('Package and runtime paths must not contain symbolic links or junctions.')
    return path


def _digest(path):
    h = hashlib.sha256()
    size = 0
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024*1024):
            h.update(chunk)
            size += len(chunk)
    return {'size': size, 'sha256': h.hexdigest()}


def _files(root):
    root = _no_links(root)
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            _no_links(Path(directory)/name)
        for name in files:
            path = _no_links(Path(directory)/name)
            if not stat.S_ISREG(path.stat().st_mode):
                raise ValueError('The package accepts regular files only.')
            result[path.relative_to(root).as_posix()] = path
    return result


def _relative(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('Invalid package inventory filename.')
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(part in ('', '.', '..') or ':' in part for part in path.parts):
        raise ValueError('Invalid package inventory filename.')
    return value


def _image(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[A-Za-z0-9./:_-]+@)?sha256:[0-9a-f]{64}', value):
        raise ValueError('Use an inspected immutable Docker image identity.')
    return value


def validate_lan_address(value):
    if not isinstance(value, str) or value != value.strip():
        raise ValueError('Supply one explicit RFC1918 IPv4 server address.')
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError:
        raise ValueError('Supply one explicit RFC1918 IPv4 server address.') from None
    if not any(address in ipaddress.IPv4Network(network) for network in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
        raise ValueError('Only an explicit RFC1918 LAN listener is supported; wildcard/public/loopback addresses are refused.')
    return str(address)


def _local_docker_context():
    # An inherited remote context must not turn package inspection/testing into
    # operations on an unrelated customer or production daemon.
    if os.environ.get('DOCKER_HOST') and not os.environ['DOCKER_HOST'].startswith('unix://'):
        raise ValueError('Use an explicitly local Linux Docker Unix-socket context; remote daemons are refused.')
    try:
        context = subprocess.run(['docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}'], capture_output=True, check=False)
        if context.returncode or not context.stdout.decode('utf-8').strip().startswith('unix://'):
            raise ValueError('Use an explicitly local Linux Docker Unix-socket context; remote daemons are refused.')
    except OSError:
        raise ValueError('Docker is unavailable. Install the approved Linux Docker/Compose prerequisites separately.') from None


def _docker(*args):
    _local_docker_context()
    try:
        result = subprocess.run(['docker', *map(str, args)], capture_output=True, check=False)
    except OSError:
        raise ValueError('Docker is unavailable. Install the approved Linux Docker/Compose prerequisites separately.') from None
    if result.returncode:
        raise ValueError('The requested local Docker operation failed. Check the private operator/container logs; no image was automatically downloaded.')
    return result.stdout


def _inspect(reference):
    rows = json.loads(_docker('image', 'inspect', _image(reference)))
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError('The local Docker image identity cannot be verified.')
    row = rows[0]
    if row.get('Os') != 'linux' or row.get('Architecture') != 'amd64':
        raise ValueError('This candidate supports inspected linux/amd64 images only.')
    return _image(row.get('Id'))


def _shared(package):
    path = Path(package)/'release/deploy/staging.py'
    # Loading an immutable bundle must not create __pycache__ inside it.
    result = types.ModuleType('customer_shared_staging')
    result.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), result.__dict__)
    return result


def verify_package(package, *, expected_manifest_sha256=None):
    root = _no_links(package)
    manifest_path = root/'manifest.json'
    if not root.is_dir() or (root/'INCOMPLETE').exists():
        raise ValueError('Use a complete trusted package directory.')
    if expected_manifest_sha256 is not None:
        if not re.fullmatch(r'[0-9a-f]{64}', str(expected_manifest_sha256)) or _digest(manifest_path)['sha256'] != expected_manifest_sha256:
            raise ValueError('The manifest differs from its independently trusted digest.')
    manifest = _json(manifest_path)
    if (not isinstance(manifest, dict) or manifest.get('format') != FORMAT or
            manifest.get('status') != 'draft-for-review' or manifest.get('owner_release_approved') is not False or
            not re.fullmatch(r'[0-9a-f]{40}', str(manifest.get('release_id', ''))) or
            manifest.get('target') != {'os': 'linux', 'architecture': 'amd64'}):
        raise ValueError('The package manifest/release format is unsupported or misleading.')
    images = manifest.get('images', {})
    if not isinstance(images, dict) or set(images) != {'app', 'nginx'}:
        raise ValueError('The package must identify the exact application and proxy images.')
    for value in images.values():
        _image(value)
    expected = manifest.get('files')
    if not isinstance(expected, dict):
        raise ValueError('The package inventory is missing.')
    if not REQUIRED_FILES <= set(expected):
        raise ValueError('The package lacks required shared release/installer/image files.')
    for name, proof in expected.items():
        _relative(name)
        if name == 'manifest.json' or not isinstance(proof, dict) or set(proof) != {'size', 'sha256'}:
            raise ValueError('The package inventory is invalid.')
        if type(proof['size']) is not int or proof['size'] < 0 or not isinstance(proof['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', proof['sha256']):
            raise ValueError('The package inventory digest/size is invalid.')
    actual = _files(root)
    actual.pop('manifest.json', None)
    if set(actual) != set(expected):
        raise ValueError('The package contains missing or unexpected files.')
    if any(_digest(path) != expected[name] for name, path in actual.items()):
        raise ValueError('The package failed content-integrity verification.')
    if (root/'release/RELEASE').read_text(encoding='ascii').strip() != manifest['release_id']:
        raise ValueError('The source release and image manifest do not agree.')
    return manifest


def _credential_key(value):
    key = str(value).upper().replace('-', '_').replace('.', '_')
    if key.endswith(('_FILE', '_PATH', '_ENV', '_REF', '_REFERENCE')):
        return False
    return key in {'PASSWORD', 'PASSWD', 'PWD', 'SECRET', 'TOKEN', 'API_KEY', 'PRIVATE_KEY',
        'ACCESS_TOKEN', 'REFRESH_TOKEN', 'CLIENT_SECRET', 'DJANGO_SECRET_KEY'} or key.endswith(
        ('_PASSWORD', '_PASSWD', '_TOKEN', '_SECRET', '_API_KEY', '_PRIVATE_KEY', '_ACCESS_KEY'))


def _literal_credential(value):
    if value is None or isinstance(value, bool):
        return False
    if not isinstance(value, str):
        return isinstance(value, (int, float))
    value = value.strip().strip('\"\'').strip()
    if not value or value.upper() in {'CHANGEME', 'CHANGE_ME', 'REPLACE_ME', 'REDACTED', 'NOT_CONFIGURED', 'UNAVAILABLE', 'NONE', 'NULL'}:
        return False
    if (value.startswith('${') and value.endswith('}')) or (value.startswith('<') and value.endswith('>')):
        return False
    return True


def _json_credentials(value):
    if isinstance(value, dict):
        return any(_credential_assignment(key, item) or _json_credentials(item)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(_json_credentials(item) for item in value)
    return False


def _credential_assignment(key, value):
    if str(key).casefold() == 'authorization':
        # Historical workflow receipts use this label for human approval text;
        # an actual HTTP credential header has a controlled scheme prefix.
        if not isinstance(value, str):
            return False
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '\"\'':
            if value[0] == '\"':
                try:
                    value = json.loads(value)
                except ValueError:
                    value = value[1:-1]
            else:
                value = value[1:-1].replace("''", "'")
        return bool(re.match(r'(?i)^\s*(?:bearer|basic|token)\s+\S+', value))
    return _credential_key(key) and _literal_credential(value)


def _configuration_credentials(text, *, template=False, yaml=False):
    if yaml:
        # Treat YAML literal/folded scalar bodies as strings rather than mapping
        # fields. Workflows legitimately contain Python/shell test code in run:|.
        # Credential-named scalar headers themselves are still checked below.
        lines = []
        block_indent = None
        for line in text.splitlines():
            indent = len(line) - len(line.lstrip(' \t'))
            if block_indent is not None:
                if not line.strip() or indent > block_indent:
                    continue
                block_indent = None
            lines.append(line)
            if re.match(r'^\s*(?:-\s+)?[^:#]+:\s*[|>][0-9+-]*\s*(?:#.*)?$', line):
                block_indent = indent
        text = '\n'.join(lines)
    # Recognize mapping/assignment boundaries in the restricted data syntax,
    # including nested YAML flow and TOML inline tables. Quoted scalar values
    # are consumed whole, so example text containing "{password:...}" is not a
    # second mapping. No YAML tag, constructor, alias or Python code is executed.
    quoted = r'''(?:"(?:\\.|[^"\\])*"|'(?:''|[^'])*')'''
    triple = r'''(?:"""[\s\S]*?"""|\x27\x27\x27[\s\S]*?\x27\x27\x27)'''
    reference = r'\$\{(?:[^{}]|\{[^{}]*\})*\}'
    value = '(?:'+triple+'|'+quoted+'|'+reference+r'|[^,{}\[\]\r\n#]*)'
    expression = (r'(?P<assignment>(?:^[ \t]*(?:-[ \t]+)?|[,{][ \t]*)(?:export[ \t]+)?'
        r'(?P<key>["\x27]?[A-Za-z_][A-Za-z0-9_.-]*["\x27]?)[ \t]*[:=][ \t]*'
        '(?P<value>'+value+'))|(?:'+triple+'|'+quoted+')')
    for match in re.finditer(expression, text, re.MULTILINE):
        if match.group('assignment') is None:
            continue
        key = match.group('key').strip('\"\'')
        raw_value = match.group('value')
        value = raw_value.strip().strip('\"\'')
        if template and value.lower().startswith(('replace_', 'replace-')) and re.fullmatch(r'[A-Za-z0-9_-]+', value):
            continue
        if _credential_assignment(key, raw_value):
            return True
    return False


def _private_source(name, raw):
    """Conservative artifact gates, not a proof about encoded/opaque secrets.

    Armor is matched as an actual header line, so a Python test/reference string
    containing the marker does not reject the source implementing this gate.
    Structured credential checks apply to data/configuration, not source code.
    """
    path = PurePosixPath(name)
    parts = tuple(part.casefold() for part in path.parts)
    base = parts[-1]
    if (any(part in {'.local', 'private', '.ssh', '.aws', '.azure'} for part in parts) or
            base.endswith(('.sqlite', '.sqlite3', '.db', '.key', '.p12', '.pfx', '.jks', '.keystore', '.keytab')) or
            base in {'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519', '.netrc', '.git-credentials', '.pgpass', '.pypirc', '.npmrc', 'credentials.json', 'service-account.json', 'service_account.json'} or
            (name.startswith('backend/media/') and name != 'backend/media/.gitkeep')):
        return True
    env_artifact = 'env' in base.split('.') or base == '.envrc'
    template = base.endswith(('.example', '.sample', '.template', '.example.env', '.sample.env', '.template.env'))
    if env_artifact and not template:
        return True
    if re.search(rb'(?m)^[ \t]*-----BEGIN (?:[A-Z0-9 ]*PRIVATE KEY|PGP PRIVATE KEY BLOCK)-----[ \t]*\r?$', raw):
        return True
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeError:
        return False
    if base.endswith('.json'):
        try:
            if _json_credentials(json.loads(text)):
                return True
        except (ValueError, RecursionError):
            pass
    if env_artifact or path.suffix.lower() in {'.ini', '.cfg', '.conf', '.toml', '.yaml', '.yml', '.properties'}:
        return _configuration_credentials(text, template=template, yaml=path.suffix.lower() in {'.yaml', '.yml'})
    return False


def _check_tracked_source(repository, release_id):
    payload = subprocess.check_output(['git', 'archive', '--format=zip', release_id], cwd=repository)
    with ZipFile(io.BytesIO(payload)) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            _relative(entry.filename)
            if stat.S_ISLNK(entry.external_attr >> 16) or _private_source(entry.filename, archive.read(entry)):
                # Neither filenames nor source bytes are echoed: an accidental
                # credential may itself have been used as a filename.
                raise ValueError('The tracked release contains a private-key or credential artifact. Remove it from the release before packaging; no candidate was exported.')


def build_package(repository, target, release_id, app_image, nginx_image):
    repository = _no_links(repository)
    target = _no_links(target)
    # The existing shared exporter performs the clean exact-commit check before
    # reserving a destination. Inspect Git first, before Docker or file mutation.
    if not re.fullmatch(r'[0-9a-f]{40}', str(release_id)):
        raise ValueError('Supply an exact reviewed 40-character source commit.')
    try:
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip()
        dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=repository, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        raise ValueError('A readable clean Git release is required.') from None
    if head != release_id or dirty:
        raise ValueError('Build only from a clean checkout of the exact reviewed commit.')
    if target.exists() or not target.parent.is_dir():
        raise ValueError('Use a new package directory with an existing parent; existing data is never replaced.')
    _check_tracked_source(repository, release_id)
    app_id, nginx_id = _inspect(app_image), _inspect(nginx_image)
    baked = _docker('run', '--rm', '--pull=never', '--network', 'none', '--entrypoint', 'cat', app_id, '/app/RELEASE').decode('ascii').strip()
    if baked != release_id:
        raise ValueError('The application image was built from another source release.')
    target.mkdir(mode=0o700)
    try:
        (target/'images').mkdir()
        (target/'metadata').mkdir()
        shared_spec = importlib.util.spec_from_file_location('customer_export_staging', Path(__file__).resolve().parents[1]/'staging.py')
        shared = importlib.util.module_from_spec(shared_spec)
        shared_spec.loader.exec_module(shared)
        shared.prepare_release(repository, target/'release', release_id)
        # Never distribute runtime datasets or credentials even if an operator
        # accidentally committed them into an otherwise clean release.
        for name in _files(target/'release'):
            parts = PurePosixPath(name).parts
            if '.local' in parts or 'private' in parts or name.endswith(('.sqlite', '.sqlite3', '.db')) or Path(name).name == '.env' or (name.startswith('backend/media/') and name != 'backend/media/.gitkeep'):
                raise ValueError('Tracked private/runtime files were found; this release cannot be packaged.')
        for name in ('DEPENDENCIES.lock', 'OS-PACKAGES.lock'):
            raw = _docker('run', '--rm', '--pull=never', '--network', 'none', '--entrypoint', 'cat', app_id, '/app/'+name)
            (target/'metadata'/name).write_bytes(raw)
        raw = _docker('run', '--rm', '--pull=never', '--network', 'none', '--entrypoint', 'python', app_id, '-c', LICENSE_SCRIPT)
        licenses = json.loads(raw)
        if not isinstance(licenses, list):
            raise ValueError('The observed dependency license metadata is invalid.')
        (target/'metadata/python-license-inventory.json').write_text(json.dumps(licenses, indent=2)+'\n', encoding='utf-8')
        _docker('image', 'save', '--output', str(target/'images/server-images.tar'), app_id, nginx_id)
        manifest = {'format': FORMAT, 'status': 'draft-for-review', 'owner_release_approved': False,
            'release_id': release_id, 'created_utc': datetime.now(timezone.utc).isoformat(),
            'target': {'os': 'linux', 'architecture': 'amd64'}, 'images': {'app': app_id, 'nginx': nginx_id},
            'approval_holds': HOLD_IDS, 'repaired_findings': REPAIRED_FINDINGS, 'private_runtime_included': False,
            'license_status': 'Observed metadata only; PyMuPDF AGPL/commercial route and all redistribution obligations require owner review. NOASSERTION is not clearance.',
            'trust_notice': 'SHA256 detects corruption, not an attacker replacing both manifest and package. Compare the manifest digest through a trusted independent channel.',
            'files': {name: _digest(path) for name, path in _files(target).items()}}
        (target/'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n', encoding='utf-8')
        verify_package(target)
        return {'package': str(target), 'release_id': release_id, 'manifest_sha256': _digest(target/'manifest.json')['sha256'], 'status': 'draft-for-review'}
    except Exception:
        (target/'INCOMPLETE').write_text('Incomplete candidate package. Never install or distribute.\n', encoding='utf-8')
        raise


def _draft(acknowledge):
    if acknowledge is not True:
        raise ValueError('This is an unapproved draft candidate with recorded holds. Explicitly acknowledge draft testing; this does not grant customer or production deployment approval.')


def _private_input(path):
    path = _no_links(path)
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('The external private secret/TLS input is unavailable.')
    if any(char in str(path) for char in '\r\n\0$`\"'):
        raise ValueError('Use directive-safe private input paths.')
    return path


def _write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
    Path(path).chmod(0o600)


def _update_inputs(package, runtime, directory):
    root = _no_links(directory)
    if not root.is_dir() or any(root.is_relative_to(path) or path.is_relative_to(root) for path in (package, runtime)):
        raise ValueError('Use a separate existing operator update directory, outside package and runtime data.')
    _private_input(root/'catalog.json')
    if not _no_links(root/'receipts').is_dir():
        raise ValueError('The existing read-only update receipt directory is unavailable.')
    if not (package/'release/deploy/customer/compose.updates.yaml').is_file():
        raise ValueError('This package does not support persistent Update Center inputs.')
    if any(char in str(root) for char in '\r\n\0$`"'):
        raise ValueError('Use directive-safe external update paths.')
    return root


def prepare_runtime(package, runtime, *, host, lan_ip, secret_file, tls_directory, acknowledge_draft=False, restore_backup=None, update_directory=None):
    _draft(acknowledge_draft)
    manifest = verify_package(package)
    package = _no_links(package)
    runtime = _no_links(runtime)
    if runtime.exists() or not runtime.parent.is_dir() or runtime.is_relative_to(package):
        raise ValueError('Prepare only a new runtime outside the immutable package. Existing records are never initialized or overwritten.')
    address = validate_lan_address(lan_ip)
    secret = _private_input(secret_file)
    tls = _no_links(tls_directory)
    for path in (secret, _private_input(tls/'fullchain.pem'), _private_input(tls/'privkey.pem')):
        if path.is_relative_to(package) or path.is_relative_to(runtime):
            raise ValueError('Private key/secret inputs must be supplied outside the distributable package/runtime.')
    updates = _update_inputs(package, runtime, update_directory) if update_directory is not None else None
    value = secret.read_text(encoding='utf-8').strip()
    if len(value) < 50 or value.startswith(('django-insecure-', 'change-me')):
        raise ValueError('Supply an external production-strength Django secret; its content is never shown.')
    shared = _shared(package)
    nginx = shared.render_nginx(host=host, upstream='web:8000', static_root='/data/static',
        certificate='/tls/fullchain.pem', key='/tls/privkey.pem', http_port=8080, https_port=8443)
    runtime.mkdir(mode=0o700)
    data = runtime/'data'
    try:
        if restore_backup is not None:
            backup = _no_links(restore_backup)
            if backup.is_relative_to(package) or backup.is_relative_to(runtime):
                raise ValueError('Supply a verified external private backup, outside the package/new runtime.')
            helper_path = package/'release/backend/core/operations_backup.py'
            helper = types.ModuleType('customer_shared_backup')
            helper.__file__ = str(helper_path)
            exec(compile(helper_path.read_bytes(), str(helper_path), 'exec'), helper.__dict__)
            helper.restore_backup(backup, data)
            _write_json(runtime/'restored.json', {
                'source_release_id': _json(backup/'manifest.json')['release_id'],
                'source_manifest_sha256': _digest(backup/'manifest.json')['sha256'],
                'target_release_id': manifest['release_id'],
                'created_utc': datetime.now(timezone.utc).isoformat()})
        for path in (data, data/'media', data/'static', data/'upload-tmp'):
            path.mkdir(mode=0o755 if path.name == 'static' else 0o700, exist_ok=restore_backup is not None)
            path.chmod(0o755 if path.name == 'static' else 0o700)
            if hasattr(os, 'geteuid') and os.geteuid() == 0:
                os.chown(path, 10001, 10001)
        if restore_backup is not None:
            # Ownership and restrictive modes apply only to restored COPIES,
            # never to the live source or verified backup artifact.
            for folder, dirs, files in os.walk(data):
                for name in (*dirs, *files):
                    path = _no_links(Path(folder)/name)
                    path.chmod(0o700 if path.is_dir() else 0o600)
                    if hasattr(os, 'geteuid') and os.geteuid() == 0:
                        os.chown(path, 10001, 10001)
            (data/'static').chmod(0o755)
        nginx_path = runtime/'nginx.conf'
        nginx_path.write_text(nginx, encoding='utf-8')
        nginx_path.chmod(0o644)
        values = {'STAGING_HOST': host, 'ISURVIX_LAN_IP': address, 'ISURVIX_RELEASE_ID': manifest['release_id'],
            'ISURVIX_APP_IMAGE': manifest['images']['app'], 'ISURVIX_NGINX_IMAGE': manifest['images']['nginx'],
            'ISURVIX_DATA_DIRECTORY': data.as_posix(), 'ISURVIX_SECRET_FILE': secret.as_posix(),
            'ISURVIX_TLS_DIRECTORY': tls.as_posix(), 'ISURVIX_NGINX_CONFIG': nginx_path.as_posix()}
        if updates is not None:
            values['ISURVIX_UPDATE_DIRECTORY'] = updates.as_posix()
        for value in values.values():
            if any(char in value for char in '\r\n\0$`'):
                raise ValueError('Use directive-safe runtime configuration.')
        env = runtime/'customer.env'
        env.write_text(''.join(name+'='+json.dumps(value)+'\n' for name, value in values.items()), encoding='utf-8')
        env.chmod(0o600)
        state = {'format': FORMAT, 'status': 'draft-for-review', 'release_id': manifest['release_id'],
            'package_manifest_sha256': _digest(package/'manifest.json')['sha256'],
            'env_sha256': _digest(env)['sha256'], 'nginx_sha256': _digest(nginx_path)['sha256'],
            'values': values, 'created_utc': datetime.now(timezone.utc).isoformat()}
        _write_json(runtime/'install.json', state)
        return {'runtime': str(runtime), 'release_id': manifest['release_id'], 'host': host, 'lan_ip': address,
                'database_created': False, 'restored_backup': restore_backup is not None, 'deployment_performed': False,
                'posix_permissions_verified': os.name == 'posix'}
    except Exception:
        (runtime/'INCOMPLETE_PREPARATION').write_text('Incomplete preparation; inspect and recover into a new target.\n')
        raise


def _runtime(package, runtime):
    manifest = verify_package(package)
    runtime = _no_links(runtime)
    state = _json(runtime/'install.json')
    if (state.get('format') != FORMAT or state.get('release_id') != manifest['release_id'] or
            state.get('package_manifest_sha256') != _digest(Path(package)/'manifest.json')['sha256'] or
            state.get('env_sha256') != _digest(runtime/'customer.env')['sha256'] or
            state.get('nginx_sha256') != _digest(runtime/'nginx.conf')['sha256'] or
            (runtime/'INCOMPLETE_PREPARATION').exists()):
        raise ValueError('Runtime/package configuration changed or is incomplete. Review the exact release and configuration before continuing.')
    validate_lan_address(state['values']['ISURVIX_LAN_IP'])
    if state['values'].get('ISURVIX_UPDATE_DIRECTORY'):
        _update_inputs(Path(package).absolute(), runtime, state['values']['ISURVIX_UPDATE_DIRECTORY'])
    return manifest, state


def load_images(package, *, acknowledge_draft=False):
    _draft(acknowledge_draft)
    manifest = verify_package(package)
    _docker('image', 'load', '--input', str(Path(package)/'images/server-images.tar'))
    for image in manifest['images'].values():
        if _inspect(image) != image:
            raise ValueError('A loaded image does not match its reviewed content identity.')
    return {'loaded': True, 'images': manifest['images'], 'network_download_performed': False}


def _compose_base(package, runtime, state):
    runtime, package = Path(runtime), Path(package)
    project = 'isurvix-customer-'+hashlib.sha256(str(runtime.absolute()).encode()).hexdigest()[:12]
    base = ('compose', '--env-file', str(runtime/'customer.env'), '-p', project,
            '-f', str(package/'release/deploy/customer/compose.yaml'))
    if state['values'].get('ISURVIX_UPDATE_DIRECTORY'):
        base += ('-f', str(package/'release/deploy/customer/compose.updates.yaml'))
    return base


def run_action(package, runtime, action, *, acknowledge_draft=False):
    _draft(acknowledge_draft)
    manifest, state = _runtime(package, runtime)
    runtime, package = Path(runtime), Path(package)
    base = _compose_base(package, runtime, state)
    database = runtime/'data/database.sqlite3'
    if action in ('initialize', 'migrate-restored'):
        restored = action == 'migrate-restored'
        if restored:
            if not database.is_file() or not (runtime/'restored.json').is_file() or (runtime/'initialized.json').exists() or (runtime/'INITIALIZATION_STARTED').exists():
                raise ValueError('Migrate only a verified newly restored candidate once. Preserve previous/partial results and recover to another new target after failure.')
        elif database.exists() or (runtime/'INITIALIZATION_STARTED').exists():
            raise ValueError('A database or previous initialization already exists. Preserve it and follow verified new-target recovery; never initialize it again.')
        with (runtime/'INITIALIZATION_STARTED').open('x') as stream:
            stream.write(manifest['release_id']+'\n')
        extra = () if restored else ('-e', 'ISURVIX_INITIALIZE_DATABASE=yes')
        _docker(*base, 'run', '--rm', '--no-deps', '--pull', 'never', *extra,
                'web', 'python', 'manage.py', 'migrate', '--noinput')
        _docker(*base, 'run', '--rm', '--no-deps', '--pull', 'never', 'web', 'python', 'manage.py', 'collectstatic', '--noinput')
        _write_json(runtime/'initialized.json', {'release_id': manifest['release_id'], 'created_utc': datetime.now(timezone.utc).isoformat()})
        return {'initialized': True, 'restored_copy_migrated': restored, 'users_created': 0, 'engineering_approvals_created': 0}
    if action == 'start':
        if not database.is_file() or not (runtime/'initialized.json').is_file():
            raise ValueError('A completed initialized/restored database is required before serving the application.')
        _docker(*base, 'up', '-d', '--pull', 'never', '--no-build')
    elif action == 'stop':
        _docker(*base, 'stop')
    elif action == 'status':
        return {'status': _docker(*base, 'ps', '--format', 'json').decode('utf-8'), 'release_id': manifest['release_id']}
    elif action == 'create-owner':
        if not database.is_file() or not (runtime/'initialized.json').is_file():
            raise ValueError('Initialize the new installation before explicit owner provisioning.')
        # The human operator answers Django's terminal prompts directly. No
        # password argument, generated credential, stored output or default user.
        _local_docker_context()
        result = subprocess.run(['docker', *base, 'run', '--rm', '--no-deps', '--pull', 'never',
                                 'web', 'python', 'manage.py', 'createsuperuser'], check=False)
        if result.returncode:
            raise ValueError('Owner creation did not complete. No password was captured by this helper.')
    else:
        raise ValueError('Use a supported explicit customer-server operation.')
    return {'action': action, 'release_id': manifest['release_id'], 'records_deleted': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    for name in ('verify', 'load', 'prepare', 'initialize', 'migrate-restored', 'start', 'stop', 'status', 'create-owner'):
        command = commands.add_parser(name)
        command.add_argument('--package', type=Path, required=True)
        if name != 'verify':
            command.add_argument('--acknowledge-draft', action='store_true')
        if name not in ('verify', 'load'):
            command.add_argument('--runtime', type=Path, required=True)
        if name == 'verify':
            command.add_argument('--manifest-sha256')
        if name == 'prepare':
            for option in ('host', 'lan-ip', 'secret-file', 'tls-directory'):
                command.add_argument('--'+option, required=True)
            command.add_argument('--restore-backup', type=Path)
            command.add_argument('--update-directory', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.action == 'verify':
            manifest = verify_package(args.package, expected_manifest_sha256=args.manifest_sha256)
            result = {'verified': True, 'release_id': manifest['release_id'], 'owner_release_approved': False}
        elif args.action == 'load':
            result = load_images(args.package, acknowledge_draft=args.acknowledge_draft)
        elif args.action == 'prepare':
            result = prepare_runtime(args.package, args.runtime, host=args.host, lan_ip=args.lan_ip,
                secret_file=args.secret_file, tls_directory=args.tls_directory, acknowledge_draft=args.acknowledge_draft,
                restore_backup=args.restore_backup, update_directory=args.update_directory)
            # Optional recovery is explicit and targets a NEW runtime only.
        else:
            result = run_action(args.package, args.runtime, args.action, acknowledge_draft=args.acknowledge_draft)
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError, KeyError, UnicodeError) as error:
        # Provider/key contents are never echoed; errors describe controlled
        # operator configuration, not stdout/stderr from arbitrary containers.
        parser.exit(2, str(error)+'\n')


if __name__ == '__main__':
    main()
