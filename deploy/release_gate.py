"""Fail-closed, same-source candidate publication; never grants release approval.

One verified customer bundle supplies the SAME application image to both editions.
GitHub credentials are read from the environment and never written into records.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler


REQUIRED_WORKFLOWS = (
    '.github/workflows/repair-validation.yml',
    '.github/workflows/staging-verification.yml',
    '.github/workflows/customer-server-verification.yml',
)
FORMAT = 'isurvix-shared-release-v1'


class ChecksPending(ValueError):
    """A bounded orchestration wait is permitted only for unfinished checks."""


def _sha(value, length=40):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{%d}' % length, value):
        raise ValueError('Use an exact immutable source or content identity.')
    return value


def verified_runs(runs, release_id, repository):
    _sha(release_id)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Use the expected owner/repository identity.')
    latest = {path: {} for path in REQUIRED_WORKFLOWS}
    terminal_conclusions = {}
    run_paths = {}
    for run in runs:
        if not isinstance(run, dict) or run.get('path') not in REQUIRED_WORKFLOWS:
            continue
        head_repository = run.get('head_repository')
        if run.get('head_sha') != release_id or not isinstance(head_repository, dict) or head_repository.get('full_name') != repository:
            continue
        path = run['path']
        if any(type(run.get(key)) is not int or run[key] < 1 for key in ('id', 'run_number', 'run_attempt')):
            raise ValueError('A required workflow has incomplete provenance.')
        if run['id'] in run_paths and run_paths[run['id']] != path:
            raise ValueError('A required run identity names contradictory workflow paths.')
        run_paths[run['id']] = path
        try:
            updated = datetime.fromisoformat(run['updated_at'].replace('Z', '+00:00'))
            if updated.tzinfo is None:
                raise ValueError()
        except (KeyError, TypeError, AttributeError, ValueError):
            raise ValueError('A required workflow has no reliable update time.') from None
        # A completed attempt cannot acquire a different outcome merely by
        # receiving a later timestamp. Preserve this evidence across snapshots
        # even when a newer attempt has already appeared on another page.
        if run.get('status') == 'completed':
            identity = (path, run['id'], run['run_attempt'])
            if identity in terminal_conclusions and terminal_conclusions[identity] != run.get('conclusion'):
                raise ValueError('A required workflow has contradictory terminal conclusions; publication is blocked.')
            terminal_conclusions[identity] = run.get('conclusion')
        # Independent push/PR runs must all pass. An updated older success must
        # never hide another run that is still active or has failed. Only a
        # newer attempt of the SAME run can supersede that run's old failure.
        order = (run['run_attempt'], updated)
        previous = latest[path].get(run['id'])
        if previous is not None:
            previous_order, previous_run = previous
            if previous_run['run_number'] != run['run_number']:
                raise ValueError('A required workflow has contradictory run provenance.')
            if order == previous_order and any(
                    previous_run.get(key) != run.get(key) for key in ('status', 'conclusion')):
                raise ValueError('A required workflow has contradictory status snapshots; publication is blocked.')
        if previous is None or order > previous[0]:
            latest[path][run['id']] = order, run
    result = {}
    for path in REQUIRED_WORKFLOWS:
        effective = list(latest[path].values())
        for _, run in effective:
            if run.get('status') == 'completed' and run.get('conclusion') != 'success':
                raise ValueError('A required same-source check is unsuccessful; candidate publication is blocked.')
        if not effective or any(run.get('status') != 'completed' for _, run in effective):
            raise ChecksPending('A required same-source check is missing or unfinished; candidate publication is blocked.')
        # Retain the existing single canonical artifact-run identity and v1
        # record shape, after every independent latest attempt is verified.
        _, run = max(effective, key=lambda item: (
            item[0][1], item[1]['run_attempt'], item[1]['run_number'], item[1]['id']))
        result[path] = {'run_id': run['id'], 'run_attempt': run['run_attempt'],
                        'source_commit': release_id, 'status': 'completed', 'conclusion': 'success',
                        'url': f'https://github.com/{repository}/actions/runs/{run["id"]}'}
    return result


def _checks(checks, release_id):
    if not isinstance(checks, dict) or set(checks) != set(REQUIRED_WORKFLOWS):
        raise ValueError('All required same-source checks must be present.')
    run_ids = set()
    for value in checks.values():
        if (not isinstance(value, dict) or value.get('source_commit') != release_id
                or value.get('status') != 'completed' or value.get('conclusion') != 'success'
                or type(value.get('run_id')) is not int or value['run_id'] < 1
                or type(value.get('run_attempt')) is not int or value['run_attempt'] < 1):
            raise ValueError('A required same-source check is not verified.')
        if value['run_id'] in run_ids:
            raise ValueError('Each required workflow must have its own verified run identity.')
        run_ids.add(value['run_id'])


def confirm_gate_pair(original, fresh):
    release = _sha(original.get('source_commit'))
    _checks(original.get('required_checks'), release)
    if fresh.get('source_commit') != release:
        raise ValueError('The final gate names another source release.')
    _checks(fresh.get('required_checks'), release)
    if original['required_checks'] != fresh['required_checks']:
        raise ValueError('Required run identities or attempts changed during artifact transfer. Obtain the verified artifacts again.')
    try:
        observed = datetime.fromisoformat(fresh['observed_utc'])
        age = (datetime.now(timezone.utc) - observed).total_seconds()
        if not 0 <= age <= 120:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise ValueError('Final check observation is missing or stale; recheck immediately before candidate assembly.') from None


def release_record(manifest, manifest_sha256, checks, proof):
    release = _sha(manifest.get('release_id'))
    _sha(manifest_sha256, 64)
    _checks(checks, release)
    if manifest.get('status') != 'draft-for-review' or manifest.get('owner_release_approved') is not False:
        raise ValueError('Only an explicitly unapproved review candidate can be assembled.')
    supported = proof.get('supported_from')
    if (proof.get('release') != release or proof.get('fresh_install') is not True
            or proof.get('restart_preserved_db_and_media') is not True
            or proof.get('upgrade_recovery_verified') is not True
            or type(proof.get('runtime_image_pulls')) is not int or proof['runtime_image_pulls'] != 0
            or not isinstance(supported, list) or not supported or len(set(supported)) != len(supported)):
        raise ValueError('The actual install/upgrade/recovery proof is missing or incompatible.')
    for source in supported:
        _sha(source)
        if source == release:
            raise ValueError('A same-version restart is not an upgrade proof.')
    images = manifest.get('images')
    if not isinstance(images, dict) or set(images) != {'app', 'nginx'}:
        raise ValueError('Both editions require the same immutable application and proxy identities.')
    for image in images.values():
        if not isinstance(image, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
            raise ValueError('Mutable image tags cannot be published.')
    if proof.get('images') != images or proof.get('manifest_sha256') != manifest_sha256:
        raise ValueError('Installation/upgrade proof names different artifact bytes or image identities.')
    return {'format': FORMAT, 'source_commit': release, 'manifest_sha256': manifest_sha256,
            'images': images, 'editions': ['cloud', 'customer'], 'supported_from': supported,
            'required_checks': checks, 'candidate_only': True, 'owner_release_approved': False,
            'created_utc': datetime.now(timezone.utc).isoformat(),
            'approval_holds': manifest.get('approval_holds', []),
            'verification': {key: proof[key] for key in ('release', 'fresh_install', 'runtime_image_pulls',
                'restart_preserved_db_and_media', 'upgrade_recovery_verified', 'supported_from', 'images', 'manifest_sha256')},
            'trust_notice': 'Use a trusted catalog and independently delivered digest. This record does not grant licence or deployment approval.'}


def publish_record(path, record):
    if (not isinstance(record, dict) or record.get('format') != FORMAT
            or record.get('owner_release_approved') is not False or record.get('candidate_only') is not True):
        raise ValueError('A verified unapproved candidate record is required.')
    _sha(record.get('source_commit'))
    _sha(record.get('manifest_sha256'), 64)
    _checks(record.get('required_checks'), record['source_commit'])
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write('\n')


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Release-check requests never forward credentials to another URL.')


def _api(path, token):
    if not path.startswith('/repos/') or '\r' in path or '\n' in path:
        raise ValueError('Invalid repository API path.')
    if not isinstance(token, str) or not token or any(ord(char) < 32 or ord(char) == 127 for char in token):
        raise ValueError('The scoped Actions-read credential is unavailable or invalid.')
    request = Request('https://api.github.com' + path, headers={
        'Accept': 'application/vnd.github+json', 'Authorization': 'Bearer ' + token,
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'iSurvix-release-gate'})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=30) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError('Release-check response exceeds the bounded limit.')
            return json.loads(raw)
    except (HTTPError, URLError, UnicodeError, json.JSONDecodeError):
        raise ValueError('GitHub verification is unavailable or unauthorized; publication remains blocked.') from None


def fetch_verified(repository, release_id, token):
    _sha(release_id)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Use the expected owner/repository identity.')
    if not token:
        raise ValueError('A scoped Actions-read credential is required for release verification.')
    runs = []
    for page in range(1, 11):
        payload = _api(f'/repos/{repository}/actions/runs?head_sha={release_id}&per_page=100&page={page}', token)
        batch = payload.get('workflow_runs') if isinstance(payload, dict) else None
        if not isinstance(batch, list):
            raise ValueError('GitHub returned an invalid workflow record.')
        runs.extend(batch)
        if len(batch) < 100:
            return verified_runs(runs, release_id, repository)
    raise ValueError('Too many workflow records to establish complete release provenance.')



def _artifact_time(value):
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        if result.tzinfo is None:raise ValueError()
        return result
    except (AttributeError,TypeError,ValueError):
        raise ValueError('Artifact attempt has no reliable UTC time.') from None


def select_attempt_artifacts(run,jobs,artifacts,*,repository,release_id,run_id,run_attempt):
    """IDs are opaque; only immutable creation inside the verified job binds an attempt."""
    _sha(release_id)
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository)
            or any(type(v) is not int or v<1 for v in (run_id,run_attempt))):
        raise ValueError('Invalid artifact source identity.')
    if (not isinstance(run,dict) or run.get('id')!=run_id or run.get('run_attempt')!=run_attempt
            or run.get('head_sha')!=release_id or run.get('path')!=REQUIRED_WORKFLOWS[2]
            or run.get('status')!='completed' or run.get('conclusion')!='success'):
        raise ValueError('Artifact attempt is not the verified successful customer run.')
    repository_ids=[]
    for key in ('repository','head_repository'):
        value=run.get(key)
        if (not isinstance(value,dict) or value.get('full_name')!=repository
                or type(value.get('id')) is not int or value['id']<1):
            raise ValueError('Artifact attempt repository differs.')
        repository_ids.append(value['id'])
    if not isinstance(jobs,list) or not isinstance(artifacts,list):
        raise ValueError('Artifact listing is incomplete.')
    matching=[]
    for job in jobs:
        if not isinstance(job,dict):raise ValueError('Invalid artifact job record.')
        if job.get('name')!='disposable-linux':continue
        if (job.get('run_id')!=run_id or job.get('run_attempt')!=run_attempt
                or job.get('head_sha')!=release_id or job.get('status')!='completed'
                or job.get('conclusion')!='success'):
            raise ValueError('Artifact job does not belong to the successful attempt.')
        matching.append(job)
    if len(matching)!=1:raise ValueError('Artifact job window is missing or ambiguous.')
    start=_artifact_time(matching[0].get('started_at'));end=_artifact_time(matching[0].get('completed_at'))
    if end<start:raise ValueError('Artifact job time window is invalid.')
    names={'customer-server-DRAFT-candidate':'candidate_artifact_id','customer-server-verification':'verification_artifact_id'}
    selected={};seen=set()
    for artifact in artifacts:
        if not isinstance(artifact,dict):raise ValueError('Invalid artifact record.')
        if artifact.get('name') not in names:continue
        created=_artifact_time(artifact.get('created_at'))
        if not start<=created<=end:continue
        identity=artifact.get('id');source=artifact.get('workflow_run')
        if (type(identity) is not int or identity<1 or identity in seen or artifact.get('expired') is not False
                or not isinstance(source,dict) or source.get('id')!=run_id or source.get('head_sha')!=release_id
                or source.get('repository_id')!=repository_ids[0] or source.get('head_repository_id')!=repository_ids[1]):
            raise ValueError('Artifact provenance or availability differs.')
        key=names[artifact['name']]
        if key in selected:raise ValueError('Artifact name is ambiguous within the verified attempt.')
        seen.add(identity);selected[key]=identity
    if set(selected)!=set(names.values()):raise ValueError('Verified attempt artifacts are missing; publication remains blocked.')
    return selected


def fetch_attempt_artifacts(repository,release_id,run_id,run_attempt,token):
    _sha(release_id)
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository)
            or any(type(v) is not int or v<1 for v in (run_id,run_attempt))):
        raise ValueError('Invalid artifact source identity.')
    base=f'/repos/{repository}/actions/runs/{run_id}'
    run=_api(base+f'/attempts/{run_attempt}',token)
    def pages(path,key):
        values=[]
        for page in range(1,11):
            payload=_api(path+f'?per_page=100&page={page}',token)
            batch=payload.get(key) if isinstance(payload,dict) else None
            if not isinstance(batch,list):raise ValueError('Invalid complete artifact listing.')
            values.extend(batch)
            if len(batch)<100:return values
        raise ValueError('Too many artifact records to establish complete provenance.')
    jobs=pages(base+f'/attempts/{run_attempt}/jobs','jobs')
    artifacts=pages(base+'/artifacts','artifacts')
    return select_attempt_artifacts(run,jobs,artifacts,repository=repository,release_id=release_id,run_id=run_id,run_attempt=run_attempt)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('check')
    check.add_argument('--repository', required=True)
    check.add_argument('--release-id', required=True)
    check.add_argument('--output', type=Path, required=True)
    check.add_argument('--wait-seconds', type=int, default=0)
    artifacts = commands.add_parser('artifacts')
    artifacts.add_argument('--repository', required=True)
    artifacts.add_argument('--gate', type=Path, required=True)
    artifacts.add_argument('--output', type=Path, required=True)
    record = commands.add_parser('record')
    for name in ('package', 'gate', 'fresh-gate', 'verification', 'output'):
        record.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'check':
            if not 0 <= args.wait_seconds <= 1800:
                raise ValueError('Use a bounded wait of at most1800 seconds.')
            deadline = time.monotonic() + args.wait_seconds
            while True:
                try:
                    checks = fetch_verified(args.repository, args.release_id, os.environ.get('GITHUB_TOKEN', ''))
                    break
                except ChecksPending:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(min(20, max(0, deadline - time.monotonic())))
            result = {'source_commit': args.release_id, 'required_checks': checks,
                      'observed_utc': datetime.now(timezone.utc).isoformat(),
                      'customer_run_id': checks[REQUIRED_WORKFLOWS[2]]['run_id']}
            with args.output.open('x', encoding='utf-8') as stream:
                json.dump(result, stream, indent=2)
            print(json.dumps({'eligible': True, 'customer_run_id': result['customer_run_id']}))
        elif args.command == 'artifacts':
            gate = json.loads(args.gate.read_text(encoding='utf-8'))
            _checks(gate['required_checks'], gate['source_commit'])
            customer = gate['required_checks'][REQUIRED_WORKFLOWS[2]]
            if gate['customer_run_id'] != customer['run_id']:raise ValueError('Customer run binding differs.')
            result = fetch_attempt_artifacts(args.repository, gate['source_commit'], customer['run_id'], customer['run_attempt'], os.environ.get('GITHUB_TOKEN', ''))
            result['run_id'] = customer['run_id']
            with args.output.open('x', encoding='utf-8') as stream:json.dump(result, stream, indent=2)
        else:
            spec = importlib.util.spec_from_file_location('installed_customer_verifier', Path(__file__).parent / 'customer/customer.py')
            customer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(customer)
            manifest = customer.verify_package(args.package)
            gate = json.loads(args.gate.read_text(encoding='utf-8'))
            fresh = json.loads(args.fresh_gate.read_text(encoding='utf-8'))
            confirm_gate_pair(gate, fresh)
            proof = json.loads(args.verification.read_text(encoding='utf-8'))
            if gate.get('source_commit') != manifest['release_id']:
                raise ValueError('The selected package and verified checks differ.')
            digest = hashlib.sha256((args.package / 'manifest.json').read_bytes()).hexdigest()
            result = release_record(manifest, digest, gate['required_checks'], proof)
            result['ci_observed_utc'] = fresh['observed_utc']
            publish_record(args.output, result)
            print(json.dumps({'candidate_record_written': True, 'source_commit': result['source_commit'], 'owner_release_approved': False}))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
