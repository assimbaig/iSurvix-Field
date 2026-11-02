"""Prepare and test an explicit support repair without operational data.

Candidate code runs only inside an inspected, immutable local Linux Docker image
with no network, no credentials and no production mounts. Git export/patching on
the operator host transforms files only; it never imports candidate source.
Receipts are OPERATOR ATTESTATIONS, not approvals or independently verified CI.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from zipfile import ZipFile, ZIP_DEFLATED


ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = 'assimbaig/iSurvix-Field'
PLAN_FORMAT = 'isurvix-support-repair-plan-v2'
RECEIPT_FORMAT = 'isurvix-support-repair-v1'
MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_LOG_BYTES = 2 * 1024 * 1024
PROOF_KEYS = {'baseline_failed', 'patched_passed', 'unit_passed', 'integration_passed', 'isolation', 'execution_id'}
CONTROLLER = {'id': 'isurvix-unique-photo-counter-v1',
              'unit': 'count_unique(list[str]) returns the number of unique photo identities',
              'integration': 'counter.py INPUT OUTPUT reads links(photo_id,field_id) and writes unique_photos,links',
              'verdict_owner': 'trusted external operator process; never candidate console or JSON verdict'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def sha(value, length=40):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{%d}' % length, value):
        raise ValueError('An exact source/content identity is required.')
    return value


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            result.update(block)
    return result.hexdigest()


def no_links(path):
    path = Path(path).absolute()
    if any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)() for p in (path, *path.parents)):
        raise ValueError('Symbolic or junction paths are not accepted for operator inputs.')
    return path


def read_json(path, limit=131072):
    path = no_links(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError('The bounded operator input is unavailable.')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON fields are not accepted.')
            result[key] = value
        return result
    try:
        return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError('The operator input is not valid bounded JSON.') from None


def relative(name):
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name or '\x00' in name
            or name.startswith('/') or any(p in ('', '.', '..') or p.endswith((' ', '.')) for p in name.split('/'))):
        raise ValueError('Unsafe source/archive path.')
    return PurePosixPath(name)


def archive_entries(archive, *, maximum=MAX_SOURCE_BYTES):
    entries = archive.infolist()
    if not entries or len(entries) > 50000 or sum(e.file_size for e in entries) > maximum:
        raise ValueError('The source archive exceeds the bounded limit.')
    seen = {}
    for entry in entries:
        name = entry.filename.rstrip('/')
        path = relative(name)
        key = name.casefold()
        if key in seen or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1:
            raise ValueError('Duplicate, symbolic or encrypted archive entries are refused.')
        if entry.file_size > 32 * 1024 * 1024:
            raise ValueError('An archive member exceeds the bounded limit.')
        seen[key] = entry.is_dir()
        for ancestor in path.parents:
            if str(ancestor) != '.' and str(ancestor).casefold() in seen and not seen[str(ancestor).casefold()]:
                raise ValueError('A source file cannot also be an archive directory.')
    files = {key for key, directory in seen.items() if not directory}
    for key in seen:
        if any(str(parent) in files for parent in PurePosixPath(key).parents if str(parent) != '.'):
            raise ValueError('A source file cannot contain archive children.')
    return entries


def read_bundle(path):
    path = no_links(path)
    if not path.is_file() or path.stat().st_size > 262144:
        raise ValueError('A bounded support diagnostic ZIP is required.')
    try:
        with ZipFile(path) as archive:
            archive_entries(archive, maximum=262144)
            if sorted(archive.namelist()) != ['diagnostics.json', 'manifest.json']:
                raise ValueError('A diagnostic bundle must contain exactly its two documented JSON members.')
            raw = archive.read('diagnostics.json')
            manifest = json.loads(archive.read('manifest.json'))
            diagnostics = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError('The support diagnostic bundle is unavailable or invalid.') from None
    if (not isinstance(manifest, dict)
            or set(manifest) != {'format', 'case_id', 'report_sha256', 'source_release'}
            or manifest['format'] != 'isurvix-support-diagnostics-v1'
            or not isinstance(diagnostics, dict) or diagnostics.get('format') != 'isurvix-support-health-v1'):
        raise ValueError('Unsupported diagnostic bundle format.')
    try:
        if str(uuid.UUID(manifest['case_id'])) != manifest['case_id']:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Use the immutable support case identity.') from None
    sha(manifest['report_sha256'], 64)
    sha(manifest['source_release'])
    if raw != canonical(diagnostics) or hashlib.sha256(raw).hexdigest() != manifest['report_sha256']:
        raise ValueError('The diagnostic content does not match its immutable case digest.')
    if diagnostics.get('release') != manifest['source_release']:
        raise ValueError('Diagnostic and manifest source identities differ.')
    return manifest


def clean_environment():
    # Used for trusted host Git and test subprocesses. No API key, cloud credential,
    # application setting or operator secret is inherited into a repair test.
    allowed = ('PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT')
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0',
               PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8', ORT_DISABLE_TELEMETRY='1',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', LANG='C.UTF-8')
    return env


def git(repository, *args, binary=False):
    environment = clean_environment()
    # A new export may live below the operator checkout's ignored .local tree.
    # Never let Git discover and patch that ancestor repository instead.
    environment['GIT_CEILING_DIRECTORIES'] = str(Path(repository).resolve().parent)
    result = subprocess.run(['git', '-c', 'core.hooksPath=' + os.devnull, *args], cwd=repository,
                            env=environment, capture_output=True, timeout=90)
    if result.returncode:
        raise ValueError('An exact source or reviewed patch could not be validated. No original source was changed.')
    return result.stdout if binary else result.stdout.decode('utf-8').strip()


def customer_guard():
    spec = importlib.util.spec_from_file_location('support_customer_source_guard', ROOT / 'deploy/customer/customer.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def source_archive(repository, commit):
    raw = git(repository, 'archive', '--format=zip', sha(commit), binary=True)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError('The source export exceeds the bounded limit.')
    guard = customer_guard()
    with ZipFile(io.BytesIO(raw)) as archive:
        entries = archive_entries(archive)
        for entry in entries:
            if not entry.is_dir() and guard._private_source(entry.filename, archive.read(entry)):
                raise ValueError('Private runtime or credential material cannot enter a repair workspace.')
    return raw


def extract_source(path, destination):
    path = no_links(path)
    destination = no_links(destination)
    if destination.exists():
        raise ValueError('A fresh source extraction directory is required.')
    with ZipFile(path) as archive:
        entries = archive_entries(archive)
        destination.mkdir(parents=True, mode=0o700)
        for entry in entries:
            target = destination / entry.filename
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(archive.read(entry))
    return destination


def patch_bytes(path):
    path = no_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= 2 * 1024 * 1024:
        raise ValueError('A bounded explicit patch is required.')
    raw = path.read_bytes()
    try:
        text = raw.decode('utf-8')
    except UnicodeError:
        raise ValueError('Only UTF-8 textual repair patches are accepted.') from None
    if any(marker in text for marker in ('GIT binary patch', 'new file mode 120000',
                                        'new file mode 160000', 'rename from ', 'rename to ')):
        raise ValueError('Binary, symbolic, submodule or rename patches require separate review.')
    names = []
    for line in text.splitlines():
        if line.startswith(('--- ', '+++ ')):
            name = line[4:].split('\t')[0]
            if name == '/dev/null':
                continue
            if not name.startswith(('a/', 'b/')):
                raise ValueError('Use a standard source-relative Git patch.')
            name = name[2:]
            relative(name)
            if not name.startswith(('backend/', 'frontend/', 'tests/')) or any(
                    p.casefold() in {'.local', '.git', 'private', 'media', '.ssh'} or p.startswith('.env')
                    for p in PurePosixPath(name).parts):
                raise ValueError('Repair patches cannot change operator, workflow or operational paths.')
            names.append(name)
    if not names:
        raise ValueError('The patch contains no permitted source changes.')
    return raw


def inventory(root):
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob('*')) if p.is_file()}


def zip_source(root, target):
    with ZipFile(target, 'x', compression=ZIP_DEFLATED) as archive:
        for name in inventory(root):
            archive.write(root / name, name)


def label_list(values):
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 8:
        raise ValueError('Select between one and eight explicit ordinary test labels.')
    if any(not isinstance(v, str) or not re.fullmatch(r'core\.test_[A-Za-z0-9_.]{1,160}', v) for v in values):
        raise ValueError('Only explicit project test labels are accepted; shell commands are not.')
    return list(values)


def test_identities(workspace):
    """Record regression references without importing or executing their code."""
    identities = {}
    for stage in ('unit', 'integration'):
        relative_path = 'tests/fixtures/support_repair/test_' + stage + '.py'
        path = no_links(Path(workspace) / relative_path)
        if not path.is_file() or path.stat().st_size > 131072:
            raise ValueError('The supported repair requires both bounded immutable regression files.')
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (UnicodeError, SyntaxError, RecursionError):
            raise ValueError('Regression references must be valid bounded Python source.') from None
        nodes = list(ast.walk(tree))
        if len(nodes) > 10000:
            raise ValueError('The regression reference exceeds the bounded limit.')
        methods = sorted(node.name for node in nodes if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'))
        skipped = any((isinstance(node, ast.Name) and node.id in {'skip', 'skipIf', 'skipUnless'}) or
                      (isinstance(node, ast.Attribute) and node.attr in {'skip', 'skipIf', 'skipUnless'}) for node in nodes)
        if not methods or skipped:
            raise ValueError('Zero or skipped regression references cannot satisfy repair acceptance.')
        identities[stage] = {'path': relative_path, 'sha256': digest(path), 'methods': methods}
    return identities


def suite_plan(workspace):
    """Construct a trusted-controller plan for explicit, known fixture tests.

    This never executes candidate code and is not an OS-isolation mechanism.
    Public execution always supplies a Docker probe executor from run().
    """
    return {'profile': 'synthetic-stdlib', 'unit_labels': [], 'integration_labels': [],
            'controller_sha256': hashlib.sha256(canonical(CONTROLLER)).hexdigest(),
            'test_identities': test_identities(workspace)}


def prepare(*, repository, output, bundle, base_commit, tested_commit, regression_patch, repair_patch,
            profile, unit_labels=(), integration_labels=(), github_repository=REPOSITORY):
    repository = no_links(repository)
    output = no_links(output)
    if output.exists() or repository == output or repository.is_relative_to(output):
        raise ValueError('Use a new repair output path, never an existing or parent source directory.')
    manifest = read_bundle(bundle)
    sha(base_commit); sha(tested_commit)
    if base_commit != manifest['source_release'] or base_commit == tested_commit:
        raise ValueError('The repair must bind the report source to a different exact tested candidate.')
    if not isinstance(github_repository, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', github_repository):
        raise ValueError('Use one explicit approved GitHub repository identity.')
    if profile != 'synthetic-stdlib':
        raise ValueError('Generic Django repair execution is unsupported until a protected external black-box adapter is approved. Ordinary application tests remain separate.')
    if unit_labels or integration_labels:
        raise ValueError('The approved synthetic controller has fixed checks; arbitrary test commands are unsupported.')
    units, integrations = [], []
    regression = patch_bytes(regression_patch)
    repair = patch_bytes(repair_patch)
    base = source_archive(repository, base_commit)
    candidate = source_archive(repository, tested_commit)
    git(repository, 'merge-base', '--is-ancestor', base_commit, tested_commit)
    output.mkdir(parents=True, mode=0o700)
    try:
        (output / 'original.zip').write_bytes(base)
        (output / 'candidate.zip').write_bytes(candidate)
        (output / 'regression.patch').write_bytes(regression)
        (output / 'repair.patch').write_bytes(repair)
        with tempfile.TemporaryDirectory(prefix='prepare-', dir=output) as temporary:
            temp = Path(temporary)
            baseline = extract_source(output / 'original.zip', temp / 'baseline')
            git(baseline, 'apply', '--check', str(output / 'regression.patch'))
            git(baseline, 'apply', str(output / 'regression.patch'))
            references = test_identities(baseline)
            zip_source(baseline, output / 'baseline.zip')
            git(baseline, 'apply', '--check', str(output / 'repair.patch'))
            git(baseline, 'apply', str(output / 'repair.patch'))
            expected = extract_source(output / 'candidate.zip', temp / 'candidate')
            if inventory(baseline) != inventory(expected):
                raise ValueError('The exact candidate tree differs from the two explicitly reviewed patches.')
            if test_identities(expected) != references:
                raise ValueError('Candidate repairs cannot replace, remove or skip the immutable regression references.')
        (output / 'original.zip').unlink()
        plan = {'format': PLAN_FORMAT, 'case_id': manifest['case_id'], 'report_sha256': manifest['report_sha256'],
                'base_commit': base_commit, 'tested_commit': tested_commit,
                'patch_sha256': hashlib.sha256(repair).hexdigest(),
                'regression_sha256': hashlib.sha256(regression).hexdigest(),
                'profile': profile, 'unit_labels': units, 'integration_labels': integrations,
                'github_repository': github_repository, 'runner_sha256': digest(__file__),
                'controller_sha256': hashlib.sha256(canonical(CONTROLLER)).hexdigest(),
                'test_identities': references,
                'input_sha256': {name: digest(output / name) for name in
                                 ('baseline.zip', 'candidate.zip', 'regression.patch', 'repair.patch')}}
        (output / 'plan.json').write_bytes(canonical(plan))
        return plan
    except Exception:
        # Keep an incomplete NEW target for diagnosis; it is not executable
        # without its final complete plan and must not be reused.
        raise


def validate_plan(directory):
    directory = no_links(directory)
    plan = read_json(directory / 'plan.json')
    keys = {'format', 'case_id', 'report_sha256', 'base_commit', 'tested_commit', 'patch_sha256',
            'regression_sha256', 'profile', 'unit_labels', 'integration_labels', 'github_repository',
            'runner_sha256', 'input_sha256', 'controller_sha256', 'test_identities'}
    if not isinstance(plan, dict) or set(plan) != keys or plan['format'] != PLAN_FORMAT:
        raise ValueError('A complete supported repair plan is required.')
    if str(uuid.UUID(plan['case_id'])) != plan['case_id']:
        raise ValueError('Invalid support case identity.')
    for key in ('report_sha256', 'patch_sha256', 'regression_sha256', 'runner_sha256'):
        sha(plan[key], 64)
    sha(plan['base_commit']); sha(plan['tested_commit'])
    if plan['base_commit'] == plan['tested_commit'] or plan['runner_sha256'] != digest(__file__):
        raise ValueError('The source or reviewed operator runner identity changed.')
    expected = {'baseline.zip', 'candidate.zip', 'regression.patch', 'repair.patch'}
    if not isinstance(plan['input_sha256'], dict) or set(plan['input_sha256']) != expected:
        raise ValueError('All immutable repair input hashes are required.')
    for name, value in plan['input_sha256'].items():
        sha(value, 64)
        if digest(no_links(directory / name)) != value:
            raise ValueError('A prepared repair input changed; prepare a new reviewed workspace.')
    if (plan['profile'] != 'synthetic-stdlib' or plan['unit_labels'] or plan['integration_labels']
            or plan['controller_sha256'] != hashlib.sha256(canonical(CONTROLLER)).hexdigest()
            or not isinstance(plan['test_identities'], dict) or set(plan['test_identities']) != {'unit', 'integration'}):
        raise ValueError('Unsupported or changed trusted black-box controller.')
    return plan


def docker_preflight(image):
    if os.name != 'posix':
        raise ValueError('Repair execution requires an approved local Linux Docker host; no host-code fallback exists.')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', str(image)):
        raise ValueError('Supply an inspected immutable local image ID; no image is downloaded.')
    guard = customer_guard()
    if guard._inspect(image) != image:
        raise ValueError('The supplied local image has a different immutable identity.')


def docker_command(directory, image, name, *, uid, gid, target='candidate', stage='unit'):
    directory = no_links(directory)
    validate_plan(directory)
    if (not re.fullmatch(r'sha256:[0-9a-f]{64}', str(image))
            or not re.fullmatch(r'isurvix-support-[0-9a-f]{32}', name)
            or type(uid) is not int or type(gid) is not int or uid < 0 or gid < 0
            or target not in ('baseline', 'candidate') or stage not in ('unit', 'integration')):
        raise ValueError('Use the fixed isolated Docker profile and exact immutable image.')
    return ['docker', 'run', '--rm', '--interactive', '--pull=never', '--name=' + name, '--network=none', '--read-only',
            '--cap-drop=ALL', '--security-opt=no-new-privileges:true', '--pids-limit=128',
            '--memory=2g', '--cpus=2', '--user=%d:%d' % (uid, gid), '--log-driver=none',
            '--tmpfs=/work:rw,nosuid,nodev,size=768m,uid=%d,gid=%d,mode=0700' % (uid, gid),
            '--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=64m,uid=%d,gid=%d,mode=0700' % (uid, gid),
            '--mount', 'type=bind,src=' + str(directory) + ',dst=/inputs,readonly',
            '--mount', 'type=bind,src=' + str(Path(__file__).resolve()) + ',dst=/repair-tool.py,readonly',
            '--env=ISURVIX_REPAIR_CONTAINER=1', '--env=HOME=/work/home',
            '--env=PYTHONDONTWRITEBYTECODE=1', '--env=ORT_DISABLE_TELEMETRY=1',
            '--env=HF_HUB_OFFLINE=1', '--env=TRANSFORMERS_OFFLINE=1',
            image, '/usr/local/bin/python', '-I', '/repair-tool.py', 'container-probe',
            '--target', target, '--stage', stage]


def bounded_process(command, *, cwd=None, env=None, timeout=900, maximum=MAX_LOG_BYTES, input_data=None):
    if input_data is not None and (not isinstance(input_data, bytes) or len(input_data) > 16384):
        raise ValueError('The fixed business probe input exceeds its bounded limit.')
    process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    chunks = []
    exceeded = threading.Event()
    def read():
        total = 0
        while block := process.stdout.read(65536):
            total += len(block)
            if total > maximum:
                exceeded.set()
                process.kill()
                break
            chunks.append(block)
    thread = threading.Thread(target=read, daemon=True)
    thread.start()
    if input_data is not None:
        try:
            process.stdin.write(input_data)
        except BrokenPipeError:
            pass
        finally:
            try:
                process.stdin.close()
            except BrokenPipeError:
                pass
    try:
        result = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill(); process.wait(); thread.join(5)
        raise ValueError('The bounded repair test time expired; no successful receipt was produced.') from None
    finally:
        thread.join(5)
        if process.stdout:
            process.stdout.close()
    if exceeded.is_set() or thread.is_alive():
        raise ValueError('Repair output exceeded the bounded limit; no successful receipt was produced.')
    return b''.join(chunks).decode('utf-8', errors='replace'), result


def test_result(output, returncode, *, require_failure=False):
    raise ValueError('Candidate console summaries are not authoritative test evidence; use the protected external controller.')


def probe_request(stage, identity):
    """Fresh business requests; expected results stay in the host controller."""
    values = [uuid.uuid4().hex for _ in range(6)]
    groups = [[], [values[0]], [values[0], values[0]],
              [values[0], values[1], values[0]], values[:3 + uuid.uuid4().int % 4]]
    cases = []
    for group in groups:
        payload = {'values': group} if stage == 'unit' else {'links': [
            {'photo_id': value, 'field_id': 'point-' + str(index % 2)} for index, value in enumerate(group)]}
        cases.append({'id': uuid.uuid4().hex, 'payload': payload})
    return {'format': 'isurvix-counter-probe-v1', 'probe_id': str(uuid.uuid4()),
            'stage': stage, 'controller_id': CONTROLLER['id'], 'test_identity': identity, 'cases': cases}


UNIT_BRIDGE = '''import importlib.util,json,sys
payload=json.loads(sys.stdin.buffer.read(16385))
spec=importlib.util.spec_from_file_location('untrusted_repair_counter',sys.argv[1])
candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
value=candidate.count_unique(payload['values'])
sys.stdout.write(json.dumps({'value':value},allow_nan=False))
'''


def business_probe(workspace, request):
    """Container adapter: execute candidate in CHILD processes, never here.

    It forwards bounded business observations only. It does not decide whether
    a test passed and cannot issue any receipt. Local tests may explicitly call
    this adapter on known synthetic fixtures; public execution has no fallback.
    """
    workspace = Path(workspace)
    if (not isinstance(request, dict) or set(request) != {'format', 'probe_id', 'stage', 'controller_id', 'test_identity', 'cases'}
            or request.get('format') != 'isurvix-counter-probe-v1'
            or request.get('controller_id') != CONTROLLER['id'] or request.get('stage') not in ('unit', 'integration')
            or not isinstance(request.get('cases'), list) or not 1 <= len(request['cases']) <= 8):
        raise ValueError('Unsupported fixed business-probe request.')
    stage = request['stage']
    module = no_links(workspace / 'tests/fixtures/support_repair/counter.py')
    if not module.is_file():
        raise ValueError('The approved business adapter requires its exact counter interface.')
    temp = workspace / '.local/business-probes'
    temp.mkdir(parents=True, exist_ok=True)
    env = clean_environment()
    env.update(TMP=str(temp), TEMP=str(temp), TMPDIR=str(temp), HOME=str(temp))
    observations = []
    for case in request['cases']:
        if not isinstance(case, dict) or set(case) != {'id', 'payload'}:
            raise ValueError('Malformed fixed business probe.')
        item = {'case_id': case['id'], 'returncode': -1, 'business': None,
                'input_unchanged': True, 'error_code': ''}
        try:
            if stage == 'unit':
                output, code = bounded_process([sys.executable, '-I', '-c', UNIT_BRIDGE, str(module)],
                    cwd=workspace, env=env, timeout=10, maximum=65536, input_data=canonical(case['payload']))
                item['returncode'] = code
                if code:
                    item['error_code'] = 'process_failed'
                else:
                    try:
                        item['business'] = json.loads(output)
                    except (ValueError, RecursionError):
                        item['error_code'] = 'invalid_business_response'
            else:
                with tempfile.TemporaryDirectory(dir=temp) as folder:
                    source = Path(folder) / 'request.json'
                    target = Path(folder) / 'response.json'
                    original = canonical(case['payload'])
                    source.write_bytes(original)
                    _output, code = bounded_process([sys.executable, '-I', str(module), str(source), str(target)],
                        cwd=workspace, env=env, timeout=10, maximum=65536)
                    item['returncode'] = code
                    item['input_unchanged'] = source.is_file() and source.read_bytes() == original
                    if code:
                        item['error_code'] = 'process_failed'
                    elif not target.is_file() or target.stat().st_size > 65536:
                        item['error_code'] = 'invalid_business_response'
                    else:
                        try:
                            item['business'] = read_json(target, 65536)
                        except (ValueError, OSError):
                            item['error_code'] = 'invalid_business_response'
        except (ValueError, OSError):
            item['error_code'] = 'execution_failed'
        observations.append(item)
    return {'format': 'isurvix-counter-response-v1', 'probe_id': request['probe_id'],
            'stage': stage, 'controller_id': CONTROLLER['id'], 'observations': observations}


def evaluate_probe(request, response):
    """The trusted HOST owns every assertion and produces the only verdict."""
    failures, errors = 0, 0
    valid = (isinstance(response, dict)
             and set(response) == {'format', 'probe_id', 'stage', 'controller_id', 'observations'}
             and response.get('format') == 'isurvix-counter-response-v1'
             and response.get('probe_id') == request['probe_id']
             and response.get('stage') == request['stage']
             and response.get('controller_id') == CONTROLLER['id']
             and isinstance(response.get('observations'), list)
             and len(response['observations']) == len(request['cases']))
    if not valid:
        errors = len(request['cases'])
    else:
        for case, item in zip(request['cases'], response['observations']):
            if (not isinstance(item, dict)
                    or set(item) != {'case_id', 'returncode', 'business', 'input_unchanged', 'error_code'}
                    or item.get('case_id') != case['id'] or type(item.get('returncode')) is not int
                    or item['returncode'] != 0 or item.get('error_code') != ''
                    or type(item.get('input_unchanged')) is not bool):
                errors += 1
                continue
            value = item['business']
            if request['stage'] == 'unit':
                expected = {'value': len(set(case['payload']['values']))}
            else:
                links = case['payload']['links']
                expected = {'unique_photos': len({link['photo_id'] for link in links}), 'links': len(links)}
            if (not isinstance(value, dict) or set(value) != set(expected)
                    or any(type(number) is not int or number < 0 for number in value.values())):
                errors += 1
            elif value != expected or item['input_unchanged'] is not True:
                failures += 1
    return {'tests': len(request['cases']), 'failures': failures, 'errors': errors, 'skipped': 0,
            'passed': failures == errors == 0, 'returncode': 0 if failures == errors == 0 else 1,
            'log_sha256': hashlib.sha256(canonical(response)).hexdigest(),
            'controller_id': CONTROLLER['id'], 'probe_id': request['probe_id']}


def run_suite(workspace, plan, stage, *, require_failure=False, probe_executor=None):
    if stage not in ('unit', 'integration'):
        raise ValueError('Use the fixed unit or integration stage.')
    if probe_executor is None:
        raise ValueError('A protected external probe executor is required; no host candidate-execution fallback exists.')
    if (plan.get('profile') != 'synthetic-stdlib'
            or plan.get('controller_sha256') != hashlib.sha256(canonical(CONTROLLER)).hexdigest()
            or plan.get('test_identities') != test_identities(workspace)
            or plan.get('runner_sha256', digest(__file__)) != digest(__file__)):
        raise ValueError('The approved controller or immutable regression identity changed.')
    request = probe_request(stage, plan['test_identities'][stage])
    response = probe_executor(request)
    result = evaluate_probe(request, response)
    if plan['test_identities'] != test_identities(workspace):
        raise ValueError('A regression reference changed during probing.')
    if require_failure and not (result['failures'] > 0 and result['errors'] == 0):
        raise ValueError('Baseline must return valid business data that fails a trusted assertion; crashes, exits and malformed replies do not reproduce the bug.')
    return result


def proof_valid(proof):
    if (not isinstance(proof, dict) or set(proof) != PROOF_KEYS
            or any(proof.get(k) is not True for k in ('baseline_failed', 'patched_passed', 'unit_passed', 'integration_passed'))
            or proof.get('isolation') != 'docker-no-network'):
        raise ValueError('A complete successful isolated regression/unit/integration proof is required.')
    try:
        if str(uuid.UUID(proof['execution_id'])) != proof['execution_id']:
            raise ValueError()
    except (TypeError, ValueError, AttributeError):
        raise ValueError('Use the exact isolated execution identity.') from None


def receipt(plan, proof):
    proof_valid(proof)
    return {'format': RECEIPT_FORMAT, 'case_id': plan['case_id'], 'report_sha256': plan['report_sha256'],
            'base_commit': plan['base_commit'], 'tested_commit': plan['tested_commit'],
            'patch_sha256': plan['patch_sha256'], 'regression_sha256': plan['regression_sha256'],
            'test_evidence': proof, 'pr_url': '', 'provenance': 'operator-attested',
            'candidate_only': True, 'owner_release_approved': False}


def validate_receipt(value):
    keys = {'format', 'case_id', 'report_sha256', 'base_commit', 'tested_commit', 'patch_sha256',
            'regression_sha256', 'test_evidence', 'pr_url', 'provenance', 'candidate_only', 'owner_release_approved'}
    if (not isinstance(value, dict) or set(value) != keys or value['format'] != RECEIPT_FORMAT
            or value['provenance'] != 'operator-attested' or value['candidate_only'] is not True
            or value['owner_release_approved'] is not False):
        raise ValueError('Only an explicitly unapproved operator-attested repair receipt is supported.')
    if str(uuid.UUID(value['case_id'])) != value['case_id']:
        raise ValueError('Invalid support case identity.')
    sha(value['base_commit']); sha(value['tested_commit'])
    for key in ('report_sha256', 'patch_sha256', 'regression_sha256'):
        sha(value[key], 64)
    proof_valid(value['test_evidence'])
    return value


def link_pr(source, pr_url, target, *, github_repository=REPOSITORY):
    value = validate_receipt(read_json(source))
    if not re.fullmatch('https://github\\.com/' + re.escape(github_repository) + r'/pull/[1-9][0-9]*', str(pr_url)):
        raise ValueError('Record the actual draft PR URL in the configured repository; queries and fragments are refused.')
    if value['pr_url'] and value['pr_url'] != pr_url:
        raise ValueError('The receipt already names another PR; retain it and create a new reviewed attempt.')
    result = {**value, 'pr_url': pr_url}
    target = no_links(target)
    if target.exists():
        if read_json(target) == result:
            return result
        raise ValueError('Existing evidence cannot be overwritten.')
    with target.open('xb') as stream:
        stream.write(canonical(result))
    return result


def container_run():
    raise ValueError('Legacy in-container test verdicts are disabled. Only host-controlled business probes are supported.')


def container_probe(target, stage):
    if (os.name != 'posix' or not Path('/.dockerenv').exists()
            or os.environ.get('ISURVIX_REPAIR_CONTAINER') != '1'):
        raise ValueError('The internal test runner is available only in its isolated container profile.')
    directory = Path('/inputs')
    plan = validate_plan(directory)
    isolation = {'network_blocked': False, 'inputs_readonly': False,
                 'credentials_absent': not any(key in os.environ for key in
                     ('GITHUB_TOKEN', 'GH_TOKEN', 'OPENAI_API_KEY', 'DJANGO_SECRET_KEY',
                      'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AZURE_CLIENT_SECRET')),
                 'docker_socket_absent': not Path('/var/run/docker.sock').exists()}
    try:
        connection = socket.create_connection(('1.1.1.1', 443), timeout=1)
    except OSError:
        isolation['network_blocked'] = True
    else:
        connection.close()
    try:
        with (directory / ('.write-probe-' + uuid.uuid4().hex)).open('xb'):
            pass
    except OSError as error:
        import errno
        isolation['inputs_readonly'] = error.errno in (errno.EROFS, errno.EPERM, errno.EACCES)
    if not all(isolation.values()):
        raise ValueError('The container did not demonstrate its required isolation controls.')
    if target not in ('baseline', 'candidate') or stage not in ('unit', 'integration'):
        raise ValueError('Use only the fixed baseline/candidate business stages.')
    raw = sys.stdin.buffer.read(16385)
    if len(raw) > 16384:
        raise ValueError('The business probe exceeds its bounded input size.')
    request = json.loads(raw)
    if (not isinstance(request, dict) or request.get('stage') != stage
            or request.get('test_identity') != plan['test_identities'][stage]):
        raise ValueError('The probe names a different immutable regression reference.')
    work = Path('/work')
    (work / 'home').mkdir(exist_ok=True)
    workspace = extract_source(directory / (target + '.zip'), work / 'source')
    if test_identities(workspace) != plan['test_identities']:
        raise ValueError('The candidate replaced the immutable regression references.')
    # No candidate is imported into this adapter process. More importantly, the
    # host receives BUSINESS observations, never test counts or a pass verdict.
    print(json.dumps({'response': business_probe(workspace, request),
                      'isolation_checks': isolation}, sort_keys=True))


def run(directory, image):
    directory = no_links(directory)
    plan = validate_plan(directory)
    if (directory / 'repair-receipt.json').exists() or (directory / 'execution.json').exists():
        raise ValueError('This immutable attempt already has evidence. Do not overwrite a completed attempt.')
    docker_preflight(image)
    stages, probes = {}, []
    try:
        # Inspection only: no candidate imports or host execution. The Docker
        # inputs remain read-only, and the HOST controller owns every assertion.
        with tempfile.TemporaryDirectory(prefix='controller-', dir=directory) as temporary:
            work = Path(temporary)
            for target in ('baseline', 'candidate'):
                workspace = extract_source(directory / (target + '.zip'), work / target)
                for stage in ('unit', 'integration'):
                    def executor(request):
                        name = 'isurvix-support-' + uuid.uuid4().hex
                        command = docker_command(directory, image, name, uid=os.getuid(), gid=os.getgid(), target=target, stage=stage)
                        try:
                            output, code = bounded_process(command, timeout=180, maximum=131072,
                                                           input_data=canonical(request))
                            if code:
                                raise ValueError('The isolated business adapter did not finish; no repair receipt was written.')
                            envelope = json.loads(output)
                            checks = envelope.get('isolation_checks')
                            if (not isinstance(envelope, dict) or set(envelope) != {'response', 'isolation_checks'}
                                    or not isinstance(checks, dict)
                                    or set(checks) != {'network_blocked', 'inputs_readonly', 'credentials_absent', 'docker_socket_absent'}
                                    or any(value is not True for value in checks.values())):
                                raise ValueError('The isolated adapter did not supply the required controls and business response.')
                            probes.append({'target': target, 'stage': stage, 'request_sha256': hashlib.sha256(canonical(request)).hexdigest(),
                                           'response_sha256': hashlib.sha256(canonical(envelope['response'])).hexdigest(),
                                           'isolation_checks': checks})
                            return envelope['response']
                        finally:
                            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20)
                    result = run_suite(workspace, plan, stage, require_failure=target == 'baseline', probe_executor=executor)
                    stages[target + '_' + stage] = result
                    if target == 'candidate' and result['passed'] is not True:
                        raise ValueError('Candidate business behavior did not pass the trusted host assertions.')
        proof = {'baseline_failed': True, 'patched_passed': True, 'unit_passed': True,
                 'integration_passed': True, 'isolation': 'docker-no-network', 'execution_id': str(uuid.uuid4())}
        saved = receipt(plan, proof)
        metadata = {'format': 'isurvix-support-execution-v2', 'image': image, 'network': 'none',
                    'production_mounts': False, 'credentials_forwarded': False,
                    'verdict_owner': 'trusted-host-blackbox-controller', 'controller': CONTROLLER,
                    'controller_sha256': plan['controller_sha256'], 'test_identities': plan['test_identities'],
                    'created_utc': datetime.now(timezone.utc).isoformat(), 'stages': stages, 'probes': probes,
                    'receipt': saved}
        (directory / 'execution.json').write_bytes(canonical(metadata))
        (directory / 'repair-receipt.json').write_bytes(canonical(saved))
        return saved
    except (OSError, json.JSONDecodeError, KeyError, TypeError, AttributeError):
        raise ValueError('The isolated repair did not return complete valid business evidence.') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_cmd = commands.add_parser('prepare')
    for key in ('repository', 'output', 'bundle', 'regression-patch', 'repair-patch'):
        prepare_cmd.add_argument('--' + key, type=Path, required=True)
    for key in ('base-commit', 'tested-commit'):
        prepare_cmd.add_argument('--' + key, required=True)
    prepare_cmd.add_argument('--profile', choices=['synthetic-stdlib', 'django'], required=True)
    prepare_cmd.add_argument('--unit-label', action='append', default=[])
    prepare_cmd.add_argument('--integration-label', action='append', default=[])
    prepare_cmd.add_argument('--github-repository', default=REPOSITORY)
    run_cmd = commands.add_parser('run')
    run_cmd.add_argument('--directory', type=Path, required=True)
    run_cmd.add_argument('--image', required=True)
    link_cmd = commands.add_parser('link-pr')
    link_cmd.add_argument('--receipt', type=Path, required=True)
    link_cmd.add_argument('--pr-url', required=True)
    link_cmd.add_argument('--output', type=Path, required=True)
    link_cmd.add_argument('--github-repository', default=REPOSITORY)
    commands.add_parser('container', help=argparse.SUPPRESS)
    probe_cmd = commands.add_parser('container-probe', help=argparse.SUPPRESS)
    probe_cmd.add_argument('--target', choices=['baseline', 'candidate'], required=True)
    probe_cmd.add_argument('--stage', choices=['unit', 'integration'], required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            result = prepare(repository=args.repository, output=args.output, bundle=args.bundle,
                             base_commit=args.base_commit, tested_commit=args.tested_commit,
                             regression_patch=args.regression_patch, repair_patch=args.repair_patch,
                             profile=args.profile, unit_labels=args.unit_label,
                             integration_labels=args.integration_label, github_repository=args.github_repository)
        elif args.command == 'run':
            result = run(args.directory, args.image)
        elif args.command == 'link-pr':
            result = link_pr(args.receipt, args.pr_url, args.output, github_repository=args.github_repository)
        elif args.command == 'container-probe':
            container_probe(args.target, args.stage)
            return 0
        else:
            container_run()
            return 0
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
