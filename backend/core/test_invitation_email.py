"""Saved invitation delivery: no operational database, email or mailbox writes."""
import hashlib
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import GovernanceAudit, IndustryCatalog, ProjectInvitation, InvitationEmailDelivery
from .onboarding_service import apply_application, review_application, provision_application, invite_application


@override_settings(NOTIFICATION_EMAIL_ENABLED=True,
                   NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',
                   ALLOWED_HOSTS=['testserver'], PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class InvitationEmailTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser('mail-owner', 'owner@example.test', 'Fixture849!')
        self.industry = IndustryCatalog.objects.get(code='telecom')
        self.client.force_login(self.owner)

    def invite(self):
        app = apply_application(self.owner, request_key=uuid.uuid4(), name='Synthetic mail company',
                                email='company-admin@example.test', industry=self.industry)
        review_application(self.owner, app.pk, approve=True)
        provision_application(self.owner, app.pk)
        return invite_application(self.owner, app.pk)

    def test_new_invitation_is_queued_without_waiting_for_network(self):
        app, token = self.invite()
        response = self.client.get(reverse('company_onboarding_detail', args=[app.pk]))
        self.assertContains(response, 'Email queued')
        self.assertNotContains(response, 'No email was sent')
        from .models import InvitationEmailDelivery
        delivery = InvitationEmailDelivery.objects.get(invitation_id=app.invitation_id)
        self.assertEqual(delivery.status, 'queued')
        self.assertEqual(delivery.attempts, 0)
        self.assertEqual(app.invitation.token_hash, hashlib.sha256(token.encode()).hexdigest())

    def test_worker_sends_once_and_does_not_claim_inbox_delivery(self):
        from .invitation_email import process_next_email
        app, token = self.invite()
        with patch('core.invitation_email.GraphMailClient') as client:
            self.assertTrue(process_next_email())
            self.assertFalse(process_next_email())
        client.return_value.send.assert_called_once()
        recipient, subject, body = client.return_value.send.call_args.args
        self.assertEqual(recipient, 'company-admin@example.test')
        self.assertIn('https://testserver/governance/invite/' + token + '/', body)
        delivery = InvitationEmailDelivery.objects.get(invitation_id=app.invitation_id)
        self.assertEqual(delivery.status, 'accepted')
        self.assertIsNotNone(delivery.accepted_at)
        self.assertNotIn(token, str(list(GovernanceAudit.objects.values('details'))))
        self.assertNotIn(token, str(delivery.__dict__))

    def test_revoked_and_inactive_issuer_invitations_are_not_sent(self):
        from .invitation_email import process_next_email
        app, token = self.invite()
        ProjectInvitation.objects.filter(pk=app.invitation_id).update(revoked_at=timezone.now())
        with patch('core.invitation_email.GraphMailClient') as client:
            self.assertTrue(process_next_email())
        client.return_value.send.assert_not_called()
        self.assertEqual(InvitationEmailDelivery.objects.get(invitation_id=app.invitation_id).status, 'cancelled')

    def test_uncertain_submission_is_not_automatically_retried(self):
        from .invitation_email import process_next_email, retry_failed_emails
        from .notification_email import NotificationEmailError
        app, token = self.invite()
        with patch('core.invitation_email.GraphMailClient') as client:
            client.return_value.send.side_effect = NotificationEmailError('send_uncertain', uncertain=True)
            self.assertTrue(process_next_email())
            self.assertFalse(process_next_email())
        self.assertEqual(InvitationEmailDelivery.objects.get(invitation_id=app.invitation_id).status, 'uncertain')
        self.assertEqual(retry_failed_emails(), 0)

    def test_rejected_rate_limit_retries_same_job_without_new_invitation(self):
        from .invitation_email import process_next_email
        from .notification_email import NotificationEmailError
        from .models import InvitationEmailDelivery
        app, token = self.invite()
        with patch('core.invitation_email.GraphMailClient') as client:
            client.return_value.send.side_effect = NotificationEmailError('rate_limited', retryable=True)
            self.assertTrue(process_next_email())
        job = InvitationEmailDelivery.objects.get(invitation_id=app.invitation_id)
        self.assertEqual(job.status, 'queued')
        self.assertGreater(job.available_at, timezone.now())
        InvitationEmailDelivery.objects.filter(pk=job.pk).update(available_at=timezone.now()-timedelta(seconds=1))
        with patch('core.invitation_email.GraphMailClient') as client:
            self.assertTrue(process_next_email())
            self.assertFalse(process_next_email())
        self.assertEqual(ProjectInvitation.objects.count(), 1)
        self.assertEqual(InvitationEmailDelivery.objects.count(), 1)

    def test_interrupted_send_is_retained_as_uncertain_after_lease_expires(self):
        from .invitation_email import recover_interrupted_emails, process_next_email
        from .models import InvitationEmailDelivery
        app, token = self.invite()
        InvitationEmailDelivery.objects.filter(invitation_id=app.invitation_id).update(
            status='sending', lease_id=uuid.uuid4(), lease_expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(recover_interrupted_emails(), 1)
        self.assertEqual(recover_interrupted_emails(), 0)
        self.assertFalse(process_next_email())
        self.assertEqual(InvitationEmailDelivery.objects.get(invitation_id=app.invitation_id).status, 'uncertain')

    @override_settings(NOTIFICATION_EMAIL_ENABLED=False)
    def test_disabled_email_preserves_manual_invitation_and_no_queue(self):
        from .models import InvitationEmailDelivery
        app, token = self.invite()
        self.assertTrue(token)
        self.assertFalse(InvitationEmailDelivery.objects.exists())
        self.assertContains(self.client.get(reverse('company_onboarding_detail', args=[app.pk])),
                            'Share the private link manually')

    def test_bad_origin_never_sends_mail_or_changes_invitation(self):
        from .invitation_email import process_next_email
        app, token = self.invite()
        with override_settings(NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://evil.example.test'), \
                patch('core.invitation_email.GraphMailClient') as client:
            self.assertTrue(process_next_email())
        client.return_value.send.assert_not_called()
        self.assertEqual(InvitationEmailDelivery.objects.get(invitation_id=app.invitation_id).status, 'failed')
        self.assertEqual(ProjectInvitation.objects.get(pk=app.invitation_id).token_hash,
                         hashlib.sha256(token.encode()).hexdigest())
