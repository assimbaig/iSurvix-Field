"""Independent candidate tampering probes; actual isolated migration fixtures."""
from contextlib import closing
import sqlite3
from .test_custom_notification_upgrade import CustomNotificationUpgradeTests


class NotificationUpgradeIndependentSecurityTests(CustomNotificationUpgradeTests):
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
