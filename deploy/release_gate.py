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
    latest = {}
    for run in runs:
        if not isinstance(run, dict) or run.get('path') not in REQUIRED_WORKFLOWS:
            continue
        head_repository = run.get('head_repository')
        if run.get('head_sha') != release_id or not isinstance(head_repository, dict) or head_repository.get('full_name') != repository:
            continue
        path = run['path']
        if any(type(run.get(key)) is not int or run[key] < 1 for key in ('id', 'run_number', 'run_attempt')):
            raise ValueError('A required workflow has incomplete provenance.')
        try:
            updated = datetime.fromisoformat(run['updated_at'].replace('Z', '+00:00'))
            if updated.tzinfo is None:
                raise ValueError()
        except (KeyError, TypeError, AttributeError, ValueError):
            raise ValueError('A required workflow has no reliable update time.') from None
        # Re-running an older run number can be more recent than another run.
        order = (updated, run['run_attempt'], run['run_number'], run['id'])
        if path not in latest or order > latest[path][0]:
            latest[path] = order, run
    result = {}
    for path in REQUIRED_WORKFLOWS:
        run = latest.get(path, (None, {}))[1]
        if run.get('status') != 'completed':
            raise ChecksPending('A required same-source check is missing or unfinished; candidate publication is blocked.')
        if run.get('conclusion') != 'success':
            raise ValueError('A required same-source check is missing, unfinished or unsuccessful; candidate publication is blocked.')
        result[path] = {'run_id': run['id'], 'run_attempt': run['run_attempt'],
                        'source_commit': release_id, 'status': 'completed', 'conclusion': 'success',
                        'url': f'https://github.com/{repository}/actions/runs/{run["id"]}'}
    return result


def _checks(checks, release_id):
    if not isinstance(checks, dict) or set(checks) != set(REQUIRED_WORKFLOWS):
        raise ValueError('All required same-source checks must be present.')
    for value in checks.values():
        if (not isinstance(value, dict) or value.get('source_commit') != release_id
                or value.get('status') != 'completed' or value.get('conclusion') != 'success'
                or type(value.get('run_id')) is not int or value['run_id'] < 1
                or type(value.get('run_attempt')) is not int or value['run_attempt'] < 1):
            raise ValueError('A required same-source check is not verified.')


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('check')
    check.add_argument('--repository', required=True)
    check.add_argument('--release-id', required=True)
    check.add_argument('--output', type=Path, required=True)
    check.add_argument('--wait-seconds', type=int, default=0)
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
