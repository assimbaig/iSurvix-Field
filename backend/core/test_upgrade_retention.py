"""Upgrade proof checks old row values, not merely a successful migration exit."""
import importlib.util
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings


ROOT = Path(__file__).resolve().parents[2]


class UpgradeRetentionProofTests(SimpleTestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('upgrade_fixture', ROOT / 'deploy/customer/upgrade_fixture.py')
        self.proof = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.proof)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / '.local')
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'synthetic.sqlite3'
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('create table retained_review(id integer primary key, answer text, original_hash text)')
            db.execute("insert into retained_review values(1,'human answer','source-hash')")
            db.execute('create table core_governanceaudit(id integer primary key, action text)')
            db.execute("insert into core_governanceaudit values(1,'original-event')")

    def test_upgrade_allows_append_only_audit_and_new_tables_without_losing_old_rows(self):
        before = self.proof.snapshot(self.path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("insert into core_governanceaudit values(2,'update-event')")
            db.execute('create table additive_new_model(id integer primary key)')
        self.proof.assert_retained(before, self.path)

    def test_changed_answer_deleted_row_or_changed_original_hash_fails_upgrade_proof(self):
        before = self.proof.snapshot(self.path)
        for statement in ["update retained_review set answer='AI overwrite'", "update retained_review set original_hash='different'", 'delete from retained_review']:
            with self.subTest(statement=statement):
                with closing(sqlite3.connect(self.path)) as db, db:
                    db.execute(statement)
                with self.assertRaises(ValueError):
                    self.proof.assert_retained(before, self.path)
                with closing(sqlite3.connect(self.path)) as db, db:
                    db.execute('delete from retained_review')
                    db.execute("insert into retained_review values(1,'human answer','source-hash')")


class UpgradeSyntheticFixtureIntegration(TestCase):
    def test_only_explicit_pristine_fixture_can_create_retained_survey_evidence_and_job(self):
        from django.contrib.auth import get_user_model
        from core.models import Checklist, PhotoEvidence, PhotoPlacement
        from core.survey_processing_models import SurveyDocument, SurveyProcessingRevision, SurveyProcessingJob
        spec = importlib.util.spec_from_file_location('upgrade_fixture_seed', ROOT / 'deploy/customer/upgrade_fixture.py')
        proof = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(proof)
        get_user_model().objects.create_superuser('synthetic_owner', 'owner@example.test', None)
        with tempfile.TemporaryDirectory(dir=ROOT / '.local') as temporary, override_settings(MEDIA_ROOT=temporary):
            with patch.dict('os.environ', {'ISURVIX_DISPOSABLE_REHEARSAL': 'no'}), self.assertRaises(ValueError):
                proof.seed()
            self.assertEqual(Checklist.objects.count(), 0)
            with patch.dict('os.environ', {'ISURVIX_DISPOSABLE_REHEARSAL': 'yes'}):
                receipt = proof.seed(engineer_password='synthetic-test-only')
                self.assertTrue(get_user_model().objects.get(username='synthetic_retained_engineer').check_password('synthetic-test-only'))
                self.assertEqual(receipt['native_ai_calls'], 0)
                self.assertEqual(PhotoEvidence.objects.count(), 3)
                self.assertEqual(SurveyDocument.objects.count(), 1)
                self.assertEqual(PhotoPlacement.objects.get().status, 'manual')
                self.assertEqual(SurveyProcessingRevision.objects.count(), 1)
                self.assertEqual(SurveyProcessingJob.objects.get().status, 'queued')
                self.assertEqual(Checklist.objects.get().answer_data['custom']['notes'], 'Human fixture remark: retain exactly.')
                with self.assertRaises(ValueError):
                    proof.seed()
                self.assertEqual(Checklist.objects.count(), 1)
