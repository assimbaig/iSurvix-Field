"""Scoped support diagnostics and audit lifecycle use isolated real Django records."""
from copy import deepcopy
from io import BytesIO
import hashlib
import json
import uuid
from zipfile import ZipFile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Company, Project, Profile, ProjectMembership, Checklist
from .photo_models import PhotoJob


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False, ISURVIX_RELEASE_ID='a' * 40,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SupportBackendTests(TestCase):
    def setUp(self):
        self.ca = Company.objects.create(name='Private support company A')
        self.cb = Company.objects.create(name='Private support company B')
        self.pa = Project.objects.create(name='Private project A', company=self.ca)
        self.pb = Project.objects.create(name='Private project B', company=self.cb)
        self.owner = User.objects.create_superuser('support-owner', 'owner@example.test', 'isolated-password')
        self.admin = self.person('support-admin-a', Profile.Roles.ADMIN, self.pa)
        self.other = self.person('support-admin-b', Profile.Roles.ADMIN, self.pb)
        self.engineer = self.person('support-engineer', Profile.Roles.ENGINEER, self.pa)
        self.task = Checklist.objects.create(user=self.engineer, project=self.pa, site_id='PRIVATE-SITE')
        self.foreign_task = Checklist.objects.create(user=self.other, project=self.pb)
        PhotoJob.objects.create(checklist=self.task, requested_by=self.admin, model='private-model',
                                status='failed', error='PRIVATE-SECRET-STACK')
        PhotoJob.objects.create(checklist=self.foreign_task, requested_by=self.other, model='private-model', status='queued')

    def person(self, name, role, project):
        user = User.objects.create_user(name, password='isolated-password')
        profile = user.profile
        profile.role = role
        profile.company = project.company
        profile.project = project
        profile.save()
        ProjectMembership.objects.create(user=user, project=project, is_primary=True)
        return user

    def create(self, actor=None, **changes):
        from .support_service import create_case
        data = {'category': 'processing', 'description': 'PRIVATE-SECRET-USER-TEXT',
                'project_id': self.pa.pk, 'request_key': str(uuid.uuid4())}
        data.update(changes)
        return create_case(actor or self.admin, **data)

    def action(self, case, action, **changes):
        from .support_service import change_case
        data = {'action': action, 'expected_version': case.version, 'request_key': str(uuid.uuid4())}
        data.update(changes)
        return change_case(self.owner, case.pk, **data)

    def receipt(self, case, **changes):
        result = {'format': 'isurvix-support-repair-v1', 'case_id': str(case.pk),
                  'report_sha256': case.report_digest, 'base_commit': 'a' * 40,
                  'tested_commit': 'b' * 40, 'patch_sha256': 'c' * 64, 'regression_sha256': 'd' * 64,
                  'test_evidence': {'baseline_failed': True, 'patched_passed': True,
                                    'unit_passed': True, 'integration_passed': True,
                                    'isolation': 'docker-no-network', 'execution_id': str(uuid.uuid4())},
                  'pr_url': 'https://github.com/assimbaig/iSurvix-Field/pull/123',
                  'provenance': 'operator-attested', 'candidate_only': True, 'owner_release_approved': False}
        result.update(changes)
        return result

    def import_receipt(self, case, receipt=None, **changes):
        from .support_service import import_receipt
        data = {'receipt': receipt or self.receipt(case), 'expected_version': case.version,
                'request_key': str(uuid.uuid4())}
        data.update(changes)
        return import_receipt(self.owner, case.pk, **data)

    def test_health_counts_scope_to_current_authorized_projects_and_omit_private_text(self):
        from .support_service import health
        data = health(self.admin)
        self.assertEqual(data['scope']['company_id'], self.ca.pk)
        self.assertEqual(data['counts']['projects'], 1)
        self.assertEqual(data['counts']['photo_jobs'], {'failed': 1})
        encoded = json.dumps(data)
        for private in ('Private support company', 'Private project', 'PRIVATE-SITE', 'PRIVATE-SECRET', 'private-model'):
            self.assertNotIn(private, encoded)
        self.assertEqual(health(self.owner)['counts']['projects'], 2)

    def test_diagnostics_export_contains_only_bound_allowlisted_json_and_preserves_case(self):
        from .support_service import export_bundle
        case = self.create()
        raw = export_bundle(self.admin, case.pk)
        with ZipFile(BytesIO(raw)) as archive:
            self.assertEqual(set(archive.namelist()), {'manifest.json', 'diagnostics.json'})
            manifest = json.loads(archive.read('manifest.json'))
            report = archive.read('diagnostics.json')
        self.assertEqual(manifest['case_id'], str(case.pk))
        self.assertEqual(manifest['report_sha256'], hashlib.sha256(report).hexdigest())
        self.assertEqual(manifest['report_sha256'], case.report_digest)
        self.assertEqual(manifest['source_release'], 'a' * 40)
        self.assertNotIn(b'PRIVATE-SECRET', report)
        self.assertNotIn(b'owner@example.test', report)
        self.assertEqual(json.loads(report), case.report)

    def test_create_request_replay_is_once_and_changed_inputs_are_rejected(self):
        key = str(uuid.uuid4())
        first = self.create(request_key=key)
        replay = self.create(request_key=key)
        self.assertEqual(first.pk, replay.pk)
        self.assertEqual(first.events.count(), 1)
        with self.assertRaises(ValidationError):
            self.create(request_key=key, description='different inputs')

    def test_foreign_company_and_wrong_role_cannot_read_or_change_cases(self):
        from .support_service import export_bundle, health, change_case
        case = self.create()
        for user in (self.other, self.engineer):
            with self.subTest(user=user.username), self.assertRaises((PermissionDenied, ValidationError)):
                export_bundle(user, case.pk)
        with self.assertRaises(PermissionDenied):
            health(self.engineer)
        with self.assertRaises(PermissionDenied):
            change_case(self.admin, case.pk, action='request_repair', expected_version=1, request_key=str(uuid.uuid4()))

    def test_revocation_is_rechecked_after_a_cached_principal(self):
        from .support_service import export_bundle
        case = self.create()
        _ = self.admin.profile
        Profile.objects.filter(user=self.admin).update(is_locked=True)
        with self.assertRaises(PermissionDenied):
            export_bundle(self.admin, case.pk)
        Profile.objects.filter(user=self.admin).update(is_locked=False)
        ProjectMembership.objects.filter(user=self.admin, project=self.pa).update(is_active=False)
        with self.assertRaises((PermissionDenied, ValidationError)):
            export_bundle(self.admin, case.pk)

    def test_frozen_report_and_audit_events_cannot_be_updated_or_deleted(self):
        from .support_models import SupportCase, SupportEvent
        case = self.create()
        with self.assertRaises(ValidationError):
            SupportCase.objects.filter(pk=case.pk).update(description='overwritten')
        event = case.events.first()
        event.details = {'forged': True}
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            SupportEvent.objects.filter(pk=event.pk).delete()

    def test_full_support_chain_retains_exact_report_pr_approvals_and_actual_installation(self):
        case = self.action(self.create(), 'request_repair')
        case = self.import_receipt(case)
        self.assertEqual(case.status, 'pr_ready')
        case = self.action(case, 'approve_repair')
        case = self.action(case, 'approve_release')
        with self.assertRaisesMessage(ValidationError, 'installed'):
            self.action(case, 'confirm_installed')
        with override_settings(ISURVIX_RELEASE_ID='b' * 40):
            case = self.action(case, 'confirm_installed')
        self.assertEqual(case.status, 'installed')
        self.assertEqual(list(case.events.values_list('status', flat=True)),
                         ['reported', 'repair_requested', 'pr_ready', 'repair_approved', 'release_approved', 'installed'])
        evidence = case.events.get(kind='receipt_recorded').details['receipt']
        self.assertEqual(evidence['report_sha256'], case.report_digest)
        self.assertEqual(evidence['provenance'], 'operator-attested')
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Checklist.Status.DRAFT)
        self.assertEqual(self.task.review_history, [])

    def test_no_pr_no_approval_and_untested_or_cross_bound_receipts_are_rejected(self):
        case = self.action(self.create(), 'request_repair')
        for changes in ({'case_id': str(uuid.uuid4())}, {'report_sha256': 'e' * 64},
                        {'base_commit': 'e' * 40}, {'owner_release_approved': True},
                        {'pr_url': 'https://evil.example/pull/1'}, {'extra': 'PRIVATE-SECRET'}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.import_receipt(case, self.receipt(case, **changes))
        receipt = self.receipt(case)
        receipt['test_evidence']['integration_passed'] = False
        with self.assertRaises(ValidationError):
            self.import_receipt(case, receipt)
        case = self.import_receipt(case, self.receipt(case, pr_url=''))
        self.assertEqual(case.status, 'tests_passed')
        with self.assertRaises(ValidationError):
            self.action(case, 'approve_repair')
        case = self.action(case, 'link_pr', pr_url='https://github.com/assimbaig/iSurvix-Field/pull/123')
        self.assertEqual(case.status, 'pr_ready')

    def test_duplicate_operator_receipt_does_not_duplicate_audit_or_reset_approval(self):
        case = self.action(self.create(), 'request_repair')
        receipt = self.receipt(case)
        case = self.import_receipt(case, receipt)
        case = self.action(case, 'approve_repair')
        replay = self.import_receipt(case, receipt)
        self.assertEqual(replay.status, 'repair_approved')
        self.assertEqual(replay.events.filter(kind='receipt_recorded').count(), 1)

    def test_stale_actions_and_unknown_versions_cannot_authorize_repairs(self):
        case = self.create()
        case = self.action(case, 'request_repair')
        with self.assertRaises(ValidationError):
            self.action(case, 'request_changes', expected_version=1, reason='repeat')
        with override_settings(ISURVIX_RELEASE_ID='unknown'):
            unknown = self.create()
        with self.assertRaisesMessage(ValidationError, 'release'):
            self.action(unknown, 'request_repair')

    def test_health_api_download_and_mutations_enforce_auth_csrf_scope_and_shapes(self):
        self.assertEqual(self.client.get(reverse('support_health')).status_code, 302)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('support_health')).status_code, 200)
        case = self.create()
        self.assertEqual(self.client.get(reverse('support_case_export', args=[case.pk])).status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('support_case_export', args=[case.pk])).status_code, 404)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(reverse('support_case_create'), {}).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse('support_case_action', args=[case.pk]),
                                        {'command': 'execute arbitrary source'}).status_code, 400)
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.get(reverse('support_health')).status_code, 403)

    def test_same_company_disjoint_admins_cannot_read_each_others_project_or_company_reports(self):
        from .support_service import export_bundle, health
        extra = Project.objects.create(name='Different owned project', company=self.ca)
        peer = self.person('support-admin-peer', Profile.Roles.ADMIN, extra)
        project_case = self.create()
        company_case = self.create(project_id=None)
        for case in (project_case, company_case):
            with self.subTest(case=case.pk), self.assertRaises(PermissionDenied):
                export_bundle(peer, case.pk)
        self.assertEqual(health(peer)['counts']['photo_jobs'], {})
        ProjectMembership.objects.create(user=peer, project=self.pa, legacy_admin_access=True)
        self.assertTrue(export_bundle(peer, project_case.pk))
        with self.assertRaises(PermissionDenied):
            export_bundle(peer, company_case.pk)

    def test_diagnostics_are_an_immutable_snapshot_and_do_not_invoke_a_model_or_shell(self):
        from .support_service import export_bundle, health
        with patch('subprocess.run', side_effect=AssertionError('No shell in support web services')), \
             patch('core.local_ai.ollama', side_effect=AssertionError('No model in diagnostics')):
            case = self.create()
            before = case.report_digest
            PhotoJob.objects.create(checklist=self.task, requested_by=self.admin, model='ignored', status='PRIVATE-SECRET-STATUS')
            self.assertEqual(health(self.admin)['counts']['photo_jobs'], {'failed': 1, 'other': 1})
            exported = export_bundle(self.admin, case.pk)
            with ZipFile(BytesIO(exported)) as archive:
                snapshot = json.loads(archive.read('diagnostics.json'))
                self.assertEqual(snapshot['counts']['photo_jobs'], {'failed': 1})
                self.assertNotIn(b'PRIVATE-SECRET', archive.read('diagnostics.json'))
            case.refresh_from_db()
            self.assertEqual(case.report_digest, before)

    def test_audit_failure_rolls_back_the_new_support_report(self):
        from .support_models import SupportCase, SupportEvent
        with patch('core.support_service.GovernanceAudit.objects.create', side_effect=IntegrityError('synthetic audit failure')):
            with self.assertRaises(IntegrityError):
                self.create()
        self.assertEqual(SupportCase.objects.count(), 0)
        self.assertEqual(SupportEvent.objects.count(), 0)

    def test_every_nonadministrator_role_and_forged_super_admin_profile_are_denied(self):
        from .support_service import health
        for role in (Profile.Roles.ENGINEER, Profile.Roles.QUALITY_ENGINEER, Profile.Roles.TEAM_LEAD,
                     Profile.Roles.CLIENT, Profile.Roles.PROJECT_MANAGER, Profile.Roles.SUPER_ADMIN):
            person = self.person('support-noaccess-' + role.lower(), role, self.pa)
            with self.subTest(role=role), self.assertRaises(PermissionDenied):
                health(person)
        self.owner.is_active = False
        self.owner.save(update_fields=['is_active'])
        with self.assertRaises(PermissionDenied):
            health(self.owner)

    def test_action_replay_keeps_one_event_and_different_action_payload_conflicts(self):
        case = self.create()
        key = str(uuid.uuid4())
        case = self.action(case, 'request_repair', request_key=key)
        replay = self.action(case, 'request_repair', request_key=key, expected_version=1)
        self.assertEqual(replay.version, 2)
        with self.assertRaises(ValidationError):
            self.action(case, 'request_repair', request_key=key, reason='different input')
        self.assertEqual(case.events.count(), 2)

    def test_receipt_http_rejects_duplicate_json_keys_and_retains_user_input(self):
        case = self.action(self.create(), 'request_repair')
        self.client.force_login(self.owner)
        raw = '{"format":"first","format":"second"}'
        response = self.client.post(reverse('support_case_receipt', args=[case.pk]),
                                    {'receipt': raw, 'expected_version': case.version, 'request_key': str(uuid.uuid4())})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'bounded JSON', status_code=400)
        self.assertEqual(case.events.count(), 2)
