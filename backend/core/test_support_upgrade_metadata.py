"""Real 0057->0058 migration metadata is not an unrelated permission mutation."""
from contextlib import closing
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]


def comparator():
    spec = importlib.util.spec_from_file_location('reviewed_support_retention', ROOT / 'deploy/customer/upgrade_fixture.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATE_FIXTURE = r'''
from pathlib import Path
from contextlib import closing
import copy,hashlib,importlib.util,json,logging,os,shutil,sqlite3,sys
root=Path(sys.argv[1]);work=Path(sys.argv[2]);sys.path.insert(0,str(root/'backend'))
spec=importlib.util.spec_from_file_location('ordinary_test_guard',root/'scripts/run_backend_tests.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
attempts=[];fixtures=[]
with guard.network_isolation(attempts,fixtures):
 os.environ['DJANGO_SETTINGS_MODULE']='checklist.settings_local'
 from django.conf import settings
 settings.DATABASES=copy.deepcopy(settings.DATABASES)
 source=work/'source0057.sqlite3';target=work/'target0058.sqlite3'
 settings.DATABASES['default']['NAME']=source
 settings.DATABASES['default'].pop('TEST',None)
 settings.MEDIA_ROOT=work/'media';settings.MEDIA_ROOT.mkdir()
 settings.LOGGING={}
 import django;django.setup()
 from django.core.management import call_command
 from django.db import connections
 from django.contrib.auth.models import User
 from django.contrib.contenttypes.models import ContentType
 call_command('migrate','core','0057_server_update_requests',interactive=False,verbosity=0)
 call_command('migrate','auth',interactive=False,verbosity=0)
 User.objects.create_user('synthetic-retained-support-upgrade',password=None)
 spec=importlib.util.spec_from_file_location('retention_snapshot',root/'deploy/customer/upgrade_fixture.py')
 proof=importlib.util.module_from_spec(spec);spec.loader.exec_module(proof)
 before=proof.snapshot(source)
 (work/'before.json').write_text(json.dumps(before,sort_keys=True))
 connections.close_all();shutil.copyfile(source,target)
 settings.DATABASES['default']['NAME']=target
 connections['default'].settings_dict['NAME']=target
 ContentType.objects.clear_cache()
 call_command('migrate','core','0058_support_cases',interactive=False,verbosity=0)
 connections.close_all()
 after=proof.snapshot(target)
 metadata={'content_types_added':len(after['django_content_type']['rows'])-len(before['django_content_type']['rows']),
           'permissions_added':len(after['auth_permission']['rows'])-len(before['auth_permission']['rows'])}
 assert not attempts,attempts
 assert metadata=={'content_types_added':2,'permissions_added':8},metadata
 (work/'migration-observation.json').write_text(json.dumps(metadata))
 print(json.dumps({'actual_django_migration':True,'metadata':metadata,'external_network_attempts':len(attempts)}))
'''


class SupportMetadataMigrationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        parent = ROOT / '.local/support-metadata-upgrade-tests'
        parent.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(dir=parent)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        process = subprocess.run([sys.executable, '-c', MIGRATE_FIXTURE, str(ROOT), str(cls.root)],
                                 cwd=ROOT, capture_output=True, text=True, timeout=90)
        (cls.root / 'fixture.log').write_text(process.stdout + process.stderr, encoding='utf-8')
        if process.returncode:
            raise AssertionError('Isolated actual Django migration failed: ' + process.stderr[-2200:])
        cls.before = json.loads((cls.root / 'before.json').read_text())
        cls.source_hash = hashlib.sha256((cls.root / 'source0057.sqlite3').read_bytes()).hexdigest()

    def setUp(self):
        self.proof = comparator()
        self.target = self.root / (self._testMethodName + '.sqlite3')
        shutil.copyfile(self.root / 'target0058.sqlite3', self.target)

    def mutate(self, statement, parameters=()):
        with closing(sqlite3.connect(self.target)) as db, db:
            db.execute(statement, parameters)

    def assert_rejected(self):
        with self.assertRaises(ValueError):
            self.proof.assert_retained(self.before, self.target)

    def test_real_0058_migration_allows_only_default_support_metadata_and_keeps_snapshot_digest(self):
        observation = json.loads((self.root / 'migration-observation.json').read_text())
        self.assertEqual(observation, {'content_types_added': 2, 'permissions_added': 8})
        retained = self.proof.assert_retained(self.before, self.target)
        baseline = self.proof.assert_retained(self.before, self.root / 'source0057.sqlite3')
        self.assertEqual(retained['retained_rows_sha256'], baseline['retained_rows_sha256'])
        self.assertEqual(retained['retained_rows'], baseline['retained_rows'])
        self.assertEqual(hashlib.sha256((self.root / 'source0057.sqlite3').read_bytes()).hexdigest(), self.source_hash)

    def test_a_new_user_permission_grant_still_rejects_the_upgrade(self):
        self.mutate("INSERT INTO auth_user_user_permissions(user_id,permission_id) SELECT (SELECT id FROM auth_user LIMIT 1),id FROM auth_permission WHERE codename='change_supportcase'")
        self.assert_rejected()

    def test_a_new_group_permission_grant_still_rejects_the_upgrade(self):
        self.mutate("INSERT INTO auth_group(name) VALUES ('new-admin-group')")
        self.mutate("INSERT INTO auth_group_permissions(group_id,permission_id) SELECT (SELECT id FROM auth_group WHERE name='new-admin-group'),id FROM auth_permission WHERE codename='change_supportcase'")
        self.assert_rejected()

    def test_unknown_permission_or_content_type_cannot_hide_among_new_metadata(self):
        for mutation in (
            "INSERT INTO django_content_type(app_label,model) VALUES('core','unexpected_admin')",
            "INSERT INTO auth_permission(name,content_type_id,codename) SELECT 'Can grant root',id,'grant_root' FROM django_content_type WHERE model='supportcase'",
        ):
            with self.subTest(mutation=mutation):
                shutil.copyfile(self.root / 'target0058.sqlite3', self.target)
                self.mutate(mutation)
                self.assert_rejected()

    def test_existing_permission_edits_removal_or_user_privilege_changes_still_fail(self):
        for mutation in (
            "UPDATE auth_permission SET name='Changed retained permission' WHERE id=(SELECT MIN(id) FROM auth_permission)",
            "DELETE FROM auth_permission WHERE id=(SELECT MIN(id) FROM auth_permission)",
            "UPDATE auth_user SET is_superuser=1",
        ):
            with self.subTest(mutation=mutation):
                shutil.copyfile(self.root / 'target0058.sqlite3', self.target)
                self.mutate(mutation)
                self.assert_rejected()

    def test_allowance_requires_actual_0058_record_new_tables_and_exact_default_names(self):
        for mutation in (
            "DELETE FROM django_migrations WHERE app='core' AND name='0058_support_cases'",
            "DROP TABLE core_supportevent",
            "UPDATE auth_permission SET name='Mislabelled permission' WHERE codename='change_supportcase'",
        ):
            with self.subTest(mutation=mutation):
                shutil.copyfile(self.root / 'target0058.sqlite3', self.target)
                self.mutate(mutation)
                self.assert_rejected()

    def test_same_schema_existing_support_metadata_gets_no_new_row_allowance(self):
        before58 = self.proof.snapshot(self.target)
        self.mutate("INSERT INTO auth_permission(name,content_type_id,codename) SELECT 'Can bypass',id,'bypass_supportcase' FROM django_content_type WHERE model='supportcase'")
        with self.assertRaises(ValueError):
            self.proof.assert_retained(before58, self.target)


class ReviewedHostRetentionBoundaryTests(SimpleTestCase):
    def test_postmigration_comparator_is_reviewed_host_not_frozen_source_or_candidate(self):
        from .test_customer_updates import CustomerUpdateTests
        fixture = CustomerUpdateTests(methodName='test_request_signature_expiry_and_binding_are_checked')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original = fixture.updater._module
        observed = []

        def module(path, name):
            observed.append(Path(path).resolve())
            loaded = original(path, name)
            if name == 'installed_retention':
                def old_comparator(*args, **kwargs):
                    raise ValueError('Frozen 0057 comparator does not know 0058 metadata.')
                return SimpleNamespace(snapshot=loaded.snapshot, assert_retained=old_comparator)
            return loaded

        with patch.object(fixture.updater, '_module', side_effect=module):
            result = fixture.apply()
        self.assertEqual(result['status'], 'completed')
        self.assertIn((ROOT / 'deploy/customer/upgrade_fixture.py').resolve(), observed)
        self.assertNotIn((fixture.target_package / 'release/deploy/customer/upgrade_fixture.py').resolve(), observed)
