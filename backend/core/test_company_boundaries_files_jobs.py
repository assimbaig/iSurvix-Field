"""Real isolated company-boundary HTTP/file/job and machine-credential checks."""
import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from django.contrib.auth.models import User
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from . import remote_worker_service as bridge, survey_processing as pipeline
from . import test_survey_processing as fixture
from .models import Checklist, Company, PhotoEvidence, Profile, Project
from .remote_worker_models import RemoteWorkerCredential
from .survey_processing_models import SurveyDocument, SurveyDrawingSet, SurveyProcessingJob, SurveySourceAnalysis


SETTINGS = dict(SECRET_KEY='company-boundary-files-jobs', ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], OLLAMA_MODEL='qwen3.5:4b')


class BoundaryFixture:
    person = fixture.SurveyProcessingTests.person
    request = fixture.SurveyProcessingTests.request
    add_photo = fixture.SurveyProcessingTests.add_photo

    def setUp(self):
        fixture.SurveyProcessingTests.setUp(self)
        self.company_b = Company.objects.create(name='Boundary employer B')
        self.project_b = Project.objects.create(name='Boundary B project', company=self.company_b,
                                               checklist_template=self.template)
        self.engineer_b = self.person('boundary_engineer_b', Profile.Roles.ENGINEER, self.project_b)
        self.admin_b = self.person('boundary_admin_b', Profile.Roles.ADMIN, self.project_b)
        self.project_b.administrator = self.admin_b
        self.project_b.save(update_fields=['administrator'])
        self.checklist_b = Checklist.objects.create(project=self.project_b, user=self.engineer_b,
            site_id='SYNTHETIC-COMPANY-B', answer_data={'custom': {'contact': 'B contact'}})
        self.identity = {'versions': bridge.versions(), 'model': 'qwen3.5:4b', 'model_digest': 'd' * 64}
        self.quality_b = self.person('boundary_quality_b', Profile.Roles.QUALITY_ENGINEER, self.project_b)
        self.lead_b = self.person('boundary_lead_b', Profile.Roles.TEAM_LEAD, self.project_b)
        self.customer_b = self.person('boundary_client_b', Profile.Roles.CLIENT, self.project_b)
        self.checklist_b.quality_reviewer = self.quality_b
        self.checklist_b.save(update_fields=['quality_reviewer'])

    def browser(self, actor):
        client = Client()
        client.force_login(actor)
        return client

    def issue(self):
        return bridge.provision(self.admin, [self.project.pk])

    def assets(self, checklist=None, engineer=None, photo=None):
        checklist, engineer = checklist or self.checklist, engineer or self.engineer
        if photo is None and checklist.pk == self.checklist.pk:
            photo = self.photo
        if photo is None:
            content = BytesIO()
            Image.new('RGB', (40, 30), 'red').save(content, 'PNG')
            photo = PhotoEvidence.objects.create(checklist=checklist, uploaded_by=engineer,
                filename='synthetic-company-b.png', sha256=hashlib.sha256(content.getvalue()).hexdigest())
            photo.original.save(photo.filename, ContentFile(content.getvalue()))
        raw = Path(photo.original.path).read_bytes()
        photo.metadata = {'format': 'PNG'}
        photo.preview.save('preview.png', ContentFile(raw))
        photo.save(update_fields=['metadata'])
        doc = SurveyDocument(checklist=checklist, uploaded_by=engineer, filename='support.png',
            sha256=hashlib.sha256(raw).hexdigest(), content_type='image/png', size=len(raw))
        doc.original.save(doc.filename, ContentFile(raw), save=False)
        doc.save()
        revision, _ = pipeline.submit(self.request(engineer), checklist.pk, True)
        payload = {'preview_file': photo.preview.name, 'source_id': f'photo:{photo.pk}', 'reference': 'Synthetic file'}
        source = SurveySourceAnalysis.objects.create(revision=revision, source_id=f'photo:{photo.pk}',
            payload=payload, digest=pipeline.digest(payload))
        folder = Path(settings.MEDIA_ROOT) / 'survey_processing' / f'boundary-{checklist.pk}'
        folder.mkdir(parents=True, exist_ok=True)
        paths = {}
        for kind in ['pdf', 'dxf', 'preview', 'bundle']:
            path = folder / ('synthetic.' + kind)
            path.write_bytes(f'Owned by fixture checklist {checklist.pk}: {kind}'.encode())
            paths[kind] = str(path.resolve())
        manifest = {'pdf': paths['pdf'], 'bundle': paths['bundle'],
            'sheets': [{'dxf': paths['dxf'], 'preview': paths['preview']}],
            'file_hashes': {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in paths.values()}}
        output = SurveyDrawingSet.objects.create(revision=revision, edition=1,
            review_digest='synthetic-unreleased', geometry={'sheets': []}, manifest=manifest)
        checklist.image_data = {'legacy': [photo.original.name]}
        checklist.branding_snapshot = {'clients': [{'name': 'Fixture client', 'logo': photo.original.name}]}
        checklist.save(update_fields=['image_data', 'branding_snapshot'])
        urls = [reverse('photo_evidence', args=[checklist.pk, photo.pk, variant]) for variant in ['original', 'preview']]
        urls += [reverse('survey_processing_document', args=[checklist.pk, doc.pk]),
            reverse('survey_processing_source', args=[checklist.pk, source.pk]),
            reverse('private_checklist_file', args=[checklist.pk]) + '?path=' + photo.original.name,
            reverse('custom_client_logo', args=[checklist.pk, 0])]
        urls += [reverse('survey_processing_output', args=[checklist.pk, output.pk, 0, kind])
                 for kind in ['pdf', 'dxf', 'preview', 'bundle']]
        expected_bytes = dict(zip(urls[:6], [raw] * 6))
        expected_bytes.update({url: Path(paths[kind]).read_bytes()
            for url, kind in zip(urls[6:], ['pdf', 'dxf', 'preview', 'bundle'])})
        return {'checklist': checklist, 'photo': photo, 'document': doc, 'revision': revision,
                'analysis': source, 'output': output, 'urls': urls, 'expected_bytes': expected_bytes,
                'original_sha': hashlib.sha256(raw).hexdigest()}


