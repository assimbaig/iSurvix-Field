"""Actual additive0064 migration and malformed candidate rejection."""
from contextlib import closing
import importlib.util,json,shutil,sqlite3,subprocess,sys,tempfile
from pathlib import Path
from django.test import SimpleTestCase
from .test_invitation_email_upgrade import BUILD,ROOT

class CustomNotificationUpgradeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        parent=ROOT/'.local/custom-notification-upgrade-tests';parent.mkdir(parents=True,exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(dir=parent);cls.addClassCleanup(cls.temp.cleanup);cls.root=Path(cls.temp.name)
        build=BUILD.replace("call_command('migrate','core','0060_invitation_email_delivery'","call_command('migrate','core','0064_company_notification_settings'")
        build=build.replace("before=proof.snapshot(db);", "\n with sqlite3.connect(work/'source.sqlite3') as persisted:connection.connection.backup(persisted)\n before=proof.snapshot(db);")
        for source in ('0057_server_update_requests','0063_checklist_template_company_scope'):
            work=cls.root/source;work.mkdir()
            result=subprocess.run([sys.executable,'-c',build,str(ROOT),str(work),source],capture_output=True,text=True,timeout=90)
            if result.returncode:raise AssertionError(result.stderr[-1500:])
    def fixture(self,source='0063_checklist_template_company_scope'):
        spec=importlib.util.spec_from_file_location('custom_notification_upgrade',ROOT/'deploy/customer/upgrade_fixture.py');proof=importlib.util.module_from_spec(spec);spec.loader.exec_module(proof)
        work=self.root/source;target=self.root/(self._testMethodName+'.sqlite3');shutil.copyfile(work/'target.sqlite3',target)
        return proof,json.loads((work/'before.json').read_text()),target,work/'source.sqlite3'
    def test_actual_migration_keeps_old_records_and_adds_exact_empty_settings(self):
        for source in ('0057_server_update_requests','0063_checklist_template_company_scope'):
            proof,before,target,old=self.fixture(source)
            result=proof.assert_retained(before,target,source_database=old)
            self.assertEqual(result['retained_rows'],sum(len(value['rows']) for value in before.values()))
    def test_missing_marker_extra_column_and_nonempty_settings_are_rejected(self):
        for mutation in ["DELETE FROM django_migrations WHERE name='0064_company_notification_settings'", "ALTER TABLE core_companynotificationsettings ADD COLUMN unapproved TEXT", "DROP TABLE core_companynotificationsettings", "DELETE FROM auth_permission WHERE codename='change_companynotificationsettings'", "DELETE FROM auth_permission WHERE codename LIKE '%companynotificationsettings'; DELETE FROM django_content_type WHERE model='companynotificationsettings'", "UPDATE auth_user SET is_superuser=1"]:
            proof,before,target,old=self.fixture()
            with closing(sqlite3.connect(target)) as db,db:db.executescript(mutation)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):proof.assert_retained(before,target,source_database=old)

    def test_unexpected_retained_indexes_are_rejected_for_0063_to_0064(self):
        for mutation in ('CREATE INDEX unexpected_user_index ON auth_user(username)', 'DROP INDEX ck_project_updated_page'):
            proof,before,target,old=self.fixture()
            with closing(sqlite3.connect(target)) as db,db:db.execute(mutation)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):proof.assert_retained(before,target,source_database=old)
