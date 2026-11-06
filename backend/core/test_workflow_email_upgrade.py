"""Actual workflow-mail migration must preserve rows and strict metadata rules."""
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile

from django.test import SimpleTestCase

from .test_invitation_email_upgrade import BUILD, ROOT


class WorkflowMailUpgradeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        parent = ROOT / '.local/workflow-mail-upgrade-tests'
        parent.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(dir=parent)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        build = BUILD.replace("call_command('migrate','core','0060_invitation_email_delivery'",
                              "call_command('migrate','core','0061_workflow_email_delivery'")
        for source in ('0059_task_page_indexes', '0060_invitation_email_delivery'):
            work = cls.root / source
            work.mkdir()
            result = subprocess.run([sys.executable, '-c', build, str(ROOT), str(work), source],
                                    capture_output=True, text=True, timeout=90)
            if result.returncode:
                raise AssertionError('Isolated workflow migration failed: ' + result.stderr[-1800:])
            (work/'observation.json').write_text(result.stdout, encoding='utf-8')

    def fixture(self, source='0060_invitation_email_delivery'):
        spec = importlib.util.spec_from_file_location('workflow_retention', ROOT/'deploy/customer/upgrade_fixture.py')
        proof = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(proof)
        work = self.root/source
        target = self.root/(self._testMethodName+'.sqlite3')
        shutil.copyfile(work/'target.sqlite3', target)
        return proof, json.loads((work/'before.json').read_text()), target, work

    def test_actual_0060_upgrade_preserves_rows_and_adds_only_workflow_defaults(self):
        proof, before, target, work = self.fixture()
        self.assertEqual(json.loads((work/'observation.json').read_text()),
                         {'content_types_added': 1, 'permissions_added': 4})
        proof.assert_retained(before, target)

    def test_live_0059_upgrade_preserves_rows_with_both_empty_outboxes(self):
        proof, before, target, work = self.fixture('0059_task_page_indexes')
        self.assertEqual(json.loads((work/'observation.json').read_text()),
                         {'content_types_added': 2, 'permissions_added': 8})
        proof.assert_retained(before, target)

    def test_workflow_metadata_cannot_relax_historical_permissions_or_upgrade_evidence(self):
        for mutation in (
            "DELETE FROM django_migrations WHERE app='core' AND name='0061_workflow_email_delivery'",
            "DROP TABLE core_workflowemaildelivery",
            "UPDATE auth_permission SET id=-id WHERE content_type_id IN (SELECT id FROM django_content_type WHERE app_label='core' AND model='workflowemaildelivery')",
            "UPDATE auth_permission SET name='Invented permission' WHERE codename='change_workflowemaildelivery'",
            "UPDATE auth_user SET is_superuser=1",
            "INSERT INTO django_content_type(app_label,model) VALUES('core','unapproved_notification_role')",
        ):
            with self.subTest(mutation=mutation):
                proof, before, target, work = self.fixture()
                with closing(sqlite3.connect(target)) as db, db:
                    db.execute(mutation)
                with self.assertRaises(ValueError):
                    proof.assert_retained(before, target)
