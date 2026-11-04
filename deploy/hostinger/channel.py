"""Public deployment provenance only: never store runtime data or credentials here."""
import argparse
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

REPOSITORY = 'assimbaig/iSurvix-Field'
BRANCH = 'feat/ai-settings-routing-20261031'
KEYS = {'format', 'repository', 'branch', 'source_commit', 'merge_commit',
        'source_schema', 'manifest_sha256', 'artifact_id', 'artifact_sha256', 'images'}


def _digest(value, size):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{%d}' % size, value)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class GitHubReader:
    """Fixed-origin, bounded GitHub reads; never return transport response bodies."""
    def __init__(self, token, open_request=None):
        if not isinstance(token, str) or not token.strip() or '\r' in token or '\n' in token:
            raise ValueError('A private GitHub job token is required')
        self._token = token
        self._open = open_request or urllib.request.build_opener(_NoRedirect()).open

    def __call__(self, path):
        if (not isinstance(path, str) or not path.startswith('/repos/' + REPOSITORY + '/')
                or any(value in path for value in ('..', '\r', '\n', '#', '//'))):
            raise ValueError('Unexpected GitHub API path')
        request = urllib.request.Request('https://api.github.com' + path, headers={
            'Authorization': 'Bearer ' + self._token, 'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'iSurvix-Trusted-Push-Resolver'})
        try:
            with self._open(request, timeout=15) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise ValueError('GitHub response exceeds the supported size')
                return json.loads(raw)
        except (OSError, ValueError, urllib.error.HTTPError):
            raise ValueError('GitHub PR resolution failed; check job read permissions and retry') from None


def _at(record, *keys):
    for key in keys:
        if not isinstance(record, dict):
            return None
        record = record.get(key)
    return record


def resolve_merged_pr(commit, get):
    """Bind a trusted branch push to exactly one canonical, same-repo merged PR.

    This admission step grants no owner approval. The installed receiver repeats
    owner, current-branch, source-tree, CI, artifact and upgrade authorization.
    """
    if not _digest(commit, 40):
        raise ValueError('Invalid pushed commit identity')
    candidates, seen = [], set()
    prefix = '/repos/' + REPOSITORY
    for page in range(1, 11):
        rows = get(prefix + '/commits/' + commit + '/pulls?per_page=100&page=' + str(page))
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError('Invalid commit-associated PR response')
        for row in rows:
            number = _at(row, 'number')
            if type(number) is not int or number <= 0 or number in seen:
                raise ValueError('Invalid or duplicate commit-associated PR')
            seen.add(number)
            pr = get(prefix + '/pulls/' + str(number))
            if type(_at(pr, 'number')) is not int or _at(pr, 'number') != number:
                raise ValueError('Canonical PR identity does not match the commit association')
            if (pr.get('state') == 'closed' and pr.get('merged') is True and pr.get('merged_at')
                    and pr.get('merge_commit_sha') == commit
                    and _at(pr, 'head', 'repo', 'full_name') == REPOSITORY
                    and _at(pr, 'base', 'repo', 'full_name') == REPOSITORY
                    and _at(pr, 'base', 'ref') == BRANCH):
                candidates.append(number)
        if len(rows) < 100:
            break
    else:
        raise ValueError('Commit-associated PR list exceeds the supported bound')
    if len(candidates) != 1:
        raise ValueError('Push must identify exactly one merged same-repository release-branch PR')
    return candidates[0]


def validate(record):
    if not isinstance(record, dict) or set(record) != KEYS:
        raise ValueError('Unexpected deployment-channel fields')
    if (record['format'] != 'isurvix-hostinger-channel-v1' or
            record['repository'] != REPOSITORY or record['branch'] != BRANCH):
        raise ValueError('Wrong deployment channel')
    for key in ('source_commit', 'merge_commit'):
        if not _digest(record[key], 40):
            raise ValueError('Invalid commit identity')
    for key in ('manifest_sha256', 'artifact_sha256'):
        if not _digest(record[key], 64):
            raise ValueError('Invalid artifact identity')
    if type(record['artifact_id']) is not int or record['artifact_id'] <= 0:
        raise ValueError('Invalid artifact ID')
    if not isinstance(record['source_schema'], str) or not re.fullmatch(r'\d{4}_[a-z0-9_]{1,100}', record['source_schema']):
        raise ValueError('Invalid schema identity')
    images = record['images']
    if not isinstance(images, dict) or set(images) != {'app', 'nginx'}:
        raise ValueError('Invalid image identities')
    for value in images.values():
        if not isinstance(value, str) or not value.startswith('sha256:') or not _digest(value[7:], 64):
            raise ValueError('Invalid image digest')
    return record.copy()


def from_receipt(previous, receipt):
    previous = validate(previous)
    if receipt.get('format') != 'isurvix-hostinger-receipt-v1' or receipt.get('status') not in {'completed', 'already_running'}:
        raise ValueError('The server did not confirm a completed deployment')
    updated = validate({'format': previous['format'], 'repository': REPOSITORY, 'branch': BRANCH,
                        'source_commit': receipt.get('release'), 'merge_commit': receipt.get('merge_sha'),
                        'source_schema': receipt.get('core_schema'), 'manifest_sha256': receipt.get('manifest_sha256'),
                        'artifact_id': receipt.get('artifact_id'), 'artifact_sha256': receipt.get('artifact_sha256'),
                        'images': receipt.get('images')})
    if updated == previous:
        return previous  # replay after the bookkeeping push already succeeded
    if receipt.get('source_release') != previous['source_commit']:
        raise ValueError('Deployment receipt does not continue the recorded channel')
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    resolve = sub.add_parser('resolve-pr')
    resolve.add_argument('--commit', required=True)
    resolve.add_argument('--github-output', type=Path, required=True)
    baseline = sub.add_parser('baseline')
    baseline.add_argument('--record', type=Path, required=True)
    baseline.add_argument('--github-output', type=Path, required=True)
    update = sub.add_parser('record')
    update.add_argument('--previous', type=Path, required=True)
    update.add_argument('--receipt', type=Path, required=True)
    update.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == 'resolve-pr':
            number = resolve_merged_pr(args.commit, GitHubReader(os.environ.get('GITHUB_TOKEN')))
            with args.github_output.open('a', encoding='utf-8', newline='\n') as output:
                output.write('pr=' + str(number) + '\n')
        elif args.action == 'baseline':
            value = validate(json.loads(args.record.read_text(encoding='utf-8')))
            with args.github_output.open('a', encoding='utf-8', newline='\n') as output:
                output.write('source_commit=' + value['source_commit'] + '\nsource_schema=' + value['source_schema'] + '\n')
        else:
            value = from_receipt(json.loads(args.previous.read_text(encoding='utf-8')),
                                 json.loads(args.receipt.read_text(encoding='utf-8')))
            args.output.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    except (ValueError, OSError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
