"""Actual additive notice migration and strict retained-data upgrade proof."""
from contextlib import closing
import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile

from django.test import SimpleTestCase

from .test_invitation_email_upgrade import BUILD,ROOT


class ReleaseNoticeUpgradeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        parent=ROOT/'.local/release-notice-upgrade-tests';parent.mkdir(parents=True,exist_ok=True)
        cls.temporary=tempfile.TemporaryDirectory(dir=parent);cls.addClassCleanup(cls.temporary.cleanup)
        from pathlib import Path
        cls.root=Path(cls.temporary.name)
        build=BUILD.replace("call_command('migrate','core','0060_invitation_email_delivery'",
            "call_command('migrate','core','0062_release_notice_acknowledgement'")
        for source in ('0059_task_page_indexes','0061_workflow_email_delivery'):
            work=cls.root/source;work.mkdir()
            result=subprocess.run([sys.executable,'-c',build,str(ROOT),str(work),source],
                capture_output=True,text=True,timeout=90)
            if result.returncode:raise AssertionError('Isolated notice upgrade failed: '+result.stderr[-1800:])
            (work/'observation.json').write_text(result.stdout,encoding='utf-8')

    def fixture(self,source='0061_workflow_email_delivery'):
        spec=importlib.util.spec_from_file_location('notice_upgrade_proof',ROOT/'deploy/customer/upgrade_fixture.py')
        proof=importlib.util.module_from_spec(spec);spec.loader.exec_module(proof)
        work=self.root/source;target=self.root/(self._testMethodName+'.sqlite3')
        shutil.copyfile(work/'target.sqlite3',target)
        return proof,json.loads((work/'before.json').read_text()),target,work

    def test_0061_to_0062_preserves_every_old_row_and_adds_only_notice_defaults(self):
        proof,before,target,work=self.fixture()
        self.assertEqual(json.loads((work/'observation.json').read_text()),
            {'content_types_added':1,'permissions_added':4})
        result=proof.assert_retained(before,target)
        self.assertEqual(result['retained_rows'],sum(len(value['rows']) for value in before.values()))

    def test_0059_to_0062_supports_only_the_three_reviewed_empty_additions(self):
        proof,before,target,work=self.fixture('0059_task_page_indexes')
        self.assertEqual(json.loads((work/'observation.json').read_text()),
            {'content_types_added':3,'permissions_added':12})
        proof.assert_retained(before,target)

    def test_notice_allowance_requires_exact_empty_schema_migration_and_metadata(self):
        for mutation in (
            "DROP TABLE core_releasenoticeacknowledgement",
            "DELETE FROM django_migrations WHERE app='core' AND name='0062_release_notice_acknowledgement'",
            "ALTER TABLE core_releasenoticeacknowledgement ADD COLUMN unapproved TEXT",
            "INSERT INTO core_releasenoticeacknowledgement(release_key,acknowledged_at,user_id) SELECT 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','2026-11-06',id FROM auth_user LIMIT 1",
            "UPDATE auth_permission SET name='Incorrect default' WHERE codename='change_releasenoticeacknowledgement'",
            "UPDATE auth_permission SET id=-id WHERE codename='view_releasenoticeacknowledgement'",
            "INSERT INTO django_content_type(app_label,model) VALUES('core','unapproved_notice_admin')",
            "UPDATE auth_user SET is_superuser=1",
        ):
            with self.subTest(mutation=mutation):
                proof,before,target,work=self.fixture()
                with closing(sqlite3.connect(target)) as db,db:db.execute(mutation)
                with self.assertRaises(ValueError):proof.assert_retained(before,target)

    def test_preexisting_acknowledgements_remain_subject_to_strict_retention(self):
        proof,before,target,work=self.fixture()
        with closing(sqlite3.connect(target)) as db,db:
            db.execute("INSERT INTO core_releasenoticeacknowledgement(release_key,acknowledged_at,user_id) SELECT ?,?,id FROM auth_user LIMIT 1",('a'*40,'2026-11-06'))
        retained=proof.snapshot(target)
        proof.assert_retained(retained,target)
        with closing(sqlite3.connect(target)) as db,db:
            db.execute("UPDATE core_releasenoticeacknowledgement SET release_key=?",('b'*40,))
        with self.assertRaises(ValueError):proof.assert_retained(retained,target)

    def test_actual_migration_enforces_one_acknowledgement_per_account_and_release(self):
        proof,before,target,work=self.fixture()
        statement="INSERT INTO core_releasenoticeacknowledgement(release_key,acknowledged_at,user_id) SELECT ?,?,id FROM auth_user LIMIT 1"
        with closing(sqlite3.connect(target)) as db,db:
            db.execute(statement,('a'*40,'2026-11-06'))
            with self.assertRaises(sqlite3.IntegrityError):db.execute(statement,('a'*40,'2026-11-06'))

    def test_valid_empty_new_table_still_requires_its_default_metadata(self):
        proof,before,target,work=self.fixture()
        with closing(sqlite3.connect(target)) as db,db:
            db.execute("DELETE FROM auth_permission WHERE content_type_id IN (SELECT id FROM django_content_type WHERE app_label='core' AND model='releasenoticeacknowledgement')")
            db.execute("DELETE FROM django_content_type WHERE app_label='core' AND model='releasenoticeacknowledgement'")
        with self.assertRaises(ValueError):proof.assert_retained(before,target)

    def test_correct_default_metadata_already_in_source_is_preserved_not_replaced(self):
        proof,before,target,work=self.fixture()
        current=proof.snapshot(target)
        for table in ('django_content_type','auth_permission'):
            before[table]=current[table]
        proof.assert_retained(before,target)
        with closing(sqlite3.connect(target)) as db,db:
            db.execute("UPDATE auth_permission SET name='Changed retained permission' WHERE codename='change_releasenoticeacknowledgement'")
        with self.assertRaises(ValueError):proof.assert_retained(before,target)
