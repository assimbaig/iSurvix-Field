"""Independent saved-record tests for asynchronous company invitation delivery.

All records/media use the ordinary isolated backend runner. No live mailbox,
Microsoft credentials or operational company data are required or contacted.
"""
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.core.serializers.json import DjangoJSONEncoder
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Company, GovernanceAudit, IndustryCatalog, Profile, Project, ProjectInvitation
from .onboarding_service import apply_application, provision_application, review_application


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False,
                   NOTIFICATION_EMAIL_ENABLED=True,
                   NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',
                   NOTIFICATION_EMAIL_CREDENTIALS_FILE='',
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentInvitationEmailTests(TestCase):
    def setUp(self):
        self.industry = IndustryCatalog.objects.get(code='telecom')
        self.owner = User.objects.create_user('email_qa_owner', password='Fixture-Email-884!')
        User.objects.filter(pk=self.owner.pk).update(is_staff=True, is_superuser=True)
        self.owner.profile.role = Profile.Roles.SUPER_ADMIN
        self.owner.profile.save()
        self.owner.refresh_from_db()
        self.client = self.csrf_client(self.owner)

    def csrf_client(self, user):
        client = Client(enforce_csrf_checks=True)
        client.get('/login/')
        client.force_login(user)
        return client

    def ready(self, suffix='A'):
        application = apply_application(self.owner, request_key=uuid.uuid4(),
            name='Email QA company '+suffix, email='email-qa-'+suffix.lower()+'@example.test',
            industry=self.industry)
        review_application(self.owner, application.pk, approve=True,
                           reason='Synthetic independently reviewed contact')
        return provision_application(self.owner, application.pk)

    def invite(self, application, client=None):
        client = client or self.client
        return client.post(reverse('company_onboarding_action', args=[application.pk]),
            {'action':'invite'},
            HTTP_X_CSRFTOKEN=client.cookies[settings.CSRF_COOKIE_NAME].value)

    def delivery_model(self):
        return apps.get_model('core', 'InvitationEmailDelivery')

    def test_saved_invite_queues_once_and_refresh_truthfully_preserves_status(self):
        application = self.ready()
        response = self.invite(application)
        self.assertIn(response.status_code, (200, 302))
        application.refresh_from_db()
        invitation = ProjectInvitation.objects.get(pk=application.invitation_id)
        delivery = self.delivery_model().objects.get(invitation=invitation)
        self.assertEqual(delivery.status, 'queued')
        self.assertEqual(invitation.company_id, application.company_id)
        self.assertEqual(invitation.admin_industry_id, self.industry.pk)
        self.assertEqual(invitation.role, Profile.Roles.ADMIN)
        self.assertIsNone(invitation.project_id)
        refreshed = self.client.get(reverse('company_onboarding_detail', args=[application.pk]))
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn('queued', refreshed.content.decode().lower())
        self.assertNotIn('Email sent successfully', refreshed.content.decode())
        self.assertEqual(self.delivery_model().objects.filter(invitation=invitation).count(), 1)

    def test_replayed_onboarding_invite_does_not_queue_another_delivery(self):
        application = self.ready()
        self.assertIn(self.invite(application).status_code, (200, 302))
        application.refresh_from_db()
        first_invitation_id = application.invitation_id
        first_delivery = self.delivery_model().objects.get(invitation_id=first_invitation_id)
        for _ in range(2):
            self.assertIn(self.invite(application).status_code, (200, 302))
        application.refresh_from_db()
        self.assertEqual(application.invitation_id, first_invitation_id)
        self.assertEqual(ProjectInvitation.objects.filter(pk=first_invitation_id).count(), 1)
        self.assertEqual(list(self.delivery_model().objects.values_list('pk', flat=True)),
                         [first_delivery.pk])

    def test_forbidden_company_admin_cannot_issue_or_queue_platform_application(self):
        application = self.ready()
        admin = User.objects.create_user('email_qa_customer_admin', password='Fixture-Email-884!')
        admin.profile.role = Profile.Roles.ADMIN
        admin.profile.company = Company.objects.create(name='Email QA foreign company')
        admin.profile.admin_industry = self.industry
        admin.profile.save()
        response = self.invite(application, self.csrf_client(admin))
        self.assertEqual(response.status_code, 403)
        application.refresh_from_db()
        self.assertIsNone(application.invitation_id)
        self.assertEqual(ProjectInvitation.objects.count(), 0)
        self.assertEqual(self.delivery_model().objects.count(), 0)

    def test_bearer_is_absent_from_outbox_and_audit_and_still_works_for_manual_link(self):
        application = self.ready()
        response = self.invite(application)
        self.assertEqual(response.status_code, 200)
        url = response.context['invite_url']
        self.assertTrue(url)
        token = url.rstrip('/').rsplit('/', 1)[-1]
        application.refresh_from_db()
        invitation = ProjectInvitation.objects.get(pk=application.invitation_id)
        saved_delivery = self.delivery_model().objects.get(invitation=invitation)
        data = json.dumps(self.delivery_model().objects.filter(pk=saved_delivery.pk).values().get(),
                          cls=DjangoJSONEncoder)
        audit = json.dumps(list(GovernanceAudit.objects.values_list('details', flat=True)),
                           cls=DjangoJSONEncoder)
        self.assertNotIn(token, data)
        self.assertNotIn(token, audit)
        anonymous = Client()
        self.assertEqual(anonymous.get(reverse('governance_accept_invite', args=[token])).status_code, 200)

    @override_settings(NOTIFICATION_EMAIL_ENABLED=False)
    def test_disabled_delivery_preserves_legacy_manual_invites_without_backfill(self):
        application = self.ready()
        response = self.invite(application)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['invite_url'])
        application.refresh_from_db()
        self.assertTrue(application.invitation_id)
        self.assertEqual(self.delivery_model().objects.count(), 0)

    def test_missing_credentials_cannot_invalidate_saved_invite_or_claim_email_sent(self):
        from .invitation_email import process_next_email
        application = self.ready()
        response = self.invite(application)
        token = response.context['invite_url'].rstrip('/').rsplit('/', 1)[-1]
        application.refresh_from_db()
        self.assertTrue(process_next_email())
        delivery = self.delivery_model().objects.get(invitation_id=application.invitation_id)
        self.assertEqual(delivery.status, 'failed')
        self.assertTrue(delivery.error_code)
        detail = self.client.get(reverse('company_onboarding_detail', args=[application.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn('Email sent successfully', detail.content.decode())
        self.assertEqual(Client().get(reverse('governance_accept_invite', args=[token])).status_code, 200)

    def test_transport_acceptance_is_persisted_once_and_not_claimed_as_inbox_delivery(self):
        from .invitation_email import process_next_email
        application = self.ready()
        self.invite(application)
        application.refresh_from_db()
        with patch('core.invitation_email.GraphMailClient') as graph:
            self.assertTrue(process_next_email())
            self.assertFalse(process_next_email())
        graph.return_value.send.assert_called_once()
        delivery = self.delivery_model().objects.get(invitation_id=application.invitation_id)
        self.assertEqual(delivery.status, 'accepted')
        self.assertIsNotNone(delivery.accepted_at)
        detail = self.client.get(reverse('company_onboarding_detail', args=[application.pk]))
        self.assertEqual(detail.status_code, 200)
        text = detail.content.decode().lower()
        self.assertIn('accepted', text)
        self.assertNotIn('delivered to inbox', text)

    def test_ambiguous_send_is_not_automatically_replayed(self):
        from .invitation_email import process_next_email, retry_failed_emails
        from .notification_email import NotificationEmailError
        application = self.ready()
        self.invite(application)
        application.refresh_from_db()
        with patch('core.invitation_email.GraphMailClient') as graph:
            graph.return_value.send.side_effect = NotificationEmailError('request_timeout', uncertain=True)
            self.assertTrue(process_next_email())
            self.assertEqual(retry_failed_emails(), 0)
            self.assertFalse(process_next_email())
        graph.return_value.send.assert_called_once()
        delivery = self.delivery_model().objects.get(invitation_id=application.invitation_id)
        self.assertEqual(delivery.status, 'uncertain')

    def test_revoked_and_expired_invites_are_cancelled_without_sending(self):
        from .invitation_email import process_next_email
        applications = [self.ready('Revoked'), self.ready('Expired')]
        for application in applications:
            self.invite(application)
            application.refresh_from_db()
        ProjectInvitation.objects.filter(pk=applications[0].invitation_id).update(revoked_at=timezone.now())
        ProjectInvitation.objects.filter(pk=applications[1].invitation_id).update(expires_at=timezone.now()-timedelta(seconds=1))
        with patch('core.invitation_email.GraphMailClient') as graph:
            self.assertTrue(process_next_email())
            self.assertTrue(process_next_email())
            self.assertFalse(process_next_email())
        graph.return_value.send.assert_not_called()
        self.assertEqual(self.delivery_model().objects.filter(status='cancelled').count(), 2)

    def test_issuer_authority_revoked_after_queue_prevents_send(self):
        from .invitation_email import process_next_email
        application = self.ready()
        self.invite(application)
        application.refresh_from_db()
        User.objects.filter(pk=self.owner.pk).update(is_superuser=False)
        with patch('core.invitation_email.GraphMailClient') as graph:
            self.assertTrue(process_next_email())
        graph.return_value.send.assert_not_called()
        delivery = self.delivery_model().objects.get(invitation_id=application.invitation_id)
        self.assertEqual(delivery.status, 'cancelled')

    def company_admin(self, suffix):
        user = User.objects.create_user('email_project_admin_'+suffix, password='Fixture-Email-884!')
        user.profile.role = Profile.Roles.ADMIN
        user.profile.company = Company.objects.create(name='Email project company '+suffix)
        user.profile.admin_industry = self.industry
        user.profile.save()
        project = Project.objects.create(name='Email QA project '+suffix,
            company=user.profile.company, industry=self.industry.code, administrator=user)
        user.profile.project = project
        user.profile.save(update_fields=['project'])
        return user, project

    def test_project_admin_engineer_invite_uses_same_queue_and_refresh_status(self):
        admin, project = self.company_admin('A')
        client = self.csrf_client(admin)
        response = client.post(reverse('governance_invite'),
            {'email':'new-engineer@example.test', 'role':Profile.Roles.ENGINEER, 'project':project.pk},
            HTTP_X_CSRFTOKEN=client.cookies[settings.CSRF_COOKIE_NAME].value)
        self.assertEqual(response.status_code, 200)
        invitation = ProjectInvitation.objects.get(email='new-engineer@example.test')
        self.assertEqual(invitation.project_id, project.pk)
        self.assertEqual(invitation.company_id, project.company_id)
        self.assertEqual(invitation.role, Profile.Roles.ENGINEER)
        self.assertEqual(self.delivery_model().objects.get(invitation=invitation).status, 'queued')
        self.assertIn('queued', response.content.decode().lower())
        refreshed = client.get(reverse('governance_home')+'?view=administration')
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn('queued', refreshed.content.decode().lower())

    def test_foreign_project_post_does_not_create_invitation_or_mail(self):
        admin_a, project_a = self.company_admin('A')
        admin_b, project_b = self.company_admin('B')
        client = self.csrf_client(admin_a)
        response = client.post(reverse('governance_invite'),
            {'email':'foreign-engineer@example.test', 'role':Profile.Roles.ENGINEER, 'project':project_b.pk},
            HTTP_X_CSRFTOKEN=client.cookies[settings.CSRF_COOKIE_NAME].value)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ProjectInvitation.objects.filter(email='foreign-engineer@example.test').exists())
        self.assertEqual(self.delivery_model().objects.count(), 0)
