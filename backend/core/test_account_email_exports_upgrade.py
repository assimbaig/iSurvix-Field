"""Real0064→0067 migration, exact schema and retained data safety."""
from contextlib import closing
import importlib.util,json,shutil,sqlite3,subprocess,sys,tempfile
from pathlib import Path
from django.test import SimpleTestCase
from .test_invitation_email_upgrade import BUILD,ROOT

class AccountExportUpgradeTests(SimpleTestCase):
 @classmethod
 def setUpClass(cls):
  super().setUpClass();parent=ROOT/'.local/account-export-upgrade-tests';parent.mkdir(parents=True,exist_ok=True)
  cls.tmp=tempfile.TemporaryDirectory(dir=parent);cls.addClassCleanup(cls.tmp.cleanup);cls.root=Path(cls.tmp.name)
  build=BUILD.replace("call_command('migrate','core','0060_invitation_email_delivery'","call_command('migrate','core','0067_installed_release_history'")
  build=build.replace('before=proof.snapshot(db);',"\n with sqlite3.connect(work/'source.sqlite3') as persisted:connection.connection.backup(persisted)\n before=proof.snapshot(db);")
  result=subprocess.run([sys.executable,'-c',build,str(ROOT),str(cls.root),'0064_company_notification_settings'],capture_output=True,text=True,timeout=90)
  if result.returncode:raise AssertionError(result.stderr[-1600:])
 def fixture(self):
  spec=importlib.util.spec_from_file_location('new_exports_upgrade',ROOT/'deploy/customer/upgrade_fixture.py');proof=importlib.util.module_from_spec(spec);spec.loader.exec_module(proof)
  target=self.root/(self._testMethodName+'.sqlite3');shutil.copyfile(self.root/'target.sqlite3',target)
  return proof,json.loads((self.root/'before.json').read_text()),target,self.root/'source.sqlite3'
 def test_real_migration_preserves_all_existing_records(self):
  proof,before,target,old=self.fixture();result=proof.assert_retained(before,target,source_database=old)
  self.assertEqual(result['retained_rows'],sum(len(v['rows']) for v in before.values()))
  with closing(sqlite3.connect(target)) as db:
   for table in ['core_accountrecoveryrequest','core_accountrecoverythrottle','core_dataexportjob','core_dataexportworkerlease','core_installedrelease']:self.assertEqual(db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
 def test_extra_constraints_indexes_triggers_defaults_and_permissions_are_rejected(self):
  changes=[
   "CREATE INDEX bad_export_extra ON core_dataexportjob(section)",
   "DROP INDEX export_owner_history; CREATE INDEX export_owner_history ON core_dataexportjob(owner_id COLLATE NOCASE,created_at DESC)",
   "CREATE TRIGGER bad_export_trigger AFTER INSERT ON core_dataexportjob BEGIN UPDATE auth_user SET is_superuser=1; END",
   "DELETE FROM django_migrations WHERE name='0066_data_exports'",
   "DELETE FROM auth_permission WHERE codename='view_dataexportjob'",
   "UPDATE auth_permission SET name='Unapproved' WHERE codename='view_accountrecoveryrequest'",
   "ALTER TABLE core_installedrelease ADD COLUMN unapproved TEXT",
   "INSERT INTO core_accountrecoverythrottle(key,window_started_at,hits) VALUES('unapproved','2026-11-07',0)",
   "PRAGMA writable_schema=ON; UPDATE sqlite_master SET sql=replace(sql,'\"section\" varchar(32) NOT NULL','\"section\" varchar(32) NOT NULL CHECK(section=\"tasks\")') WHERE name='core_dataexportjob'; PRAGMA writable_schema=OFF;",
   "PRAGMA writable_schema=ON; UPDATE sqlite_master SET sql=replace(sql,'\"version\" varchar(32) NOT NULL','\"version\" varchar(32) NOT NULL DEFAULT 0') WHERE name='core_installedrelease'; PRAGMA writable_schema=OFF;",
  ]
  for sql in changes:
   proof,before,target,old=self.fixture()
   with closing(sqlite3.connect(target)) as db,db:db.executescript(sql)
   with self.subTest(sql=sql),self.assertRaises(ValueError):proof.assert_retained(before,target,source_database=old)
