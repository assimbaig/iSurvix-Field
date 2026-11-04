"""Prevent a candidate's update rehearsal from claiming a stale schema target."""
import json
from pathlib import Path
import yaml

from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]


class ReleaseSchemaContractTests(SimpleTestCase):
    def test_candidate_rehearsal_target_matches_actual_migration_graph(self):
        leaves = MigrationLoader(None).graph.leaf_nodes('core')
        self.assertEqual(len(leaves), 1, 'An upgrade candidate needs an unambiguous core schema')
        record = json.loads((ROOT / 'deploy/customer/supported-upgrades.json').read_text())
        self.assertEqual(record['target_schema'], leaves[0][1])

    def test_migration_changes_run_both_disposable_deployment_gates(self):
        for name in ['staging-verification.yml', 'customer-server-verification.yml']:
            with self.subTest(workflow=name):
                workflow = (ROOT / '.github/workflows' / name).read_text()
                triggers = yaml.load(workflow, Loader=yaml.BaseLoader)['on']
                self.assertIn('pull_request', triggers)
                # CS1 removed the old migration-only whitelist. An unrestricted
                # PR gate includes every migration, UI and operations change.
                self.assertEqual(triggers['pull_request'] or {}, {},
                                 'Every PR must run migration/deployment gates without filters')
