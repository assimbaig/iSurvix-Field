"""Prepare and test an explicit support repair without operational data.

Candidate code runs only inside an inspected, immutable local Linux Docker image
with no network, no credentials and no production mounts. Git export/patching on
the operator host transforms files only; it never imports candidate source.
Receipts are OPERATOR ATTESTATIONS, not approvals or independently verified CI.
"""
import argparse
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
PLAN_FORMAT = 'isurvix-support-repair-plan-v1'
RECEIPT_FORMAT = 'isurvix-support-repair-v1'
MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_LOG_BYTES = 2 * 1024 * 1024
PROOF_KEYS = {'baseline_failed', 'patched_passed', 'unit_passed', 'integration_passed', 'isolation', 'execution_id'}


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
    if profile not in ('synthetic-stdlib', 'django'):
        raise ValueError('Only the fixed synthetic or ordinary Django test profiles are available.')
    units = label_list(unit_labels) if profile == 'django' else []
    integrations = label_list(integration_labels) if profile == 'django' else []
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
            zip_source(baseline, output / 'baseline.zip')
            git(baseline, 'apply', '--check', str(output / 'repair.patch'))
            git(baseline, 'apply', str(output / 'repair.patch'))
            expected = extract_source(output / 'candidate.zip', temp / 'candidate')
            if inventory(baseline) != inventory(expected):
                raise ValueError('The exact candidate tree differs from the two explicitly reviewed patches.')
        (output / 'original.zip').unlink()
        plan = {'format': PLAN_FORMAT, 'case_id': manifest['case_id'], 'report_sha256': manifest['report_sha256'],
                'base_commit': base_commit, 'tested_commit': tested_commit,
                'patch_sha256': hashlib.sha256(repair).hexdigest(),
                'regression_sha256': hashlib.sha256(regression).hexdigest(),
                'profile': profile, 'unit_labels': units, 'integration_labels': integrations,
                'github_repository': github_repository, 'runner_sha256': digest(__file__),
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
            'runner_sha256', 'input_sha256'}
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
    if plan['profile'] == 'django':
        label_list(plan['unit_labels']); label_list(plan['integration_labels'])
    elif plan['profile'] != 'synthetic-stdlib' or plan['unit_labels'] or plan['integration_labels']:
        raise ValueError('Unsupported fixed test profile.')
    return plan


def docker_preflight(image):
    if os.name != 'posix':
        raise ValueError('Repair execution requires an approved local Linux Docker host; no host-code fallback exists.')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', str(image)):
        raise ValueError('Supply an inspected immutable local image ID; no image is downloaded.')
    guard = customer_guard()
    if guard._inspect(image) != image:
        raise ValueError('The supplied local image has a different immutable identity.')


def docker_command(directory, image, name, *, uid, gid):
    directory = no_links(directory)
    validate_plan(directory)
    if (not re.fullmatch(r'sha256:[0-9a-f]{64}', str(image))
            or not re.fullmatch(r'isurvix-support-[0-9a-f]{32}', name)
            or type(uid) is not int or type(gid) is not int or uid < 0 or gid < 0):
        raise ValueError('Use the fixed isolated Docker profile and exact immutable image.')
    return ['docker', 'run', '--rm', '--pull=never', '--name=' + name, '--network=none', '--read-only',
            '--cap-drop=ALL', '--security-opt=no-new-privileges:true', '--pids-limit=128',
            '--memory=2g', '--cpus=2', '--user=%d:%d' % (uid, gid), '--log-driver=none',
            '--tmpfs=/work:rw,nosuid,nodev,size=768m,uid=%d,gid=%d,mode=0700' % (uid, gid),
            '--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=64m,uid=%d,gid=%d,mode=0700' % (uid, gid),
            '--mount', 'type=bind,src=' + str(directory) + ',dst=/inputs,readonly',
            '--mount', 'type=bind,src=' + str(Path(__file__).resolve()) + ',dst=/repair-tool.py,readonly',
            '--env=ISURVIX_REPAIR_CONTAINER=1', '--env=HOME=/work/home',
            '--env=PYTHONDONTWRITEBYTECODE=1', '--env=ORT_DISABLE_TELEMETRY=1',
            '--env=HF_HUB_OFFLINE=1', '--env=TRANSFORMERS_OFFLINE=1',
            image, '/usr/local/bin/python', '-I', '/repair-tool.py', 'container']


