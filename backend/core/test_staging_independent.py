"""Independent staging contracts: real files/SQLite and authenticated health HTTP.

These local checks never certify a clean Linux/VPS install or a public launch.
"""
import hashlib
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Profile
from . import test_engineer_category_submission_acceptance as survey_fixtures


ROOT = Path(__file__).resolve().parents[2]


class StagingSettingsIndependentTests(TestCase):
    def settings_process(self, changes=None):
        with tempfile.TemporaryDirectory(dir=ROOT / '.local') as directory:
            data = Path(directory)
            for name in ['media', 'static', 'upload-tmp']:
                (data / name).mkdir()
            secret = 'synthetic-staging-only-' + 'x' * 60
            secret_file = data / 'secret-key'
            secret_file.write_text(secret, encoding='utf-8')
            release_file = data / 'RELEASE'
            release_file.write_text('a' * 40, encoding='ascii')
            sqlite3.connect(data / 'database.sqlite3').close()
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith(('DJANGO_', 'ISURVIX_'))}
            env.update(PYTHONPATH=str(ROOT / 'backend'),
                       PYTHONDONTWRITEBYTECODE='1',
                       ISURVIX_DATA_ROOT=str(data),
                       DJANGO_SECRET_KEY_FILE=str(secret_file),
                       DJANGO_ALLOWED_HOSTS='staging.example.test',
                       DJANGO_CSRF_TRUSTED_ORIGINS='https://staging.example.test',
                       ISURVIX_RELEASE_ID='a' * 40,
                       ISURVIX_RELEASE_FILE=str(release_file),
                       DEBUG='False')
            env.update(changes or {})
            code = ('import json; import checklist.settings_staging as s; '
                    'print(json.dumps({"database":str(s.DATABASES["default"]["NAME"]),'
                    '"media":str(s.MEDIA_ROOT),"debug":s.DEBUG,'
                    '"secure":s.SESSION_COOKIE_SECURE,"local_ai":s.LOCAL_AI_ENABLED}))')
            process = subprocess.run([sys.executable, '-c', code], env=env,
                                     capture_output=True, text=True, timeout=20)
            self.assertNotIn(secret, process.stdout + process.stderr)
            return process, data

    def test_staging_uses_persistent_data_and_disables_native_inference(self):
        process, data = self.settings_process()
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(Path(result['database']), data / 'database.sqlite3')
        self.assertEqual(Path(result['media']), data / 'media')
        self.assertFalse(result['debug'])
        self.assertFalse(result['local_ai'])
        self.assertTrue(result['secure'])

    def test_unidentified_release_and_unbounded_hosts_fail_closed(self):
        for change in [{'ISURVIX_RELEASE_ID': ''}, {'DJANGO_ALLOWED_HOSTS': '*'}]:
            with self.subTest(change=change):
                process, _ = self.settings_process(change)
                self.assertNotEqual(process.returncode, 0)

    def test_public_debug_and_vps_native_inference_are_not_accepted(self):
        for change in [{'DEBUG': 'True'}, {'ISURVIX_LOCAL_AI_ENABLED': 'True'}]:
            with self.subTest(change=change):
                process, _ = self.settings_process(change)
                self.assertNotEqual(process.returncode, 0)


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class StagingHealthIndependentTests(TestCase):
    def test_public_liveness_contains_no_operational_details_or_model_access(self):
        response = self.client.get(reverse('operations_live'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        self.assertLessEqual(set(response.json()), {'status', 'release'})
        self.assertIn('no-store', response.headers['Cache-Control'])

    def test_public_readiness_failure_is_truthful_and_redacted(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.local') as directory:
            missing = str(Path(directory) / 'missing-private-media')
            with override_settings(MEDIA_ROOT=missing):
                response = self.client.get(reverse('operations_ready'))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['status'], 'unavailable')
        self.assertNotIn(missing, response.content.decode())
        self.assertLessEqual(set(response.json()), {'status', 'release'})

    def test_operational_diagnostics_are_platform_owner_only(self):
        url = reverse('operations_status')
        self.assertIn(self.client.get(url).status_code, (302, 403))
        customer = User.objects.create_user('staging_customer_admin')
        customer.profile.role = Profile.Roles.ADMIN
        customer.profile.save()
        self.client.force_login(customer)
        self.assertEqual(self.client.get(url).status_code, 403)
        owner = User.objects.create_superuser('staging_platform_owner', password='Synthetic-Only-827!')
        self.client.force_login(owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('secret', response.content.decode().lower())
        self.assertIn('no-store', response.headers['Cache-Control'])


class StagingRecoveryIndependentTests(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / '.local')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.database = self.root / 'source.sqlite3'
        with closing(sqlite3.connect(self.database)) as db:
            with db:
                db.execute('create table review (id integer primary key, decision text)')
                db.execute("insert into review values (1,'human-confirmed-synthetic')")
        self.media = self.root / 'media'
        (self.media / 'photos').mkdir(parents=True)
        (self.media / 'outputs').mkdir()
        self.original = b'UNCHANGED SYNTHETIC ORIGINAL EVIDENCE'
        self.output = b'%PDF-synthetic-versioned-output'
        (self.media / 'photos/original.bin').write_bytes(self.original)
        (self.media / 'outputs/revision-1.pdf').write_bytes(self.output)

    def backup(self):
        from .operations_backup import create_backup
        destination = self.root / 'backup'
        create_backup(self.database, self.media, destination, release_id='a'*40, quiesced=True)
        return destination

    def test_restore_keeps_originals_outputs_and_human_review_values(self):
        from .operations_backup import restore_backup
        backup = self.backup()
        destination = self.root / 'restored'
        restore_backup(backup, destination)
        self.assertEqual((destination / 'media/photos/original.bin').read_bytes(), self.original)
        self.assertEqual((destination / 'media/outputs/revision-1.pdf').read_bytes(), self.output)
        with closing(sqlite3.connect(destination / 'database.sqlite3')) as db:
            self.assertEqual(db.execute('select decision from review where id=1').fetchone()[0],
                             'human-confirmed-synthetic')
        self.assertEqual((self.media / 'photos/original.bin').read_bytes(), self.original)

    def test_backup_refuses_unquiesced_capture_without_creating_an_artifact(self):
        from .operations_backup import create_backup
        destination = self.root / 'unsafe-backup'
        with self.assertRaises(ValueError):
            create_backup(self.database, self.media, destination, release_id='a'*40)
        self.assertFalse(destination.exists())


    def test_corruption_is_rejected_before_publishing_restore(self):
        from .operations_backup import restore_backup
        backup = self.backup()
        (backup / 'media/photos/original.bin').write_bytes(b'CORRUPTED')
        destination = self.root / 'rejected'
        with self.assertRaises(ValueError):
            restore_backup(backup, destination)
        self.assertFalse(destination.exists())
        self.assertEqual((self.media / 'photos/original.bin').read_bytes(), self.original)

    def test_existing_restore_target_is_never_overwritten(self):
        from .operations_backup import restore_backup
        backup = self.backup()
        destination = self.root / 'existing'
        destination.mkdir()
        (destination / 'sentinel.txt').write_bytes(b'KEEP')
        with self.assertRaises(ValueError):
            restore_backup(backup, destination)
        self.assertEqual((destination / 'sentinel.txt').read_bytes(), b'KEEP')

    def test_missing_original_is_not_reported_as_successful_restore(self):
        from .operations_backup import restore_backup
        backup = self.backup()
        (backup / 'media/photos/original.bin').unlink()
        destination = self.root / 'missing-source'
        with self.assertRaises(ValueError):
            restore_backup(backup, destination)
        self.assertFalse(destination.exists())


@override_settings(SECRET_KEY='isolated-staging-survey-regression',
                   ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class StagingSurveyWorkflowIndependentTests(TestCase):
    setUp = survey_fixtures.EngineerCategorySubmissionAcceptanceTests.setUp
    person = survey_fixtures.EngineerCategorySubmissionAcceptanceTests.person
    add_photo = survey_fixtures.EngineerCategorySubmissionAcceptanceTests.add_photo
    raw = survey_fixtures.EngineerCategorySubmissionAcceptanceTests.raw
    post = survey_fixtures.EngineerCategorySubmissionAcceptanceTests.post
    state = survey_fixtures.EngineerCategorySubmissionAcceptanceTests.state
    upload = survey_fixtures.EngineerCategorySubmissionAcceptanceTests.upload
    submit = survey_fixtures.EngineerCategorySubmissionAcceptanceTests.submit
    assert_submitted = survey_fixtures.EngineerCategorySubmissionAcceptanceTests.assert_submitted
    qa_state = survey_fixtures.EngineerCategorySubmissionAcceptanceTests.qa_state
    qa_action = survey_fixtures.EngineerCategorySubmissionAcceptanceTests.qa_action
    route = survey_fixtures.EngineerCategorySubmissionAcceptanceTests.route
    complete_qa_manually = survey_fixtures.EngineerCategorySubmissionAcceptanceTests.complete_qa_manually

    def test_completed_upload_reaches_qa_and_manual_four_layer_review_despite_ai_failure(self):
        from .models import WorkAssignment
        self.upload('Civil')
        self.upload('Electrical', ('electrical-source',))
        self.upload('Tower', ('tower-source',))
        originals = {p.pk: Path(p.original.path).read_bytes()
                     for p in self.checklist.photo_evidence.all()}
        submitted, digest = self.submit()
        self.assertEqual(submitted.status_code, 201, submitted.content)
        revision = self.assert_submitted()
        self.assertEqual(revision.processing_job.status, 'queued')
        self.assertEqual(self.qa_state()['ai']['status'], 'queued')
        job = revision.processing_job
        job.status = 'failed'
        job.error = 'Synthetic worker disconnect; not a native model test'
        job.save(update_fields=['status', 'error'])
        self.complete_qa_manually()
        for reviewer in [self.quality, self.lead, self.customer]:
            response = self.route(reviewer, 'approve', 'Synthetic isolated acceptance only')
            self.assertEqual(response.status_code, 302, response.content)
        self.checklist.refresh_from_db(); self.assignment.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage, 'closed')
        self.assertEqual(self.assignment.status, WorkAssignment.Status.COMPLETED)
        self.assertEqual(self.checklist.processing_revisions.count(), 1)
        for photo in self.checklist.photo_evidence.all():
            self.assertEqual(Path(photo.original.path).read_bytes(), originals[photo.pk])
        self.assertEqual(self.checklist.submission_revisions.count(), 1)

    def test_private_upload_has_no_direct_media_or_foreign_project_bypass(self):
        self.upload('Civil')
        photo = self.checklist.photo_evidence.get()
        url = reverse('photo_evidence', args=[self.checklist.pk, photo.pk, 'original'])
        allowed = self.client.get(url)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(b''.join(allowed.streaming_content), self.raw('synthetic-one'))
        allowed.close()
        self.client.logout()
        self.assertIn(self.client.get(url).status_code, (302, 403, 404))
        self.assertEqual(self.client.get('/media/' + photo.original.name).status_code, 404)
        from .models import Company
        foreign = User.objects.create_user('staging_foreign_admin')
        profile=foreign.profile; profile.role=Profile.Roles.ADMIN
        profile.company=Company.objects.create(name='Foreign staging company')
        profile.save()
        self.client.force_login(foreign)
        self.assertIn(self.client.get(url).status_code, (403, 404))