@override_settings(**SETTINGS)
class CompanyRecordFileJobTests(BoundaryFixture, TestCase):
    def read(self, client, url):
        response = client.get(url)
        content = b''.join(response.streaming_content) if getattr(response, 'streaming', False) else response.content
        response.close()
        return response.status_code, content

    def test_company_a_roles_cannot_read_company_b_saved_files_or_record_progress(self):
        target = self.assets(self.checklist_b, self.engineer_b)
        before = list(SurveyProcessingJob.objects.values())
        for actor in [self.engineer, self.quality, self.lead, self.admin, self.customer]:
            browser = self.browser(actor)
            for url in target['urls'] + [reverse('survey_processing_state', args=[self.checklist_b.pk]),
                    reverse('survey_processing_progress', args=[self.checklist_b.pk]),
                    reverse('photo_state', args=[self.checklist_b.pk])]:
                with self.subTest(role=actor.profile.role, url=url):
                    status, content = self.read(browser, url)
                    self.assertIn(status, (403, 404))
                    self.assertNotIn(b'Boundary B project', content)
        self.assertEqual(list(SurveyProcessingJob.objects.values()), before)
        self.assertEqual(hashlib.sha256(Path(target['photo'].original.path).read_bytes()).hexdigest(), target['original_sha'])

    def test_own_company_internal_roles_keep_real_saved_asset_bytes_and_foreign_company_is_denied(self):
        assets = self.assets()
        for actor in [self.engineer, self.quality, self.lead, self.admin]:
            browser = self.browser(actor)
            for url in assets['urls']:
                with self.subTest(role=actor.profile.role, url=url):
                    status, content = self.read(browser, url)
                    self.assertEqual(status, 200)
                    self.assertEqual(content, assets['expected_bytes'][url])
        for actor in [self.engineer_b, self.quality_b, self.lead_b, self.admin_b, self.customer_b]:
            for url in assets['urls']:
                with self.subTest(role=actor.profile.role, url=url):
                    self.assertIn(self.read(self.browser(actor), url)[0], (403, 404))

    def test_nested_foreign_photo_document_analysis_output_and_revision_ids_are_not_accepted(self):
        own, other = self.assets(), self.assets(self.checklist_b, self.engineer_b)
        browser = self.browser(self.admin)
        own_state = reverse('survey_processing_state', args=[self.checklist.pk]) + '?compact=1&revision_id=' + str(own['revision'].pk)
        self.assertEqual(self.read(browser, own_state)[0], 200)
        urls = [reverse('photo_evidence', args=[self.checklist.pk, other['photo'].pk, 'original']),
                reverse('survey_processing_document', args=[self.checklist.pk, other['document'].pk]),
                reverse('survey_processing_source', args=[self.checklist.pk, other['analysis'].pk]),
                reverse('survey_processing_output', args=[self.checklist.pk, other['output'].pk, 0, 'pdf']),
                reverse('survey_processing_state', args=[self.checklist.pk]) + '?compact=1&revision_id=' + str(other['revision'].pk)]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.read(browser, url)[0], 404)

    def test_client_cannot_read_unreleased_output_or_foreign_raw_media(self):
        target = self.assets()
        Checklist.objects.filter(pk=self.checklist.pk).update(status=Checklist.Status.FINAL)
        browser = self.browser(self.customer)
        for kind in ['pdf', 'dxf', 'preview', 'bundle']:
            url = reverse('survey_processing_output', args=[self.checklist.pk, target['output'].pk, 0, kind])
            self.assertEqual(self.read(browser, url)[0], 404)
        self.assertEqual(self.read(browser, reverse('photo_evidence', args=[self.checklist.pk, self.photo.pk, 'original']))[0], 200)
        for actor in [self.engineer, self.admin, self.customer]:
            self.assertEqual(self.read(self.browser(actor), '/media/' + self.photo.original.name)[0], 404)

    def test_foreign_company_cannot_retry_or_change_job_controls(self):
        target = self.assets(self.checklist_b, self.engineer_b)
        before = list(SurveyProcessingJob.objects.values())
        before_events = target['revision'].processing_events.count()
        for actor in [self.engineer, self.quality, self.lead, self.admin, self.customer]:
            browser = self.browser(actor)
            for action in ['retry', 'pause', 'resume', 'accept', 'release']:
                response = browser.post(reverse('survey_processing_action', args=[self.checklist_b.pk]),
                    {'action': action, 'revision_id': target['revision'].pk})
                self.assertIn(response.status_code, (403, 404))
        self.assertEqual(list(SurveyProcessingJob.objects.values()), before)
        self.assertEqual(target['revision'].processing_events.count(), before_events)


