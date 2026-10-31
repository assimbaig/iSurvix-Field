"""Independent saved-settings and provider-routing acceptance, synthetic only.

Transport fixtures prove the contract, not native inference or paid API accuracy.
"""
import base64
from contextlib import contextmanager
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import threading
import time

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import Company, GovernanceAudit, IndustryCatalog, Profile


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentAISettingsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Independent AI company A')
        self.foreign = Company.objects.create(name='Independent AI company B')
        self.owner = User.objects.create_superuser('independent_ai_owner', password='Fixture-924!')
        self.admin = self.person('admin_a', Profile.Roles.ADMIN, self.company)
        self.admin_b = self.person('admin_b', Profile.Roles.ADMIN, self.foreign)
        self.client.force_login(self.admin)

    def person(self, name, role, company):
        person = User.objects.create_user('independent_ai_' + name)
        profile = person.profile
        profile.role = role
        profile.company = company
        profile.admin_industry = IndustryCatalog.objects.get(code='telecom')
        profile.save()
        return person

    def url(self, company=None):
        return reverse('ai_settings_company', args=[(company or self.company).pk])

    def form(self, **changes):
        return {'enabled': 'on', 'primary_provider': 'local',
                'local_model': 'qwen3.5:4b', 'api_model': '', 'api_endpoint': '',
                'daily_request_limit': '100', 'request_timeout': '120',
                'version': '0', **changes}

    def config(self, company=None):
        from .ai_processing_models import AIProcessingSettings
        return AIProcessingSettings.objects.get(company=company or self.company)

    def test_settings_read_is_non_mutating_and_private(self):
        from .ai_processing_models import AIProcessingSettings
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))
        self.assertFalse(AIProcessingSettings.objects.exists())

    def test_save_reload_and_duplicate_stale_submit_do_not_overwrite(self):
        response = self.client.post(self.url(), self.form())
        self.assertEqual(response.status_code, 302)
        original = self.config()
        self.assertEqual(original.daily_request_limit, 100)
        self.assertTrue(original.enabled)
        repeat = self.client.post(self.url(), self.form(daily_request_limit='77'))
        self.assertEqual(repeat.status_code, 409)
        original.refresh_from_db()
        self.assertEqual(original.daily_request_limit, 100)
        self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_unchecked_controls_persist_false_instead_of_old_value(self):
        self.client.post(self.url(), self.form())
        current = self.config()
        payload = self.form(version=str(current.version))
        payload.pop('enabled')
        self.assertEqual(self.client.post(self.url(), payload).status_code, 302)
        current.refresh_from_db()
        self.assertFalse(current.enabled)
        self.assertFalse(current.allow_external_evidence)
        self.assertFalse(current.fallback_enabled)

    def test_foreign_company_read_and_write_are_denied_without_changes(self):
        from .ai_processing_models import AIProcessingSettings
        self.assertEqual(self.client.get(self.url(self.foreign)).status_code, 403)
        self.assertEqual(self.client.post(self.url(self.foreign), self.form()).status_code, 403)
        self.assertFalse(AIProcessingSettings.objects.filter(company=self.foreign).exists())

    def test_regular_reviewer_roles_cannot_change_company_settings(self):
        from .ai_processing_models import AIProcessingSettings
        for role in (Profile.Roles.ENGINEER, Profile.Roles.QUALITY_ENGINEER,
                     Profile.Roles.TEAM_LEAD, Profile.Roles.CLIENT):
            actor = self.person(role.lower(), role, self.company)
            self.client.force_login(actor)
            self.assertEqual(self.client.post(self.url(), self.form()).status_code, 403)
        self.assertFalse(AIProcessingSettings.objects.exists())

    def test_revoked_admin_snapshot_is_not_trusted(self):
        from .ai_processing_service import update_settings
        from django.core.exceptions import PermissionDenied
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            update_settings(self.admin, self.company, {
                'enabled': True, 'primary_provider': 'local', 'local_model': 'qwen3.5:4b',
            }, expected_version=0)
        self.assertEqual(self.client.get(self.url()).status_code, 302)

    def test_cross_company_post_body_cannot_redirect_setting_ownership(self):
        response = self.client.post(self.url(), self.form(company_id=str(self.foreign.pk)))
        self.assertEqual(response.status_code, 400)
        from .ai_processing_models import AIProcessingSettings
        self.assertFalse(AIProcessingSettings.objects.exists())

    def test_settings_service_and_ui_use_the_same_current_admin_eligibility(self):
        from .ai_processing_service import update_settings
        from django.core.exceptions import PermissionDenied
        Profile.objects.filter(user=self.admin).update(admin_industry=None)
        self.assertEqual(self.client.get(self.url()).status_code, 403)
        with self.assertRaises(PermissionDenied):
            update_settings(self.admin, self.company, {'enabled': True}, expected_version=0)

    def test_external_route_requires_explicit_evidence_consent(self):
        from .ai_processing_models import AIProcessingSettings
        response = self.client.post(self.url(), self.form(
            primary_provider='https_ollama', api_endpoint='synthetic-fixture', api_model='fixture-vision'))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AIProcessingSettings.objects.exists())

    def test_invalid_limit_and_timeout_do_not_partially_save(self):
        from .ai_processing_models import AIProcessingSettings
        for changes in ({'daily_request_limit': '-1'}, {'request_timeout': '0'},
                        {'request_timeout': '9999'}, {'local_model': ''}):
            with self.subTest(changes=changes):
                response = self.client.post(self.url(), self.form(**changes))
                self.assertEqual(response.status_code, 400)
        self.assertFalse(AIProcessingSettings.objects.exists())

    def test_csrf_required_for_real_session_save(self):
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.admin)
        response = browser.post(self.url(), self.form())
        self.assertEqual(response.status_code, 403)

    def test_configured_secret_and_url_are_never_echoed_or_audited(self):
        secret = 'synthetic-credential-private-61984'
        hidden_url = 'https://private-provider.example.test/internal'
        with override_settings(AI_PROVIDER_REGISTRY={
                'synthetic-fixture': {'endpoint': hidden_url,
                                      'credential_env': 'AI_SYNTHETIC_TEST_KEY'}}):
            response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        for hidden in (secret, hidden_url, 'AI_SYNTHETIC_TEST_KEY'):
            self.assertNotIn(hidden, response.content.decode())
        self.client.post(self.url(), self.form())
        audit = json.dumps(list(GovernanceAudit.objects.values('action', 'details')))
        self.assertNotIn(secret, audit)
        self.assertNotIn(hidden_url, audit)


