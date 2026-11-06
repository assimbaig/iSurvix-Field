"""Actual retained-record upgrades may add only reviewed default mail metadata."""
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

ROOT = Path(__file__).resolve().parents[2]
BUILD = r'''
import copy,importlib.util,json,os,sys,sqlite3
from pathlib import Path
root=Path(sys.argv[1]);work=Path(sys.argv[2]);source_version=sys.argv[3]
sys.path.insert(0,str(root/'backend'))
spec=importlib.util.spec_from_file_location('guard',root/'scripts/run_backend_tests.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
attempts=[];fixtures=[]
with guard.network_isolation(attempts,fixtures):
 os.environ['DJANGO_SETTINGS_MODULE']='checklist.settings_local'
 from django.conf import settings
 settings.DATABASES=copy.deepcopy(settings.DATABASES)
 db=work/'target.sqlite3';settings.DATABASES['default']['NAME']=':memory:'
 settings.DATABASES['default'].pop('TEST',None);settings.LOGGING={}
 settings.MEDIA_ROOT=work/'media';settings.MEDIA_ROOT.mkdir()
 import django;django.setup()
 from django.core.management import call_command
 from django.db import connection,connections
 from django.contrib.auth.models import User
 call_command('migrate','core',source_version,interactive=False,verbosity=0)
 call_command('migrate','auth',interactive=False,verbosity=0)
 User.objects.create_user('synthetic-email-upgrade',password=None)
 spec=importlib.util.spec_from_file_location('proof',root/'deploy/customer/upgrade_fixture.py')
 proof=importlib.util.module_from_spec(spec);spec.loader.exec_module(proof)
 # Exercise actual Django/SQLite migrations without depending on per-DDL
 # filesystem fsync latency. Persist coherent SQLite backups for the real
 # retained-row comparator and every corruption assertion below.
 with sqlite3.connect(db) as persisted:connection.connection.backup(persisted)
 before=proof.snapshot(db);(work/'before.json').write_text(json.dumps(before))
 call_command('migrate','core','0060_invitation_email_delivery',interactive=False,verbosity=0)
 with sqlite3.connect(db) as persisted:connection.connection.backup(persisted)
 connections.close_all()
 after=proof.snapshot(db)
 print(json.dumps({'content_types_added':len(after['django_content_type']['rows'])-len(before['django_content_type']['rows']),
                  'permissions_added':len(after['auth_permission']['rows'])-len(before['auth_permission']['rows'])}))
 assert not attempts,attempts
'''


class InvitationMailUpgradeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        parent = ROOT / '.local/mail-upgrade-tests'
        parent.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(dir=parent)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        for source in ('0057_server_update_requests', '0059_task_page_indexes'):
            work = cls.root / source
            work.mkdir()
            result = subprocess.run([sys.executable, '-c', BUILD, str(ROOT), str(work), source],
                                    capture_output=True, text=True, timeout=90)
            if result.returncode:
                raise AssertionError('Isolated migration fixture failed: '+result.stderr[-1800:])
            (work/'observation.json').write_text(result.stdout, encoding='utf-8')

    def fixture(self, source='0059_task_page_indexes'):
        spec = importlib.util.spec_from_file_location('email_upgrade_proof', ROOT/'deploy/customer/upgrade_fixture.py')
        proof = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(proof)
        work = self.root / source
        target = self.root / (self._testMethodName+'.sqlite3')
        shutil.copyfile(work/'target.sqlite3', target)
        return proof, json.loads((work/'before.json').read_text()), target, work

    def test_actual_0059_to_0060_keeps_rows_and_only_adds_mail_defaults(self):
        proof, before, target, work = self.fixture()
        self.assertEqual(json.loads((work/'observation.json').read_text()),
                         {'content_types_added':1, 'permissions_added':4})
        result = proof.assert_retained(before, target)
        self.assertEqual(result['retained_rows'], sum(len(v['rows']) for v in before.values()))

    def test_existing_0057_baseline_support_and_mail_metadata_are_both_strictly_accepted(self):
        proof, before, target, work = self.fixture('0057_server_update_requests')
        self.assertEqual(json.loads((work/'observation.json').read_text()),
                         {'content_types_added':3, 'permissions_added':12})
        proof.assert_retained(before, target)

    def test_unknown_metadata_or_privilege_change_still_rejects_upgrade(self):
        for mutation in (
            "INSERT INTO django_content_type(app_label,model) VALUES('core','unapproved_mail_admin')",
            "UPDATE auth_user SET is_superuser=1",
            "UPDATE auth_permission SET name='Changed retained permission' WHERE id=(SELECT MIN(id) FROM auth_permission)",
        ):
            with self.subTest(mutation=mutation):
                proof, before, target, work = self.fixture()
                with closing(sqlite3.connect(target)) as db, db:
                    db.execute(mutation)
                with self.assertRaises(ValueError):
                    proof.assert_retained(before, target)

    def test_new_mail_permission_ids_must_be_positive(self):
        proof, before, target, work = self.fixture()
        with closing(sqlite3.connect(target)) as db, db:
            changed = db.execute("UPDATE auth_permission SET id=-id WHERE content_type_id IN "
                                 "(SELECT id FROM django_content_type WHERE app_label='core' "
                                 "AND model='invitationemaildelivery')").rowcount
        self.assertEqual(changed, 4)
        with self.assertRaises(ValueError):
            proof.assert_retained(before, target)

    def test_mail_allowance_requires_exact_table_migration_and_default_permission_names(self):
        for mutation in (
            "DELETE FROM django_migrations WHERE app='core' AND name='0060_invitation_email_delivery'",
            "DROP TABLE core_invitationemaildelivery",
            "UPDATE auth_permission SET name='Incorrect new permission' WHERE codename='change_invitationemaildelivery'",
        ):
            with self.subTest(mutation=mutation):
                proof, before, target, work = self.fixture()
                with closing(sqlite3.connect(target)) as db, db:
                    db.execute(mutation)
                with self.assertRaises(ValueError):
                    proof.assert_retained(before, target)
