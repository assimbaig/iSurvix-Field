"""Support-only changes must schedule the real shared candidate's prerequisite runs."""
import fnmatch
import importlib.util
import json
from pathlib import Path
import re

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]


class SupportDeliveryPathsTests(SimpleTestCase):
    def test_advertised_upgrade_schema_matches_the_actual_migration_graph(self):
        from django.db.migrations.loader import MigrationLoader
        record = json.loads((ROOT / 'deploy/customer/supported-upgrades.json').read_text())
        leaves = MigrationLoader(None).graph.leaf_nodes('core')
        self.assertEqual(len(leaves), 1)
        self.assertEqual(record['target_schema'], leaves[0][1])

    def test_support_changes_schedule_every_required_exact_source_workflow(self):
        spec = importlib.util.spec_from_file_location('support_release_gate', ROOT / 'deploy/release_gate.py')
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        sha = 'a' * 40
        files = [
            'backend/core/support_service.py',
            'backend/core/test_support_backend.py',
            'backend/templates/support/index.html',
            'scripts/support_repair.py',
            '.github/workflows/support-repair-verification.yml',
            'backend/core/migrations/0058_support_cases.py',
        ]
        for changed in files:
            with self.subTest(changed=changed):
                scheduled = []
                for index, workflow in enumerate(gate.REQUIRED_WORKFLOWS, 1):
                    text = (ROOT / workflow).read_text(encoding='utf-8')
                    trigger = text.split('permissions:', 1)[0]
                    patterns = re.findall(r"^      - '([^']+)'$", trigger, re.M)
                    if not patterns or any(fnmatch.fnmatchcase(changed, pattern) for pattern in patterns):
                        scheduled.append(dict(id=index, run_number=1, run_attempt=1,
                            head_sha=sha, path=workflow, status='completed', conclusion='success',
                            updated_at='2026-11-02T12:00:00Z',
                            head_repository={'full_name': 'assimbaig/iSurvix-Field'}))
                result = gate.verified_runs(scheduled, sha, 'assimbaig/iSurvix-Field')
                self.assertEqual(set(result), set(gate.REQUIRED_WORKFLOWS))
                self.assertTrue(all(item['source_commit'] == sha for item in result.values()))
