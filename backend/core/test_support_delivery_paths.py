"""Support-only changes must schedule the real shared candidate's prerequisite runs."""
import fnmatch
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import tempfile
from contextlib import closing

from django.test import SimpleTestCase
from django.test import TransactionTestCase


ROOT = Path(__file__).resolve().parents[2]


class SupportDeliveryPathsTests(SimpleTestCase):
    def test_advertised_upgrade_schema_matches_the_actual_migration_graph(self):
        from django.db.migrations.loader import MigrationLoader
        record = json.loads((ROOT / 'deploy/customer/supported-upgrades.json').read_text())
        leaves = MigrationLoader(None).graph.leaf_nodes('core')
        self.assertEqual(len(leaves), 1)
        self.assertEqual(record['target_schema'], leaves[0][1])

    def test_company_scope_migration_preserves_rows_and_records_only_unambiguous_owner(self):
        spec = importlib.util.spec_from_file_location(
            'candidate_upgrade_fixture', ROOT / 'deploy/customer/upgrade_fixture.py')
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        with tempfile.TemporaryDirectory() as directory:
            before_path = Path(directory) / 'before.sqlite3'
            after_path = Path(directory) / 'after.sqlite3'
            with closing(sqlite3.connect(before_path)) as db:
                db.executescript('''
                    CREATE TABLE core_company (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                    CREATE TABLE core_checklisttemplate (id INTEGER PRIMARY KEY, definition TEXT NOT NULL, name TEXT NOT NULL);
                    CREATE TABLE core_project (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, company_id INTEGER);
                    CREATE TABLE core_checklist (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, project_id INTEGER);
                    INSERT INTO core_company VALUES (1, 'Company A'), (2, 'Company B');
                    INSERT INTO core_checklisttemplate VALUES
                        (10, '{"title":"owned"}', 'Owned'),
                        (20, '{"title":"ambiguous"}', 'Ambiguous'),
                        (30, '{"standard_catalog":true}', 'Shared');
                    INSERT INTO core_project VALUES (100, 10, 1), (200, 20, 1), (201, 20, 2);
                    INSERT INTO core_checklist VALUES (300, 10, 100);
                ''')
            before = fixture.snapshot(before_path)
            with closing(sqlite3.connect(after_path)) as db:
                db.executescript('''
                    CREATE TABLE core_company (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                    CREATE TABLE core_checklisttemplate (id INTEGER PRIMARY KEY, definition TEXT NOT NULL, name TEXT NOT NULL, company_id BIGINT REFERENCES core_company(id));
                    CREATE TABLE core_project (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, company_id INTEGER);
                    CREATE TABLE core_checklist (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, project_id INTEGER);
                    CREATE TABLE django_migrations (app TEXT, name TEXT);
                    INSERT INTO core_company VALUES (1, 'Company A'), (2, 'Company B');
                    INSERT INTO core_checklisttemplate VALUES
                        (10, '{"title":"owned"}', 'Owned', 1),
                        (20, '{"title":"ambiguous"}', 'Ambiguous', NULL),
                        (30, '{"standard_catalog":true}', 'Shared', NULL);
                    INSERT INTO core_project VALUES (100, 10, 1), (200, 20, 1), (201, 20, 2);
                    INSERT INTO core_checklist VALUES (300, 10, 100);
                    INSERT INTO django_migrations VALUES ('core', '0063_checklist_template_company_scope');
                    CREATE INDEX core_checklisttemplate_company_id_2960fd66 ON core_checklisttemplate(company_id);
                ''')
            proof = fixture.assert_retained(before, after_path, source_database=before_path)
            self.assertEqual(proof['company_scoped_templates'], 1)
            with closing(sqlite3.connect(after_path)) as db:
                db.execute('CREATE UNIQUE INDEX unexpected_company_uniqueness ON core_checklisttemplate(company_id)')
            with self.assertRaisesRegex(ValueError, 'index'):
                fixture.assert_retained(before, after_path, source_database=before_path)

    def test_company_scope_retention_rejects_unexpected_index_on_other_retained_table(self):
        spec = importlib.util.spec_from_file_location(
            'candidate_upgrade_fixture_unexpected_other_index', ROOT / 'deploy/customer/upgrade_fixture.py')
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        with tempfile.TemporaryDirectory() as directory:
            before_path = Path(directory) / 'before.sqlite3'
            after_path = Path(directory) / 'after.sqlite3'
            with closing(sqlite3.connect(before_path)) as db:
                db.executescript('''
                    CREATE TABLE core_company (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                    CREATE TABLE core_checklisttemplate (id INTEGER PRIMARY KEY, definition TEXT NOT NULL, name TEXT NOT NULL);
                    CREATE TABLE core_project (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, company_id INTEGER);
                    CREATE TABLE core_checklist (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, project_id INTEGER);
                    INSERT INTO core_company VALUES (1, 'Company A');
                    INSERT INTO core_checklisttemplate VALUES (10, '{"title":"owned"}', 'Owned');
                    INSERT INTO core_project VALUES (100, 10, 1);
                    INSERT INTO core_checklist VALUES (300, 10, 100);
                ''')
            before = fixture.snapshot(before_path)
            with closing(sqlite3.connect(after_path)) as db:
                db.executescript('''
                    CREATE TABLE core_company (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                    CREATE TABLE core_checklisttemplate (id INTEGER PRIMARY KEY, definition TEXT NOT NULL, name TEXT NOT NULL, company_id BIGINT REFERENCES core_company(id));
                    CREATE TABLE core_project (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, company_id INTEGER);
                    CREATE TABLE core_checklist (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, project_id INTEGER);
                    CREATE TABLE django_migrations (app TEXT, name TEXT);
                    INSERT INTO core_company VALUES (1, 'Company A');
                    INSERT INTO core_checklisttemplate VALUES (10, '{"title":"owned"}', 'Owned', 1);
                    INSERT INTO core_project VALUES (100, 10, 1);
                    INSERT INTO core_checklist VALUES (300, 10, 100);
                    INSERT INTO django_migrations VALUES ('core', '0063_checklist_template_company_scope');
                    CREATE INDEX core_checklisttemplate_company_id_2960fd66 ON core_checklisttemplate(company_id);
                    CREATE INDEX unexpected_project_company_index ON core_project(company_id);
                ''')
            with self.assertRaisesRegex(ValueError, 'index'):
                fixture.assert_retained(before, after_path, source_database=before_path)

    def test_company_scope_retention_rejects_applied_marker_without_company_field(self):
        spec = importlib.util.spec_from_file_location(
            'candidate_upgrade_fixture_missing_company_field', ROOT / 'deploy/customer/upgrade_fixture.py')
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        with tempfile.TemporaryDirectory() as directory:
            before_path = Path(directory) / 'before.sqlite3'
            after_path = Path(directory) / 'after.sqlite3'
            for path, include_marker in ((before_path, False), (after_path, True)):
                with closing(sqlite3.connect(path)) as db:
                    db.executescript('''
                        CREATE TABLE core_company (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                        CREATE TABLE core_checklisttemplate (id INTEGER PRIMARY KEY, definition TEXT NOT NULL, name TEXT NOT NULL);
                        CREATE TABLE core_project (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, company_id INTEGER);
                        CREATE TABLE core_checklist (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, project_id INTEGER);
                        INSERT INTO core_company VALUES (1, 'Company A');
                        INSERT INTO core_checklisttemplate VALUES (10, '{"title":"owned"}', 'Owned');
                        INSERT INTO core_project VALUES (100, 10, 1);
                        INSERT INTO core_checklist VALUES (300, 10, 100);
                    ''')
                    if include_marker:
                        db.executescript('''
                            CREATE TABLE django_migrations (app TEXT, name TEXT);
                            INSERT INTO django_migrations VALUES ('core', '0063_checklist_template_company_scope');
                        ''')
            before = fixture.snapshot(before_path)
            with self.assertRaisesRegex(ValueError, 'company scope|0063|column'):
                fixture.assert_retained(before, after_path, source_database=before_path)

    def test_company_scope_retention_rejects_wrong_tenant_assignment(self):
        spec = importlib.util.spec_from_file_location(
            'candidate_upgrade_fixture_wrong_owner', ROOT / 'deploy/customer/upgrade_fixture.py')
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        with tempfile.TemporaryDirectory() as directory:
            before_path = Path(directory) / 'before.sqlite3'
            after_path = Path(directory) / 'after.sqlite3'
            with closing(sqlite3.connect(before_path)) as db:
                db.executescript('''
                    CREATE TABLE core_company (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                    CREATE TABLE core_checklisttemplate (id INTEGER PRIMARY KEY, definition TEXT NOT NULL, name TEXT NOT NULL);
                    CREATE TABLE core_project (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, company_id INTEGER);
                    CREATE TABLE core_checklist (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, project_id INTEGER);
                    INSERT INTO core_company VALUES (1, 'Company A'), (2, 'Company B');
                    INSERT INTO core_checklisttemplate VALUES (10, '{"title":"owned"}', 'Owned');
                    INSERT INTO core_project VALUES (100, 10, 1);
                    INSERT INTO core_checklist VALUES (300, 10, 100);
                ''')
            before = fixture.snapshot(before_path)
            with closing(sqlite3.connect(after_path)) as db:
                db.executescript('''
                    CREATE TABLE core_company (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                    CREATE TABLE core_checklisttemplate (id INTEGER PRIMARY KEY, definition TEXT NOT NULL, name TEXT NOT NULL, company_id BIGINT REFERENCES core_company(id));
                    CREATE TABLE core_project (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, company_id INTEGER);
                    CREATE TABLE core_checklist (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, project_id INTEGER);
                    CREATE TABLE django_migrations (app TEXT, name TEXT);
                    INSERT INTO core_company VALUES (1, 'Company A'), (2, 'Company B');
                    INSERT INTO core_checklisttemplate VALUES (10, '{"title":"owned"}', 'Owned', 2);
                    INSERT INTO core_project VALUES (100, 10, 1);
                    INSERT INTO core_checklist VALUES (300, 10, 100);
                    INSERT INTO django_migrations VALUES ('core', '0063_checklist_template_company_scope');
                ''')
            with self.assertRaisesRegex(ValueError, 'changed unexpectedly|company scope'):
                fixture.assert_retained(before, after_path, source_database=before_path)

    def test_company_scope_retention_rejects_non_nullable_or_defaulted_company_field(self):
        spec = importlib.util.spec_from_file_location(
            'candidate_upgrade_fixture_bad_column', ROOT / 'deploy/customer/upgrade_fixture.py')
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        for declaration in ('BIGINT NOT NULL REFERENCES core_company(id)',
                            'INTEGER REFERENCES core_company(id)',
                            'BIGINT DEFAULT 1 REFERENCES core_company(id)'):
            with self.subTest(declaration=declaration), tempfile.TemporaryDirectory() as directory:
                before_path = Path(directory) / 'before.sqlite3'
                after_path = Path(directory) / 'after.sqlite3'
                with closing(sqlite3.connect(before_path)) as db:
                    db.executescript('''
                        CREATE TABLE core_company (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                        CREATE TABLE core_checklisttemplate (id INTEGER PRIMARY KEY, definition TEXT NOT NULL, name TEXT NOT NULL);
                        CREATE TABLE core_project (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, company_id INTEGER);
                        CREATE TABLE core_checklist (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, project_id INTEGER);
                        INSERT INTO core_company VALUES (1, 'Company A');
                        INSERT INTO core_checklisttemplate VALUES (10, '{"title":"owned"}', 'Owned');
                        INSERT INTO core_project VALUES (100, 10, 1);
                        INSERT INTO core_checklist VALUES (300, 10, 100);
                    ''')
                before = fixture.snapshot(before_path)
                with closing(sqlite3.connect(after_path)) as db:
                    db.executescript(f'''
                        CREATE TABLE core_company (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                    CREATE TABLE core_checklisttemplate (
                            id INTEGER PRIMARY KEY, definition TEXT NOT NULL, name TEXT NOT NULL,
                            company_id {declaration});
                        CREATE TABLE core_project (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, company_id INTEGER);
                        CREATE TABLE core_checklist (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, project_id INTEGER);
                        CREATE TABLE django_migrations (app TEXT, name TEXT);
                        INSERT INTO core_company VALUES (1, 'Company A');
                        INSERT INTO core_checklisttemplate VALUES (10, '{{"title":"owned"}}', 'Owned', 1);
                        INSERT INTO core_project VALUES (100, 10, 1);
                        INSERT INTO core_checklist VALUES (300, 10, 100);
                        INSERT INTO django_migrations VALUES ('core', '0063_checklist_template_company_scope');
                    ''')
                with self.assertRaisesRegex(ValueError, 'unverified|column|schema'):
                    fixture.assert_retained(before, after_path, source_database=before_path)

    def test_company_scope_retention_rejects_unreviewed_application_trigger(self):
        spec = importlib.util.spec_from_file_location(
            'candidate_upgrade_fixture_trigger', ROOT / 'deploy/customer/upgrade_fixture.py')
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        with tempfile.TemporaryDirectory() as directory:
            before_path = Path(directory) / 'before.sqlite3'
            after_path = Path(directory) / 'after.sqlite3'
            with closing(sqlite3.connect(before_path)) as db:
                db.executescript('''
                    CREATE TABLE core_company (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                    CREATE TABLE core_checklisttemplate (id INTEGER PRIMARY KEY, definition TEXT NOT NULL, name TEXT NOT NULL);
                    CREATE TABLE core_project (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, company_id INTEGER);
                    CREATE TABLE core_checklist (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, project_id INTEGER);
                    INSERT INTO core_company VALUES (1, 'Company A');
                    INSERT INTO core_checklisttemplate VALUES (10, '{"title":"owned"}', 'Owned');
                    INSERT INTO core_project VALUES (100, 10, 1);
                    INSERT INTO core_checklist VALUES (300, 10, 100);
                ''')
            before = fixture.snapshot(before_path)
            with closing(sqlite3.connect(after_path)) as db:
                db.executescript('''
                    CREATE TABLE core_company (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                    CREATE TABLE core_checklisttemplate (id INTEGER PRIMARY KEY, definition TEXT NOT NULL, name TEXT NOT NULL, company_id BIGINT REFERENCES core_company(id));
                    CREATE TABLE core_project (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, company_id INTEGER);
                    CREATE TABLE core_checklist (id INTEGER PRIMARY KEY, checklist_template_id INTEGER, project_id INTEGER);
                    CREATE TABLE django_migrations (app TEXT, name TEXT);
                    INSERT INTO core_company VALUES (1, 'Company A');
                    INSERT INTO core_checklisttemplate VALUES (10, '{"title":"owned"}', 'Owned', 1);
                    INSERT INTO core_project VALUES (100, 10, 1);
                    INSERT INTO core_checklist VALUES (300, 10, 100);
                    INSERT INTO django_migrations VALUES ('core', '0063_checklist_template_company_scope');
                    CREATE TRIGGER synthetic_unreviewed_trigger AFTER UPDATE ON core_checklisttemplate
                    BEGIN UPDATE core_checklisttemplate SET name='tampered' WHERE id=NEW.id; END;
                ''')
            with self.assertRaisesRegex(ValueError, 'trigger'):
                fixture.assert_retained(before, after_path, source_database=before_path)

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


