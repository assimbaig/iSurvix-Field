"""Independent candidate tampering probes; actual isolated migration fixtures."""
from contextlib import closing
import sqlite3
import shutil
from .test_custom_notification_upgrade import CustomNotificationUpgradeTests


class NotificationUpgradeIndependentSecurityTests(CustomNotificationUpgradeTests):
    def legacy_pair(self):
        proof,_,target,_=self.fixture()
        with closing(sqlite3.connect(target)) as db,db:
            db.execute('DROP TABLE core_companynotificationsettings')
            db.execute("DELETE FROM django_migrations WHERE name='0064_company_notification_settings'")
        source=target.with_suffix('.source.sqlite3')
        shutil.copyfile(target,source)
        return proof,proof.snapshot(source),target,source

    def test_unchanged_backward_migration_metadata_is_retained_but_forged_source_marker_rejects(self):
        proof,before,target,source=self.legacy_pair()
        proof.assert_retained(before,target,source_database=source)
        with closing(sqlite3.connect(source)) as db,db:
            db.execute("INSERT INTO django_migrations(app,name,applied) VALUES ('core','0064_company_notification_settings','2026-11-06T00:00:00')")
        with self.assertRaises(ValueError):proof.assert_retained(before,target,source_database=source)

    def test_legacy_metadata_skip_rejects_changed_permission_and_missing_source_proof(self):
        proof,before,target,source=self.legacy_pair()
        with self.assertRaises(ValueError):proof.assert_retained(before,target)
        with closing(sqlite3.connect(target)) as db,db:
            db.execute("UPDATE auth_permission SET name='Changed privilege' WHERE codename='change_companynotificationsettings'")
        with self.assertRaises(ValueError):proof.assert_retained(before,target,source_database=source)

    def test_unreviewed_settings_trigger_is_rejected(self):
        proof,before,target,source=self.fixture()
        with closing(sqlite3.connect(target)) as db,db:
            db.executescript('''CREATE TRIGGER unwanted_settings_trigger AFTER INSERT ON core_companynotificationsettings
                BEGIN UPDATE core_companynotificationsettings SET timezone_name='UTC' WHERE id=NEW.id; END;''')
        with self.assertRaises(ValueError):proof.assert_retained(before,target,source_database=source)

    def test_wrong_foreign_key_action_is_rejected(self):
        proof,before,target,source=self.fixture()
        with closing(sqlite3.connect(target)) as db,db:
            sql=db.execute("SELECT sql FROM sqlite_master WHERE name='core_companynotificationsettings'").fetchone()[0]
            changed=sql.replace('REFERENCES "core_company" ("id")','REFERENCES "core_company" ("id") ON DELETE CASCADE')
            self.assertNotEqual(sql,changed)
            db.execute('PRAGMA writable_schema=ON')
            db.execute("UPDATE sqlite_master SET sql=? WHERE name='core_companynotificationsettings'",(changed,))
            db.execute('PRAGMA writable_schema=OFF')
        with self.assertRaises(ValueError):proof.assert_retained(before,target,source_database=source)

    def test_unreviewed_extra_check_constraint_is_rejected(self):
        proof,before,target,source=self.fixture()
        with closing(sqlite3.connect(target)) as db,db:
            sql=db.execute("SELECT sql FROM sqlite_master WHERE name='core_companynotificationsettings'").fetchone()[0]
            changed=sql[:-1]+', CHECK ("timezone_name" = \'UTC\'))'
            db.execute('PRAGMA writable_schema=ON')
            db.execute("UPDATE sqlite_master SET sql=? WHERE name='core_companynotificationsettings'",(changed,))
            db.execute('PRAGMA writable_schema=OFF')
        with self.assertRaises(ValueError):proof.assert_retained(before,target,source_database=source)
