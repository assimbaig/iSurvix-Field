"""Operational recovery tests use isolated SQLite/media, never live survey data."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch
from contextlib import closing

from django.contrib.auth.models import User
from django.core.management import call_command, CommandError
from io import StringIO
from types import SimpleNamespace
from datetime import timedelta
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import Profile


class BackupRecoveryTests(SimpleTestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[2]/'.local'/'ops-tests'
        base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.media=self.root/'media';self.media.mkdir()
        (self.media/'photos').mkdir();(self.media/'photos'/'original.jpg').write_bytes(b'SYNTHETIC-ORIGINAL')
        (self.media/'outputs').mkdir();(self.media/'outputs'/'draft.pdf').write_bytes(b'%PDF-SYNTHETIC-RESULT')
        self.database=self.root/'source.sqlite3'
        with sqlite3.connect(self.database) as db:
            db.execute('create table preserved (id integer primary key, kind text, value text)')
            db.executemany('insert into preserved values (?,?,?)',[(1,'queued','job-checkpoint'),(2,'human','review-record')])
        db.close()
        self.backup=self.root/'backup';self.restored=self.root/'restored'

    def create(self, **overrides):
        from .operations_backup import create_backup
        values=dict(release_id='a'*40,quiesced=True);values.update(overrides)
        return create_backup(self.database,self.media,self.backup,**values)

    def test_backup_and_restore_keep_originals_results_and_database_records(self):
        from .operations_backup import restore_backup
        original=self.database.read_bytes();self.create()
        restore_backup(self.backup,self.restored)
        self.assertEqual(self.database.read_bytes(),original)
        self.assertEqual((self.restored/'media/photos/original.jpg').read_bytes(),b'SYNTHETIC-ORIGINAL')
        self.assertEqual((self.restored/'media/outputs/draft.pdf').read_bytes(),b'%PDF-SYNTHETIC-RESULT')
        with sqlite3.connect(self.restored/'database.sqlite3') as db:
            self.assertEqual(db.execute('select * from preserved order by id').fetchall(),[(1,'queued','job-checkpoint'),(2,'human','review-record')])
        db.close()

    def test_quiescence_confirmation_required_before_backup(self):
        with self.assertRaises(ValueError):self.create(quiesced=False)
        self.assertFalse(self.backup.exists())

    def test_backup_cannot_overwrite_existing_directory(self):
        self.backup.mkdir();marker=self.backup/'keep';marker.write_text('preserve')
        with self.assertRaises(ValueError):self.create()
        self.assertEqual(marker.read_text(),'preserve')

    def test_backup_cannot_recurse_inside_media(self):
        self.backup=self.media/'nested-backup'
        with self.assertRaises(ValueError):self.create()
        self.assertFalse(self.backup.exists())

    def test_corrupt_file_is_rejected_before_restore_target_is_created(self):
        from .operations_backup import restore_backup
        self.create();(self.backup/'media/photos/original.jpg').write_bytes(b'CORRUPTED')
        with self.assertRaises(ValueError):restore_backup(self.backup,self.restored)
        self.assertFalse(self.restored.exists())

    def test_missing_media_file_is_not_a_successful_restore(self):
        from .operations_backup import restore_backup
        self.create();(self.backup/'media/outputs/draft.pdf').unlink()
        with self.assertRaises(ValueError):restore_backup(self.backup,self.restored)
        self.assertFalse(self.restored.exists())

    def test_unknown_extra_file_is_not_ignored(self):
        from .operations_backup import restore_backup
        self.create();(self.backup/'unlisted-secret').write_text('SYNTHETIC')
        with self.assertRaises(ValueError):restore_backup(self.backup,self.restored)
        self.assertFalse(self.restored.exists())

    def test_restoration_never_overwrites_an_existing_target(self):
        from .operations_backup import restore_backup
        self.create();self.restored.mkdir();(self.restored/'keep').write_text('original')
        with self.assertRaises(ValueError):restore_backup(self.backup,self.restored)
        self.assertEqual((self.restored/'keep').read_text(),'original')

    def test_path_traversal_and_windows_alias_manifests_are_rejected_before_writing(self):
        from .operations_backup import restore_backup
        self.create();manifest=self.backup/'manifest.json';original=json.loads(manifest.read_text())
        for name in ['../outside','media/CON.txt','media/folder./file','media/A~1.jpg','media/x\\y']:
            data=json.loads(json.dumps(original));data['files'][name]={'size':1,'sha256':hashlib.sha256(b'x').hexdigest()}
            manifest.write_text(json.dumps(data))
            with self.subTest(name=name),self.assertRaises(ValueError):restore_backup(self.backup,self.restored)
            self.assertFalse(self.restored.exists())
        manifest.write_text(json.dumps(original))

    def test_manifest_release_and_database_integrity_are_checked(self):
        from .operations_backup import restore_backup
        self.create();manifest=self.backup/'manifest.json';data=json.loads(manifest.read_text())
        data['release_id']='not-a-reviewed-release';manifest.write_text(json.dumps(data))
        with self.assertRaises(ValueError):restore_backup(self.backup,self.restored)

    def test_backup_and_restore_management_commands_copy_real_sqlite_and_media(self):
        config=SimpleNamespace(DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':str(self.database)}},MEDIA_ROOT=self.media)
        output=StringIO()
        with patch('core.management.commands.staging_backup.settings',config),patch('core.management.commands.staging_backup.release_id',return_value='a'*40):
            call_command('staging_backup',destination=str(self.backup),quiesced=True,stdout=output)
        self.assertEqual(json.loads(output.getvalue())['status'],'complete')
        call_command('staging_restore',backup=str(self.backup),destination=str(self.restored),stdout=StringIO())
        self.assertEqual((self.restored/'media/outputs/draft.pdf').read_bytes(),b'%PDF-SYNTHETIC-RESULT')
        with self.assertRaises(CommandError):
            call_command('staging_restore',backup=str(self.backup),destination=str(self.restored),stdout=StringIO())

    def test_failed_copy_leaves_no_complete_manifest_and_preserves_original(self):
        with patch('core.operations_backup._copy',side_effect=OSError('Synthetic disk failure')):
            with self.assertRaises(OSError):self.create()
        self.assertFalse((self.backup/'manifest.json').exists())
        self.assertTrue((self.backup/'INCOMPLETE').exists())
        self.assertEqual((self.media/'photos/original.jpg').read_bytes(),b'SYNTHETIC-ORIGINAL')

    def test_database_corruption_is_rejected_even_with_recomputed_file_hash(self):
        from .operations_backup import restore_backup
        self.create();database=self.backup/'database.sqlite3';database.write_bytes(b'NOT A SQLITE DATABASE')
        manifest=self.backup/'manifest.json';data=json.loads(manifest.read_text())
        data['files']['database.sqlite3']={'size':database.stat().st_size,'sha256':hashlib.sha256(database.read_bytes()).hexdigest()}
        manifest.write_text(json.dumps(data))
        with self.assertRaises(ValueError):restore_backup(self.backup,self.restored)
        self.assertFalse(self.restored.exists())


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False,ISURVIX_RELEASE_ID='b'*40,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OperationalHealthTests(TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[2]/'.local'/'ops-tests';base.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(dir=base);self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.media=self.root/'media';self.media.mkdir();self.static=self.root/'static';self.static.mkdir()
        options=override_settings(MEDIA_ROOT=self.media,STATIC_ROOT=self.static)
        options.enable();self.addCleanup(options.disable)
        self.owner=User.objects.create_superuser('ops-owner','owner@example.test','Fixture849!')
        self.engineer=User.objects.create_user('ops-engineer',password='Fixture849!')

    def test_public_liveness_discloses_only_status_and_reviewed_release(self):
        response=self.client.get(reverse('operations_live'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),{'status':'ok','release':'b'*40})
        self.assertIn('no-store',response.headers['Cache-Control'])

    def test_readiness_checks_applied_database_and_persistent_directories_without_ai(self):
        response=self.client.get(reverse('operations_ready'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),{'status':'ready','release':'b'*40})

    def test_readiness_reports_unavailable_without_private_error_details(self):
        with patch('core.operations_service.database_ready',side_effect=RuntimeError('SECRET:/private/database')):
            response=self.client.get(reverse('operations_ready'))
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json(),{'status':'unavailable','release':'b'*40})
        self.assertNotIn(b'SECRET',response.content)

    def test_readiness_failure_has_safe_request_correlation_without_exception_payload(self):
        with patch('core.operations_service.database_ready',side_effect=RuntimeError('SECRET-RAW-DATABASE-PATH')):
            with self.assertLogs('core.operations_service',level='WARNING') as captured:
                response=self.client.get(reverse('operations_ready'),HTTP_X_REQUEST_ID='c'*32)
        self.assertEqual(response.headers.get('X-Request-ID'),'c'*32)
        self.assertEqual(captured.records[0].request_id,'c'*32)
        self.assertNotIn('SECRET',str(captured.output))

    def test_missing_media_and_pending_migrations_are_not_ready(self):
        self.media.rmdir()
        self.assertEqual(self.client.get(reverse('operations_ready')).status_code,503)
        self.media.mkdir()
        with patch('core.operations_service.database_ready',return_value=False):
            self.assertEqual(self.client.get(reverse('operations_ready')).status_code,503)

    def test_customer_and_inactive_owner_cannot_inspect_operations(self):
        self.assertEqual(self.client.get(reverse('operations_status')).status_code,302)
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.get(reverse('operations_status')).status_code,403)
        self.client.force_login(self.owner)
        User.objects.filter(pk=self.owner.pk).update(is_active=False)
        self.assertNotEqual(self.client.get(reverse('operations_status')).status_code,200)

    def test_owner_gets_counts_without_survey_payloads_and_reads_do_not_mutate_state(self):
        self.client.force_login(self.owner)
        from .models import GovernanceAudit
        before=GovernanceAudit.objects.count()
        response=self.client.get(reverse('operations_status'))
        self.assertEqual(response.status_code,200)
        self.assertIn('survey_jobs',response.json())
        for forbidden in ['secret','token','model','payload','email','filename','lease_owner']:
            self.assertNotIn('"'+forbidden+'"',response.content.decode())
        self.assertEqual(GovernanceAudit.objects.count(),before)
        self.assertIn('no-store',response.headers['Cache-Control'])

    def test_queued_jobs_are_not_stale_and_photo_running_completed_counts_are_visible(self):
        from django.utils import timezone
        from .models import Company,Project,Checklist
        from .photo_models import PhotoJob
        from .survey_processing_models import SurveyProcessingJob,SurveyProcessingRevision
        company=Company.objects.create(name='Synthetic operations company')
        project=Project.objects.create(name='Synthetic operations project',company=company)
        checklist=Checklist.objects.create(user=self.engineer,project=project,site_id='SYNTHETIC-OPS')
        for number,status in enumerate(['queued','analysing_evidence'],1):
            revision=SurveyProcessingRevision.objects.create(checklist=checklist,number=number,digest=str(number)*64,snapshot={},submitted_by=self.engineer)
            SurveyProcessingJob.objects.create(revision=revision,status=status,model='synthetic',lease_until=timezone.now()-timedelta(seconds=1) if status!='queued' else None)
        for status in ['queued','running','completed']:
            PhotoJob.objects.create(checklist=checklist,status=status,model='synthetic')
        self.client.force_login(self.owner);data=self.client.get(reverse('operations_status')).json()
        self.assertEqual(data['stale_survey_jobs'],1)
        self.assertEqual(data['survey_jobs']['queued'],1)
        self.assertEqual(data['photo_jobs'],{'queued':1,'running':1,'completed':1})


from . import test_remote_survey_worker as remote_fixtures
from django.test import LiveServerTestCase


@override_settings(**remote_fixtures.SETTINGS)
class OperationsSavedWorkflowRecoveryTests(remote_fixtures.Fixtures,LiveServerTestCase):
    """Real HTTP/image/checkpoint/export fixture; only inference is controlled."""
    host='127.0.0.1'
    worker=remote_fixtures.RemoteSurveyHTTPIntegrationTests.worker
    controlled_inference=remote_fixtures.RemoteSurveyHTTPIntegrationTests.controlled_inference

    def test_snapshot_restores_completed_survey_originals_results_drafts_and_audit(self):
        from django.conf import settings
        from django.db import connection
        from .operations_backup import create_backup,restore_backup
        from .survey_processing_models import SurveyDrawingSet
        inference=self.controlled_inference()
        self.assertTrue(self.worker().process_once())
        self.assertEqual(inference.call_count,2)
        self.revision.processing_job.refresh_from_db()
        self.assertEqual(self.revision.processing_job.status,'ready_for_review')
        drawing=SurveyDrawingSet.objects.get(revision=self.revision)
        self.assertFalse(drawing.released)
        self.assertTrue(Path(drawing.manifest['pdf']).is_file())
        self.assertTrue(all(Path(x['dxf']).is_file() for x in drawing.manifest['sheets']))
        media=Path(settings.MEDIA_ROOT)
        expected={p.relative_to(media).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in media.rglob('*') if p.is_file()}
        base=Path(__file__).resolve().parents[2]/'.local'/'ops-tests';base.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(dir=base);self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);database=root/'captured.sqlite3'
        connection.ensure_connection()
        with closing(sqlite3.connect(database)) as target:connection.connection.backup(target)
        create_backup(database,media,root/'backup',release_id='a'*40,quiesced=True)
        restore_backup(root/'backup',root/'restored')
        with closing(sqlite3.connect(database)) as original,closing(sqlite3.connect(root/'restored/database.sqlite3')) as recovered:
            self.assertEqual(list(original.iterdump()),list(recovered.iterdump()))
        restored=root/'restored/media'
        actual={p.relative_to(restored).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in restored.rglob('*') if p.is_file()}
        self.assertEqual(actual,expected)
        self.assertEqual({p.relative_to(media).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in media.rglob('*') if p.is_file()},expected)
        self.assertFalse(any(item['accepted'] for item in self.revision.processing_result.payload['checklist_items']))
