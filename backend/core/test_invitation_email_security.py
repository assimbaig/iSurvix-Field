"""Independent post-implementation adversarial checks; all records are synthetic."""
import hashlib
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Company, GovernanceAudit, IndustryCatalog, InvitationEmailDelivery, Profile, Project, ProjectInvitation
from .onboarding_service import apply_application, invite_application, provision_application, review_application


@override_settings(NOTIFICATION_EMAIL_ENABLED=True, NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',
                   NOTIFICATION_EMAIL_CREDENTIALS_FILE='', ALLOWED_HOSTS=['testserver'],
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class InvitationEmailSecurityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser('security-mail-owner', 'owner@example.test', 'Synthetic-484!')
        self.industry = IndustryCatalog.objects.get(code='telecom')

    def invitation(self, suffix='A'):
        app = apply_application(self.owner, request_key=uuid.uuid4(), name='Synthetic security company ' + suffix,
                                email='security-admin-' + suffix.lower() + '@example.test', industry=self.industry)
        review_application(self.owner, app.pk, approve=True)
        provision_application(self.owner, app.pk)
        app, token = invite_application(self.owner, app.pk)
        return app, ProjectInvitation.objects.get(pk=app.invitation_id), token

    def admin(self):
        user = User.objects.create_user('security-customer-admin')
        user.profile.role = Profile.Roles.ADMIN
        user.profile.company = Company.objects.create(name='Synthetic mail security tenant')
        user.profile.admin_industry = self.industry
        user.profile.save()
        project = Project.objects.create(name='Synthetic mail security project', company=user.profile.company,
                                         industry=self.industry.code, administrator=user)
        user.profile.project = project
        user.profile.save(update_fields=['project'])
        return user, project

    def test_customer_admin_cannot_queue_super_admin_or_admin_escalation(self):
        actor, project = self.admin()
        self.client.force_login(actor)
        for role in [Profile.Roles.SUPER_ADMIN, Profile.Roles.ADMIN]:
            with self.subTest(role=role):
                response = self.client.post(reverse('governance_invite'),
                    {'email':'escalated@example.test', 'role':role, 'project':project.pk})
                self.assertIn(response.status_code, [400, 403])
        self.assertFalse(ProjectInvitation.objects.exists())
        self.assertFalse(InvitationEmailDelivery.objects.exists())

    def test_engineer_cannot_issue_invitation_or_email(self):
        actor, project = self.admin()
        actor.profile.role = Profile.Roles.ENGINEER
        actor.profile.save(update_fields=['role'])
        self.client.force_login(actor)
        response = self.client.post(reverse('governance_invite'),
            {'email':'escalated@example.test', 'role':Profile.Roles.ENGINEER, 'project':project.pk})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ProjectInvitation.objects.exists())
        self.assertFalse(InvitationEmailDelivery.objects.exists())

    def test_csrf_failure_does_not_create_or_queue_any_invitation(self):
        actor, project = self.admin()
        client = Client(enforce_csrf_checks=True)
        client.force_login(actor)
        response = client.post(reverse('governance_invite'),
            {'email':'csrf-target@example.test', 'role':Profile.Roles.ENGINEER, 'project':project.pk})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ProjectInvitation.objects.exists())
        self.assertFalse(InvitationEmailDelivery.objects.exists())

    def test_queued_email_cannot_outlive_a_locked_or_inactive_issuer(self):
        from .invitation_email import process_next_email
        for suffix, mutate in [
                ('locked', lambda: Profile.objects.filter(user=self.owner).update(is_locked=True)),
                ('inactive', lambda: User.objects.filter(pk=self.owner.pk).update(is_active=False))]:
            with self.subTest(state=suffix):
                User.objects.filter(pk=self.owner.pk).update(is_active=True)
                Profile.objects.filter(user=self.owner).update(is_locked=False)
                app, invitation, token = self.invitation(suffix)
                mutate()
                with patch('core.invitation_email.GraphMailClient') as graph:
                    self.assertTrue(process_next_email())
                graph.assert_not_called()
                self.assertEqual(InvitationEmailDelivery.objects.get(invitation=invitation).status, 'cancelled')

    def test_mismatched_nonce_cannot_be_attached_to_a_valid_invitation(self):
        from .invitation_email import queue_invitation_email
        app, invitation, token = self.invitation()
        with self.assertRaises(ValidationError):
            queue_invitation_email(invitation, uuid.uuid4())
        self.assertEqual(InvitationEmailDelivery.objects.count(), 1)
        self.assertEqual(ProjectInvitation.objects.get(pk=invitation.pk).token_hash,
                         hashlib.sha256(token.encode()).hexdigest())

    def test_duplicate_queue_call_reuses_one_delivery_and_one_audit(self):
        from .invitation_email import queue_invitation_email
        app, invitation, token = self.invitation()
        saved = InvitationEmailDelivery.objects.get(invitation=invitation)
        for _ in range(3):
            self.assertEqual(queue_invitation_email(invitation, saved.pk).pk, saved.pk)
        self.assertEqual(InvitationEmailDelivery.objects.count(), 1)
        self.assertEqual(GovernanceAudit.objects.filter(action='invitation_email.queued').count(), 1)

    def test_key_rotation_uses_only_matching_fallback_and_preserves_original_link(self):
        from .invitation_email import process_next_email
        old_key = settings.SECRET_KEY
        app, invitation, token = self.invitation()
        with override_settings(SECRET_KEY='new-independent-synthetic-key', SECRET_KEY_FALLBACKS=[old_key]), \
                patch('core.invitation_email.GraphMailClient') as graph:
            self.assertTrue(process_next_email())
        graph.return_value.send.assert_called_once()
        self.assertIn('/' + token + '/', graph.return_value.send.call_args.args[2])
        self.assertEqual(InvitationEmailDelivery.objects.get(invitation=invitation).status, 'accepted')

    def test_unavailable_rotation_key_fails_without_rewriting_original_invite(self):
        from .invitation_email import process_next_email
        app, invitation, token = self.invitation()
        with override_settings(SECRET_KEY='new-independent-synthetic-key', SECRET_KEY_FALLBACKS=[]), \
                patch('core.invitation_email.GraphMailClient') as graph:
            self.assertTrue(process_next_email())
        graph.assert_not_called()
        self.assertEqual(InvitationEmailDelivery.objects.get(invitation=invitation).error_code, 'invitation_key_changed')
        self.assertEqual(ProjectInvitation.objects.get(pk=invitation.pk).token_hash,
                         hashlib.sha256(token.encode()).hexdigest())

    def test_stale_lease_cannot_report_a_different_send_as_accepted(self):
        from .invitation_email import _claim, _finish
        app, invitation, token = self.invitation()
        claimed = _claim()
        new_lease = uuid.uuid4()
        InvitationEmailDelivery.objects.filter(pk=claimed.pk).update(lease_id=new_lease)
        _finish(claimed, 'accepted')
        saved = InvitationEmailDelivery.objects.get(pk=claimed.pk)
        self.assertEqual(saved.status, 'sending')
        self.assertEqual(saved.lease_id, new_lease)
        self.assertIsNone(saved.accepted_at)

    def test_unsafe_origin_is_rejected_before_transport_and_original_link_survives(self):
        from .invitation_email import process_next_email
        bad_origins = ['http://testserver', 'https://testserver@attacker.invalid',
                       'https://testserver/path', 'https://testserver?redirect=evil',
                       'https://testserver/#fragment', 'https://attacker.invalid']
        for index, origin in enumerate(bad_origins):
            with self.subTest(origin=origin):
                app, invitation, token = self.invitation(str(index))
                with override_settings(NOTIFICATION_EMAIL_PUBLIC_ORIGIN=origin), \
                        patch('core.invitation_email.GraphMailClient') as graph:
                    self.assertTrue(process_next_email())
                graph.assert_not_called()
                self.assertEqual(InvitationEmailDelivery.objects.get(invitation=invitation).error_code, 'invalid_public_origin')
                self.assertEqual(ProjectInvitation.objects.get(pk=invitation.pk).token_hash,
                                 hashlib.sha256(token.encode()).hexdigest())

    def test_expired_lease_recovers_once_without_retransmission_or_secret_audit(self):
        from .invitation_email import _claim, process_next_email, recover_interrupted_emails, retry_failed_emails
        app, invitation, token = self.invitation()
        claimed = _claim()
        InvitationEmailDelivery.objects.filter(pk=claimed.pk).update(lease_expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(recover_interrupted_emails(), 1)
        self.assertEqual(recover_interrupted_emails(), 0)
        self.assertEqual(retry_failed_emails(), 0)
        with patch('core.invitation_email.GraphMailClient') as graph:
            self.assertFalse(process_next_email())
        graph.assert_not_called()
        events = json.dumps(list(GovernanceAudit.objects.values_list('details', flat=True)))
        self.assertNotIn(token, events)
        self.assertEqual(InvitationEmailDelivery.objects.get(invitation=invitation).status, 'uncertain')


class InvitationEmailRuntimeSecurityTests(SimpleTestCase):
    def setUp(self):
        from .test_hostinger_delivery import module, RuntimePolicyTests
        from .test_invitation_mail_runtime import runtime_module
        self.controller = module()
        self.runtime = runtime_module()
        self.config = RuntimePolicyTests().config()
        web = self.config['services']['web']
        web['environment'] = {'ISURVIX_NOTIFICATION_EMAIL_ENABLED':'True',
            'ISURVIX_NOTIFICATION_CREDENTIALS_FILE':'/run/private/ifield-notification.json'}
        web['volumes'].append({'type':'bind', 'source':'/etc/isurvix-staging/ifield-notification.json',
                               'target':'/run/private/ifield-notification.json', 'read_only':True})

    def test_duplicate_mail_mount_or_directory_widening_is_rejected(self):
        import copy
        self.controller.validate_compose(self.config)
        for mutate in [
            lambda c: c['services']['web']['volumes'].append(copy.deepcopy(c['services']['web']['volumes'][-1])),
            lambda c: c['services']['web']['volumes'][-1].update(target='/run/private'),
            lambda c: c['services']['web']['volumes'][-1].update(source='/etc/isurvix-staging'),
            lambda c: c['services']['web']['volumes'][-1].update(type='volume'),
        ]:
            candidate = copy.deepcopy(self.config)
            mutate(candidate)
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    self.controller.validate_compose(candidate)

    def test_enabling_mail_cannot_weaken_existing_runtime_boundaries(self):
        import copy
        for mutate in [
            lambda c: c['services']['web'].update(privileged=True),
            lambda c: c['services']['web'].update(network_mode='host'),
            lambda c: c['services']['web'].update(cap_add=['SYS_ADMIN']),
            lambda c: c['services']['web'].update(user='0:0'),
            lambda c: c['services']['web'].update(ports=[{'published':'8000','target':8000}]),
            lambda c: c['services']['proxy']['volumes'].append(copy.deepcopy(c['services']['web']['volumes'][-1])),
        ]:
            candidate = copy.deepcopy(self.config)
            mutate(candidate)
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    self.controller.validate_compose(candidate)

    def test_readiness_does_not_contact_an_unsafe_or_unbound_host(self):
        base = {'ISURVIX_NOTIFICATION_PUBLIC_ORIGIN':'https://app.isurvix.com',
                'ISURVIX_RELEASE_ID':'a'*40, 'DJANGO_ALLOWED_HOSTS':'app.isurvix.com'}
        for origin in ['https://app.isurvix.com@evil.invalid', 'http://app.isurvix.com',
                       'https://app.isurvix.com/private', 'https://evil.invalid',
                       'https://app.isurvix.com/#fragment']:
            with self.subTest(origin=origin), patch.object(self.runtime, 'deadline_request') as client:
                self.assertFalse(self.runtime.public_release_ready(dict(base, ISURVIX_NOTIFICATION_PUBLIC_ORIGIN=origin)))
                client.assert_not_called()

    def test_broken_readiness_or_wrong_release_never_starts_a_mail_process(self):
        from threading import Event
        stop = Event()
        class Child:
            pid = 999999
            def poll(self):
                return None
            def wait(self, timeout=None):
                return 0
        def denied_readiness():
            stop.set()
            raise ValueError('Synthetic unavailable public readiness')
        with patch.object(self.runtime, '_stop_children'), patch.object(self.runtime, '_signal_process'), \
                patch.object(self.runtime.subprocess, 'Popen', return_value=Child()) as process:
            self.runtime.supervise(['synthetic-web'], ['synthetic-mail'], mail_enabled=True,
                                   readiness=denied_readiness, spawn=process, stop_event=stop)
        process.assert_called_once()
        self.assertEqual(process.call_args.args[0], ['synthetic-web'])
