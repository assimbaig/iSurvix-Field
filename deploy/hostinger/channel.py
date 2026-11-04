"""Public deployment provenance only: never store runtime data or credentials here."""
import argparse
import json
from pathlib import Path
import re

REPOSITORY = 'assimbaig/iSurvix-Field'
BRANCH = 'feat/ai-settings-routing-20261031'
KEYS = {'format', 'repository', 'branch', 'source_commit', 'merge_commit',
        'source_schema', 'manifest_sha256', 'artifact_id', 'artifact_sha256', 'images'}


def _digest(value, size):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{%d}' % size, value)


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
    baseline = sub.add_parser('baseline')
    baseline.add_argument('--record', type=Path, required=True)
    baseline.add_argument('--github-output', type=Path, required=True)
    update = sub.add_parser('record')
    update.add_argument('--previous', type=Path, required=True)
    update.add_argument('--receipt', type=Path, required=True)
    update.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == 'baseline':
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