def bounded_process(command, *, cwd=None, env=None, timeout=900, maximum=MAX_LOG_BYTES):
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
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
    match = re.search(r'Ran (\d+) tests? in [0-9.]+s', output)
    counts = {key: int(value) for key, value in re.findall(r'(failures|errors|skipped)=(\d+)', output)}
    tests = int(match.group(1)) if match else 0
    failures = counts.get('failures', 0)
    errors = counts.get('errors', 0)
    skipped = counts.get('skipped', 0)
    passed = returncode == 0 and tests > 0 and not (failures or errors or skipped) and bool(re.search(r'^OK\s*$', output, re.M))
    if require_failure and not (returncode != 0 and tests > 0 and failures > 0 and errors == 0 and skipped == 0):
        raise ValueError('Baseline must reproduce a real assertion failure, not an empty, skipped or broken test run.')
    return {'tests': tests, 'failures': failures, 'errors': errors, 'skipped': skipped,
            'passed': passed, 'returncode': returncode, 'log_sha256': hashlib.sha256(output.encode()).hexdigest()}


def run_suite(workspace, plan, stage, *, require_failure=False):
    if stage not in ('unit', 'integration'):
        raise ValueError('Use the fixed unit or integration stage.')
    workspace = Path(workspace)
    env = clean_environment()
    temp = workspace / '.local/operator-test-temp'
    temp.mkdir(parents=True, exist_ok=True)
    env.update(TMP=str(temp), TEMP=str(temp), TMPDIR=str(temp), HOME=str(temp))
    if plan['profile'] == 'synthetic-stdlib':
        command = [sys.executable, '-I', '-m', 'unittest', 'discover', '-s',
                   'tests/fixtures/support_repair', '-p', 'test_' + stage + '.py', '-v']
    else:
        command = [sys.executable, 'scripts/run_backend_tests.py', *plan[stage + '_labels'], '--verbosity', '1']
    output, code = bounded_process(command, cwd=workspace, env=env)
    return test_result(output, code, require_failure=require_failure)


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
    work = Path('/work')
    (work / 'home').mkdir(exist_ok=True)
    baseline = extract_source(directory / 'baseline.zip', work / 'baseline')
    candidate = extract_source(directory / 'candidate.zip', work / 'candidate')
    stages = {}
    for stage in ('unit', 'integration'):
        stages['baseline_' + stage] = run_suite(baseline, plan, stage, require_failure=True)
        stages['candidate_' + stage] = run_suite(candidate, plan, stage)
        if stages['candidate_' + stage]['passed'] is not True:
            raise ValueError('Candidate ' + stage + ' tests did not pass; the repair remains unverified.')
    proof = {'baseline_failed': True, 'patched_passed': True, 'unit_passed': True,
             'integration_passed': True, 'isolation': 'docker-no-network', 'execution_id': str(uuid.uuid4())}
    print(json.dumps({'receipt': receipt(plan, proof), 'stages': stages,
                      'isolation_checks': isolation}, sort_keys=True))


def run(directory, image):
    directory = no_links(directory)
    plan = validate_plan(directory)
    if (directory / 'repair-receipt.json').exists() or (directory / 'execution.json').exists():
        raise ValueError('This immutable attempt already has evidence. Do not overwrite a completed attempt.')
    docker_preflight(image)
    name = 'isurvix-support-' + uuid.uuid4().hex
    command = docker_command(directory, image, name, uid=os.getuid(), gid=os.getgid())
    try:
        output, code = bounded_process(command, timeout=1800, maximum=131072)
        if code != 0:
            raise ValueError('Isolated regression/unit/integration checks failed; no successful receipt was written.')
        evidence = json.loads(output)
        checks = evidence.get('isolation_checks')
        if (not isinstance(checks, dict)
                or set(checks) != {'network_blocked', 'inputs_readonly', 'credentials_absent', 'docker_socket_absent'}
                or any(value is not True for value in checks.values())):
            raise ValueError('The isolated run did not supply successful network/file/credential probes.')
        saved = validate_receipt(evidence['receipt'])
        expected = receipt(plan, saved['test_evidence'])
        if saved != expected or not isinstance(evidence.get('stages'), dict):
            raise ValueError('The returned isolated evidence names a different repair.')
        for stage in ('baseline_unit', 'baseline_integration', 'candidate_unit', 'candidate_integration'):
            result = evidence['stages'].get(stage)
            if not isinstance(result, dict) or type(result.get('tests')) is not int or result['tests'] < 1:
                raise ValueError('The required isolated test stage is missing.')
            if stage.startswith('candidate') and result.get('passed') is not True:
                raise ValueError('The required isolated test stage did not pass.')
        metadata = {'format': 'isurvix-support-execution-v1', 'image': image, 'network': 'none',
                    'production_mounts': False, 'credentials_forwarded': False,
                    'created_utc': datetime.now(timezone.utc).isoformat(), **evidence}
        (directory / 'execution.json').write_bytes(canonical(metadata))
        (directory / 'repair-receipt.json').write_bytes(canonical(saved))
        return saved
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        raise ValueError('The isolated repair did not return complete valid evidence.') from None
    finally:
        # The generated container identity is exact, not a user-selected target.
        # A timed-out Docker client must not leave the candidate process running.
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20)


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
        else:
            container_run()
            return 0
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
