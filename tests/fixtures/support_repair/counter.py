"""SYNTHETIC SUPPORT ACCEPTANCE FIXTURE ONLY. Never used by the application."""
import json
import sys
from pathlib import Path


def count_unique(values):
    return len(values)


def main():
    data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    values = [item['photo_id'] for item in data['links']]
    Path(sys.argv[2]).write_text(json.dumps({
        'unique_photos': count_unique(values), 'links': len(data['links']),
    }), encoding='utf-8')


if __name__ == '__main__':
    main()
