"""Actual file/JSON process boundary and unchanged source evidence reference."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class EvidenceFlowTests(unittest.TestCase):
    def test_saved_links_cross_cli_without_modifying_input(self):
        root = Path(__file__).resolve().parents[3]
        temporary = root / '.local/synthetic-repair-tests'
        temporary.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary) as directory:
            source, target = Path(directory)/'links.json', Path(directory)/'result.json'
            source.write_text(json.dumps({'links': [
                {'photo_id': 'p1', 'field_id': 'civil-1'},
                {'photo_id': 'p1', 'field_id': 'tower-1'},
                {'photo_id': 'p2', 'field_id': 'tower-1'},
            ]}), encoding='utf-8')
            original = source.read_bytes()
            subprocess.run([sys.executable, str(Path(__file__).with_name('counter.py')),
                            str(source), str(target)], check=True, timeout=10)
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')),
                             {'unique_photos': 2, 'links': 3})
            self.assertEqual(source.read_bytes(), original)