@contextmanager
def image_provider_fixture(*, malformed=False, chat_delay=0):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            self.reply({'models': [{'name': 'qwen3.5:4b'}]})
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((self.path, payload))
            if self.path == '/api/show':
                self.reply({'capabilities': ['vision']})
            elif malformed:
                self.reply({'done_reason': 'stop', 'message': {'content': '{broken-json'}})
            else:
                if chat_delay:
                    time.sleep(chat_delay)
                content = {'findings': [], 'missing': ['No verified measurement supplied'],
                           'conflicts': [], 'suggested_items': []}
                self.reply({'done_reason': 'stop', 'message': {'content': json.dumps(content)}})
        def reply(self, body):
            raw = json.dumps(body).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                if not chat_delay:
                    raise
                # Deliberately delayed timeout response has no remaining reader.
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:' + str(server.server_port), requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class IndependentAIRoutingTests(TestCase):
    def setUp(self):
        from .models import Checklist, Project
        from .survey_processing_models import SurveyProcessingJob, SurveyProcessingRevision
        self.company = Company.objects.create(name='Independent routing company')
        self.admin = User.objects.create_user('independent_route_admin')
        self.admin.profile.role = Profile.Roles.ADMIN
        self.admin.profile.company = self.company
        self.admin.profile.admin_industry = IndustryCatalog.objects.get(code='telecom')
        self.admin.profile.save()
        project = Project.objects.create(name='Independent source project', company=self.company,
                                         administrator=self.admin)
        self.checklist = Checklist.objects.create(project=project, user=self.admin, site_id='SYNTHETIC-ROUTE')
        revision = SurveyProcessingRevision.objects.create(checklist=self.checklist, number=1,
            digest='a'*64, snapshot={}, submitted_by=self.admin)
        self.job = SurveyProcessingJob.objects.create(revision=revision, model='qwen3.5:4b')

    def configure(self, **changes):
        from .ai_processing_service import update_settings
        return update_settings(self.admin, self.company,
            {'enabled': True, 'daily_request_limit': 10, **changes}, expected_version=0)

    def source(self):
        from .survey_evidence import extract_sources
        from hashlib import sha256
        output = BytesIO()
        Image.new('RGB', (50, 40), 'blue').save(output, 'PNG')
        raw = output.getvalue()
        return next(extract_sources([{'id': 1, 'filename': 'synthetic-blue.png',
            'raw': raw, 'sha256': sha256(raw).hexdigest()}], []))

    def test_real_image_request_is_validated_and_reused_without_second_inference(self):
        from .ai_processing_service import execute_source
        from .ai_processing_models import AIProcessingAttempt, AIProcessingQuota, AIProcessingRequest
        self.configure()
        source = self.source()
        with image_provider_fixture() as (base, requests):
            with override_settings(OLLAMA_BASE_URL=base, PHOTO_OLLAMA_BASE_URL=base):
                result = execute_source(self.job, source)
                request_count = len(requests)
                replay = execute_source(self.job, source)
                self.assertEqual(len(requests), request_count)
        chat = [body for route, body in requests if route == '/api/chat']
        self.assertEqual(len(chat), 1)
        actual_image = base64.b64decode(chat[0]['messages'][1]['images'][0], validate=True)
        with Image.open(BytesIO(actual_image)) as image:
            self.assertEqual(image.size, (50, 40))
        self.assertEqual(result, replay)
        self.assertEqual(result['source_id'], source['source_id'])
        self.assertEqual(result['sha256'], source['sha256'])
        self.assertEqual(result['verification_status'], 'needs_review')
        self.assertEqual(AIProcessingQuota.objects.get().used, 1)
        self.assertEqual(AIProcessingAttempt.objects.count(), 1)
        self.assertEqual(AIProcessingRequest.objects.get().state, 'succeeded')
        self.checklist.refresh_from_db()
        self.assertFalse(self.checklist.answer_data)

    def test_malformed_model_output_never_becomes_completed_result(self):
        from django.core.exceptions import ValidationError
        from .ai_processing_service import execute_source
        from .ai_processing_models import AIProcessingRequest, AIProcessingQuota
        self.configure()
        with image_provider_fixture(malformed=True) as (base, requests):
            with override_settings(OLLAMA_BASE_URL=base, PHOTO_OLLAMA_BASE_URL=base):
                with self.assertRaises(ValidationError):
                    execute_source(self.job, self.source())
        saved = AIProcessingRequest.objects.get()
        self.assertEqual(saved.state, 'failed')
        self.assertIsNone(saved.result)
        self.assertEqual(AIProcessingQuota.objects.get().used, 1)

    def test_stale_lease_cannot_publish_a_late_result(self):
        from django.core.exceptions import ValidationError
        from .ai_processing_service import execute_request
        from .ai_processing_models import AIProcessingRequest
        self.configure()
        def late(provider):
            AIProcessingRequest.objects.update(lease_until=timezone.now()-timedelta(seconds=1))
            return {'source_id': 'photo:1', 'verification_status': 'needs_review'}
        with self.assertRaises(ValidationError):
            execute_request(self.job, 'photo:1', {'sha': 'original'}, late)
        saved = AIProcessingRequest.objects.get()
        self.assertIsNone(saved.result)
        self.assertNotEqual(saved.state, 'succeeded')

    def test_changed_source_cannot_reuse_a_completed_receipt(self):
        from django.core.exceptions import ValidationError
        from .ai_processing_service import execute_request
        from .ai_processing_models import AIProcessingAttempt
        self.configure()
        execute_request(self.job, 'photo:1', {'sha': 'original'}, lambda p: {'result': 'review only'})
        with self.assertRaises(ValidationError):
            execute_request(self.job, 'photo:1', {'sha': 'replaced'}, lambda p: self.fail('must not infer'))
        self.assertEqual(AIProcessingAttempt.objects.count(), 1)

    def test_active_same_source_is_not_double_reserved(self):
        from django.core.exceptions import ValidationError
        from .ai_processing_service import execute_request
        from .ai_processing_models import AIProcessingAttempt, AIProcessingQuota
        self.configure()
        def first(provider):
            with self.assertRaises(ValidationError):
                execute_request(self.job, 'photo:1', {'sha': 'original'},
                                lambda p: self.fail('active source must not run twice'))
            return {'result': 'review only'}
        execute_request(self.job, 'photo:1', {'sha': 'original'}, first)
        self.assertEqual(AIProcessingAttempt.objects.count(), 1)
        self.assertEqual(AIProcessingQuota.objects.get().used, 1)

    def test_local_timeout_setting_controls_real_http_wait(self):
        from django.core.exceptions import ValidationError
        from .ai_processing_service import execute_source
        from .ai_processing_models import AIProcessingRequest
        self.configure(request_timeout=5)
        with image_provider_fixture(chat_delay=7) as (base, requests):
            with override_settings(OLLAMA_BASE_URL=base, PHOTO_OLLAMA_BASE_URL=base,
                                   OLLAMA_TIMEOUT=60):
                started = time.monotonic()
                with self.assertRaises(ValidationError):
                    execute_source(self.job, self.source())
                elapsed = time.monotonic()-started
                self.assertLess(elapsed, 6.5)
        self.assertEqual(AIProcessingRequest.objects.get().state, 'failed')