class CompanyScopeMigrationRetentionIntegrationTests(TransactionTestCase):
    databases = {'default'}

    def test_actual_0063_migration_retains_existing_template_and_scopes_unique_project_owner(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        baseline = [('core', '0062_release_notice_acknowledgement')]
        executor.migrate(baseline)
        historical = executor.loader.project_state(baseline).apps
        Company = historical.get_model('core', 'Company')
        Template = historical.get_model('core', 'ChecklistTemplate')
        Project = historical.get_model('core', 'Project')
        company = Company.objects.create(name='Synthetic retention company')
        template = Template.objects.create(name='Synthetic retained template', definition={'title': 'retained'})
        Project.objects.create(name='Synthetic retained project', company=company, checklist_template=template)

        with tempfile.TemporaryDirectory() as directory:
            before_path = Path(directory) / 'before.sqlite3'
            after_path = Path(directory) / 'after.sqlite3'
            with closing(sqlite3.connect(before_path)) as destination:
                connection.connection.backup(destination)
            before = importlib.util.spec_from_file_location(
                'actual_migration_retention_fixture', ROOT / 'deploy/customer/upgrade_fixture.py')
            fixture = importlib.util.module_from_spec(before)
            before.loader.exec_module(fixture)
            retained_before = fixture.snapshot(before_path)

            try:
                MigrationExecutor(connection).migrate([('core', '0063_checklist_template_company_scope')])
                with closing(sqlite3.connect(after_path)) as destination:
                    connection.connection.backup(destination)
                proof = fixture.assert_retained(retained_before, after_path, source_database=before_path)
                self.assertEqual(proof['company_scoped_templates'], 1)
            finally:
                MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())