@override_settings(**SETTINGS)
class CompanyWorkerTenantTests(BoundaryFixture, TestCase):
    def test_new_worker_credential_remembers_issuing_company(self):
        credential, _ = self.issue()
        self.assertEqual(credential.issuing_company_id, self.company.pk)

    def test_old_company_token_cannot_follow_issuer_and_project_to_another_company(self):
        credential, token = self.issue()
        # Reproduce a retained credential across an explicit legacy reclassification;
        # no customer data or live credential is used by this isolated fixture.
        Project.objects.filter(pk=self.project.pk).update(company=self.company_b)
        Profile.objects.filter(user=self.admin).update(company=self.company_b)
        self.project.refresh_from_db()
        self.engineer_b.profile.project = self.project
        self.engineer_b.profile.save(update_fields=['project'])
        candidate = Checklist.objects.create(project=self.project, user=self.engineer_b,
            site_id='NEW-TENANT-SUBMISSION', answer_data={'custom': {'contact': 'New tenant'}})
        raw = Path(self.photo.original.path).read_bytes()
        photo = PhotoEvidence.objects.create(checklist=candidate, uploaded_by=self.engineer_b,
            filename='new-tenant.png', sha256=hashlib.sha256(raw).hexdigest())
        photo.original.save(photo.filename, ContentFile(raw))
        revision, _ = pipeline.submit(self.request(self.engineer_b), candidate.pk, True)
        response = Client(HTTP_AUTHORIZATION='Bearer ' + token).post(reverse('remote_worker_claim'),
            json.dumps(self.identity), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status, 'queued')
        self.assertEqual(revision.processing_job.attempts, 0)

    def test_authenticated_current_company_worker_keeps_own_job_access(self):
        credential, token = self.issue()
        revision, _ = pipeline.submit(self.request(), self.checklist.pk, True)
        response = Client(HTTP_AUTHORIZATION='Bearer ' + token).post(reverse('remote_worker_claim'),
            json.dumps(self.identity), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['job']['revision_id'], revision.pk)

    def test_foreign_credential_cannot_claim_or_touch_another_company_job(self):
        credential, token = bridge.provision(self.admin_b, [self.project_b.pk])
        revision, _ = pipeline.submit(self.request(), self.checklist.pk, True)
        before = list(SurveyProcessingJob.objects.values())
        remote = Client(HTTP_AUTHORIZATION='Bearer ' + token)
        response = remote.post(reverse('remote_worker_claim'), json.dumps(self.identity),
                               content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['job'])
        for name in ['remote_worker_heartbeat', 'remote_worker_next', 'remote_worker_failure']:
            response = remote.post(reverse(name, args=[revision.processing_job.pk]),
                json.dumps({'code': 'local_unavailable'}), content_type='application/json',
                HTTP_X_WORKER_LEASE='00000000-0000-0000-0000-000000000000')
            self.assertIn(response.status_code, (403, 404))
        self.assertEqual(list(SurveyProcessingJob.objects.values()), before)

    def test_unknown_legacy_pin_is_denied_without_deleting_jobs_or_credential(self):
        credential, token = self.issue()
        revision, _ = pipeline.submit(self.request(), self.checklist.pk, True)
        RemoteWorkerCredential.objects.filter(pk=credential.pk).update(issuing_company=None)
        before = list(SurveyProcessingJob.objects.values())
        response = Client(HTTP_AUTHORIZATION='Bearer ' + token).post(reverse('remote_worker_claim'),
            json.dumps(self.identity), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(RemoteWorkerCredential.objects.filter(pk=credential.pk).exists())
        self.assertEqual(list(SurveyProcessingJob.objects.values()), before)

    def test_company_pin_cannot_be_reassigned_through_model_save(self):
        credential, _ = self.issue()
        credential.issuing_company = self.company_b
        with self.assertRaises(ValidationError):
            credential.save()
        credential.refresh_from_db()
        self.assertEqual(credential.issuing_company_id, self.company.pk)

    def test_retained_service_credential_rechecks_current_tenant_and_revocation(self):
        credential, _ = self.issue()
        self.assertEqual(bridge._projects(credential), [self.project.pk])
        Profile.objects.filter(user=self.admin).update(company=self.company_b)
        with self.assertRaises(PermissionDenied):
            bridge._projects(credential)
        Profile.objects.filter(user=self.admin).update(company=self.company)
        RemoteWorkerCredential.objects.filter(pk=credential.pk).update(revoked_at=timezone.now())
        with self.assertRaises(PermissionDenied):
            bridge._projects(credential)

    def test_worker_input_and_result_endpoints_enforce_company_even_with_a_known_valid_foreign_lease(self):
        own, own_token = self.issue()
        other, other_token = bridge.provision(self.admin_b, [self.project_b.pk])
        revision, _ = pipeline.submit(self.request(), self.checklist.pk, True)
        claimed = bridge.claim(own, self.identity)
        task = bridge.next_task(own, claimed['job_id'], claimed['lease'])
        url = reverse('remote_worker_image', args=[claimed['job_id'], task['task_id']])
        response = Client(HTTP_AUTHORIZATION='Bearer ' + own_token,
            HTTP_X_WORKER_LEASE=claimed['lease']).get(url)
        self.assertEqual(response.status_code, 200)
        content = b''.join(response.streaming_content)
        response.close()
        self.assertEqual(hashlib.sha256(content).hexdigest(), task['image_sha256'])
        before = list(SurveyProcessingJob.objects.values())
        original = hashlib.sha256(Path(self.photo.original.path).read_bytes()).hexdigest()
        foreign = Client(HTTP_AUTHORIZATION='Bearer ' + other_token, HTTP_X_WORKER_LEASE=claimed['lease'])
        self.assertEqual(foreign.get(url).status_code, 403)
        response = foreign.post(reverse('remote_worker_complete', args=[claimed['job_id'], task['task_id']]),
            json.dumps({'versions': bridge.versions(), 'input_digest': task['input_digest'],
                'result': {'source_id': task['input']['source_id']}}), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(list(SurveyProcessingJob.objects.values()), before)
        self.assertEqual(hashlib.sha256(Path(self.photo.original.path).read_bytes()).hexdigest(), original)


@override_settings(**SETTINGS)
class CompanyCredentialMigrationTests(TransactionTestCase):
    """No current-company guess can silently bless an old, tenantless token."""
    def setUp(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([('core', '0053_audit_append_only_options')])
        apps = self.executor.loader.project_state([('core', '0053_audit_append_only_options')]).apps
        self.old = apps
        UserModel, CompanyModel, ProjectModel, ProfileModel = [apps.get_model('auth', 'User'),
            apps.get_model('core', 'Company'), apps.get_model('core', 'Project'), apps.get_model('core', 'Profile')]
        self.admin = UserModel.objects.create(username='migration-company-admin')
        self.company = CompanyModel.objects.create(name='Migration employer A')
        self.other_company = CompanyModel.objects.create(name='Migration employer B')
        self.project = ProjectModel.objects.create(name='Migration tenant project', company=self.company,
                                                  administrator=self.admin)
        ProfileModel.objects.create(user=self.admin, role='ADMIN', project=self.project, company=self.company)

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def credential(self, proof=None):
        Credential = self.old.get_model('core', 'RemoteWorkerCredential')
        Audit = self.old.get_model('core', 'GovernanceAudit')
        row = Credential.objects.create(label='Retained worker', created_by=self.admin,
            secret_hash='d' * 64, expires_at=timezone.now() + timedelta(days=1))
        row.projects.add(self.project)
        details = {'credential_id': str(row.pk)}
        if proof is not None:
            details['company_id'] = proof
        Audit.objects.create(actor=self.admin, actor_name=self.admin.username,
            action='remote_worker.provisioned', project=self.project, details=details)
        return row

    def migrate(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('core', '0054_remote_worker_company_pin')])
        return executor.loader.project_state([('core', '0054_remote_worker_company_pin')]).apps

    def test_explicit_coherent_issuance_proof_can_backfill_without_changing_secret_or_scope(self):
        row = self.credential(self.company.pk)
        apps = self.migrate()
        saved = apps.get_model('core', 'RemoteWorkerCredential').objects.get(pk=row.pk)
        self.assertEqual(saved.issuing_company_id, self.company.pk)
        self.assertEqual(saved.secret_hash, 'd' * 64)
        self.assertEqual(list(saved.projects.values_list('pk', flat=True)), [self.project.pk])

    def test_missing_or_contradictory_issuance_proof_is_not_guessed_from_current_company(self):
        unknown = self.credential()
        contradictory = self.credential(self.other_company.pk)
        apps = self.migrate()
        Credential = apps.get_model('core', 'RemoteWorkerCredential')
        self.assertIsNone(Credential.objects.get(pk=unknown.pk).issuing_company_id)
        self.assertIsNone(Credential.objects.get(pk=contradictory.pk).issuing_company_id)
        self.assertEqual(Credential.objects.count(), 2)

    def test_partial_project_proof_and_boolean_company_id_do_not_authorize_legacy_binding(self):
        partial = self.credential(self.company.pk)
        extra = self.old.get_model('core', 'Project').objects.create(name='Unproven additional project',
            company=self.company, administrator=self.admin)
        partial.projects.add(extra)
        invalid = self.credential(True)
        apps = self.migrate()
        Credential = apps.get_model('core', 'RemoteWorkerCredential')
        self.assertIsNone(Credential.objects.get(pk=partial.pk).issuing_company_id)
        self.assertIsNone(Credential.objects.get(pk=invalid.pk).issuing_company_id)

    def test_nondefault_migration_uses_only_its_scratch_database(self):
        """Replay another tenant database without accidentally touching default."""
        sentinel = self.credential(self.company.pk)
        self.migrate()
        RemoteWorkerCredential.objects.filter(pk=sentinel.pk).update(issuing_company=None)
        default_before = list(RemoteWorkerCredential.objects.values())
        from django.db.backends.sqlite3.base import DatabaseWrapper
        alias = 'company_pin_disposable_replay'
        config = deepcopy(connection.settings_dict)
        config['NAME'] = ':memory:'
        # This independent in-memory connection is never the runner's operational
        # or default DB. Register it only for historical-model .using(alias).
        scratch = DatabaseWrapper(config, alias=alias)
        scratch.ensure_connection()
        connections[alias] = scratch
        try:
            executor = MigrationExecutor(scratch)
            executor.migrate([('core', '0053_audit_append_only_options')])
            apps = executor.loader.project_state([('core', '0053_audit_append_only_options')]).apps
            person = apps.get_model('auth', 'User').objects.using(alias).create(username='scratch-issuer')
            company = apps.get_model('core', 'Company').objects.using(alias).create(name='Scratch employer')
            project = apps.get_model('core', 'Project').objects.using(alias).create(name='Scratch project',
                company=company, administrator=person)
            apps.get_model('core', 'Profile').objects.using(alias).create(user=person, company=company,
                project=project, role='ADMIN')
            legacy = apps.get_model('core', 'RemoteWorkerCredential').objects.using(alias).create(
                created_by=person, label='Scratch token', secret_hash='e' * 64,
                expires_at=timezone.now() + timedelta(days=1))
            legacy.projects.add(project)
            apps.get_model('core', 'GovernanceAudit').objects.using(alias).create(actor=person,
                actor_name=person.username, action='remote_worker.provisioned', project=project,
                details={'credential_id': str(legacy.pk), 'company_id': company.pk})
            executor = MigrationExecutor(scratch)
            executor.migrate([('core', '0054_remote_worker_company_pin')])
            current = executor.loader.project_state([('core', '0054_remote_worker_company_pin')]).apps
            self.assertEqual(list(RemoteWorkerCredential.objects.values()), default_before)
            saved = current.get_model('core', 'RemoteWorkerCredential').objects.using(alias).get(pk=legacy.pk)
            self.assertEqual(saved.issuing_company_id, company.pk)
            other_tenant = current.get_model('core', 'Company').objects.using(alias).create(name='Second scratch tenant')
            runtime_record = RemoteWorkerCredential.objects.using(alias).get(pk=legacy.pk)
            runtime_record.issuing_company_id = other_tenant.pk
            with self.assertRaises(ValidationError):
                runtime_record.save(using=alias)
            self.assertEqual(list(RemoteWorkerCredential.objects.values()), default_before)
        finally:
            scratch.close()
            del connections[alias]
