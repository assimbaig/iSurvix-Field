"""Structured privileged-change evidence without credentials or mutable authority."""
from copy import deepcopy
import importlib
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Company, GovernanceAudit, IndustryCatalog, Profile, Project, ProjectInvitation, ProjectMembership


SETTINGS = {'ROOT_URLCONF': 'checklist.urls_local', 'ALLOWED_HOSTS': ['testserver'],
            'SECURE_SSL_REDIRECT': False, 'PASSWORD_HASHERS': ['django.contrib.auth.hashers.MD5PasswordHasher']}


@override_settings(**SETTINGS)
class PrivilegedChangeAuditTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Audit employer A')
        self.other_company = Company.objects.create(name='Audit employer B')
        self.project = Project.objects.create(name='Audit project', company=self.company)
        self.admin = self.person('audit-company-admin', Profile.Roles.ADMIN)
        self.engineer = self.person('audit-engineer', Profile.Roles.ENGINEER)
        self.client.force_login(self.admin)

    def person(self, name, role):
        user = User.objects.create_user(name, password='Synthetic-private-password-618!')
        user.profile.role = role
        user.profile.company = self.company
        user.profile.project = self.project
        user.profile.save()
        ProjectMembership.objects.create(user=user, project=self.project, is_primary=True)
        return user

    def helper(self):
        return importlib.import_module('core.privileged_audit')

    def test_role_change_http_records_one_actor_target_scope_and_before_after_event(self):
        before = GovernanceAudit.objects.count()
        response = self.client.post(reverse('governance_member', args=[self.engineer.pk]),
                                    {'action': 'role', 'role': Profile.Roles.QUALITY_ENGINEER})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GovernanceAudit.objects.count(), before + 1)
        event = GovernanceAudit.objects.latest('pk')
        self.assertEqual(event.action, 'member_role')
        self.assertEqual(event.actor_id, self.admin.pk)
        self.assertEqual(event.details['user_id'], self.engineer.pk)
        change = event.details.get('privileged_change')
        self.assertIsNotNone(change, 'A stored role change needs structured before/after evidence.')
        self.assertEqual(change['version'], 1)
        self.assertEqual(change['actor']['id'], self.admin.pk)
        self.assertEqual(change['actor']['role'], Profile.Roles.ADMIN)
        self.assertEqual(change['target'], {'kind': 'user', 'id': self.engineer.pk})
        self.assertEqual(change['scope'], {'company_id': self.company.pk, 'project_id': self.project.pk})
        self.assertEqual(change['before']['role'], Profile.Roles.ENGINEER)
        self.assertEqual(change['after']['role'], Profile.Roles.QUALITY_ENGINEER)

    def test_user_snapshot_uses_stored_state_and_omits_password_and_email(self):
        helper = self.helper()
        cached = self.engineer.profile
        Profile.objects.filter(pk=cached.pk).update(role=Profile.Roles.TEAM_LEAD, company=self.other_company)
        saved = helper.snapshot_user(self.engineer)
        self.assertEqual(saved['role'], Profile.Roles.TEAM_LEAD)
        self.assertEqual(saved['company_id'], self.other_company.pk)
        self.assertEqual(saved['id'], self.engineer.pk)
        self.assertNotIn('password', saved)
        self.assertNotIn('email', saved)
        self.assertNotIn('Synthetic-private-password', json.dumps(saved))

    def test_envelope_keeps_creation_and_detaches_from_caller_mutations(self):
        helper = self.helper()
        after = helper.snapshot_user(self.engineer)
        details = helper.change_details(self.admin, 'user', self.engineer.pk, None, after, project=self.project)
        self.assertIsNone(details['privileged_change']['before'])
        after['role'] = Profile.Roles.ADMIN
        self.assertEqual(details['privileged_change']['after']['role'], Profile.Roles.ENGINEER)
        event = GovernanceAudit.objects.create(actor=self.admin, actor_name=self.admin.username,
                                               action='fixture_privilege_created', project=self.project, details=details)
        old = deepcopy(event.details)
        Profile.objects.filter(user=self.admin).update(role=Profile.Roles.ENGINEER)
        event.refresh_from_db()
        self.assertEqual(event.details, old)
        self.assertEqual(event.details['privileged_change']['actor']['role'], Profile.Roles.ADMIN)

    def test_sensitive_or_unrecognized_snapshot_fields_are_rejected(self):
        helper = self.helper()
        valid = helper.snapshot_user(self.engineer)
        for key in ('password', 'token_hash', 'session_key', 'request', 'unknown_privilege'):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                helper.change_details(self.admin, 'user', self.engineer.pk, valid,
                                      {**valid, key: 'private-must-not-persist'}, project=self.project)
        with self.assertRaises(ValidationError):
            helper.change_details(self.admin, 'user', self.engineer.pk, valid,
                                  {**valid, 'is_superuser': 'true'}, project=self.project)
        with self.assertRaises(ValidationError):
            helper.change_details(self.admin, 'user', self.engineer.pk, valid,
                                  {**valid, 'role': 'FORGED_PLATFORM_OWNER'}, project=self.project)

    def test_membership_snapshots_distinguish_missing_existing_and_revoked_grants(self):
        helper = self.helper()
        additional = Project.objects.create(name='Audit additional project', company=self.company)
        missing = helper.snapshot_membership(self.engineer, additional)
        self.assertFalse(missing['exists'])
        self.assertEqual(missing['primary_project_id'], self.project.pk)
        membership = ProjectMembership.objects.create(user=self.engineer, project=additional, expires_at=timezone.now())
        before = helper.snapshot_membership(self.engineer, additional)
        ProjectMembership.objects.filter(pk=membership.pk).update(is_active=False)
        after = helper.snapshot_membership(self.engineer, additional)
        details = helper.change_details(self.admin, 'membership', membership.pk, before, after, project=additional)
        self.assertTrue(details['privileged_change']['before']['is_active'])
        self.assertFalse(details['privileged_change']['after']['is_active'])
        self.assertEqual(after['user_id'], self.engineer.pk)
        self.assertNotIn('email', after)

    def test_invitation_snapshot_never_includes_link_secret_or_email(self):
        helper = self.helper()
        invitation = ProjectInvitation.objects.create(project=self.project, company=self.company,
            created_by=self.admin, email='private-recipient@example.test', role=Profile.Roles.ENGINEER,
            token_hash='a' * 64, expires_at=timezone.now())
        snapshot = helper.snapshot_invitation(invitation)
        self.assertEqual(snapshot['company_id'], self.company.pk)
        self.assertEqual(snapshot['role'], Profile.Roles.ENGINEER)
        serialized = json.dumps(snapshot)
        self.assertNotIn('a' * 64, serialized)
        self.assertNotIn('private-recipient', serialized)
        self.assertNotIn('token_hash', snapshot)

    def test_project_and_maintenance_snapshots_are_bounded_structured_metadata(self):
        helper = self.helper()
        snapshot = helper.snapshot_project(self.project)
        self.assertEqual(snapshot['company_id'], self.company.pk)
        self.assertEqual(snapshot['administrator_id'], self.admin.pk)
        counts = helper.snapshot_maintenance()
        self.assertEqual(set(counts), {'sessions', 'locked_profiles', 'open_invitations'})
        self.assertTrue(all(type(value) is int and value >= 0 for value in counts.values()))
        change = helper.change_details(self.admin, 'maintenance', None, counts, counts)
        self.assertEqual(change['privileged_change']['target'], {'kind': 'maintenance', 'id': None})

    def test_audit_insert_failure_rolls_back_role_change(self):
        before = self.engineer.profile.role
        count = GovernanceAudit.objects.count()
        with patch('core.governance_views.audit', side_effect=IntegrityError('Synthetic audit persistence failure')):
            response = self.client.post(reverse('governance_member', args=[self.engineer.pk]),
                                        {'action': 'role', 'role': Profile.Roles.QUALITY_ENGINEER})
        self.assertEqual(response.status_code, 409)
        self.engineer.profile.refresh_from_db()
        self.assertEqual(self.engineer.profile.role, before)
        self.assertEqual(GovernanceAudit.objects.count(), count)

    def test_nondefault_snapshot_reads_its_object_database_and_leaves_default_unchanged(self):
        helper = self.helper()
        from django.db.backends.sqlite3.base import DatabaseWrapper
        alias = 'privilege_audit_snapshot_disposable'
        config = deepcopy(connection.settings_dict)
        config['NAME'] = ':memory:'
        scratch = DatabaseWrapper(config, alias=alias)
        scratch.ensure_connection()
        connections[alias] = scratch
        default = helper.snapshot_user(self.admin)
        try:
            executor = MigrationExecutor(scratch)
            executor.migrate(executor.loader.graph.leaf_nodes())
            apps = executor.loader.project_state().apps
            person = apps.get_model('auth', 'User').objects.using(alias).create(pk=self.admin.pk, username='Alternate audit actor')
            company = apps.get_model('core', 'Company').objects.using(alias).create(name='Alternate audit company')
            apps.get_model('core', 'Profile').objects.using(alias).create(user=person, role=Profile.Roles.CLIENT, company=company)
            loaded = User.objects.using(alias).get(pk=person.pk)
            snapshot = helper.snapshot_user(loaded)
            self.assertEqual(snapshot['role'], Profile.Roles.CLIENT)
            self.assertEqual(snapshot['company_id'], company.pk)
            self.assertEqual(helper.snapshot_user(self.admin), default)
        finally:
            scratch.close()
            del connections[alias]
