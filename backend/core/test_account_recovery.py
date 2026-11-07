"""Account recovery uses isolated records and transport fixtures, never live mail."""
from datetime import timedelta
from unittest.mock import patch
from io import StringIO
import json

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.management import call_command


@override_settings(NOTIFICATION_EMAIL_ENABLED=True,
    NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver', ALLOWED_HOSTS=['testserver'],
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AccountRecoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('recovery-fixture', email='fixture@example.test', password='BeforeFixture849!')

    def queued(self, email=None, ip='192.0.2.10'):
        from .account_recovery import request_reset
        from .account_recovery_models import AccountRecoveryRequest
        request_reset(email or self.user.email, ip)
        return AccountRecoveryRequest.objects.order_by('-created_at').first()

    def link(self, row):
        from .account_recovery import _reset_token
        return reverse('account_password_reset_confirm', args=[row.pk, _reset_token(row)])

    def test_request_never_returns_a_token_or_sends_synchronously(self):
        from .account_recovery import request_reset
        from .account_recovery_models import AccountRecoveryRequest
        with patch('core.account_recovery.GraphMailClient') as mail:
            self.assertIsNone(request_reset('fixture@example.test', '192.0.2.1'))
        mail.assert_not_called()
        row = AccountRecoveryRequest.objects.get()
        self.assertEqual(row.status, 'queued')
        self.assertEqual(row.attempts, 0)
        self.assertNotIn('fixture@example.test', str(row.__dict__))
        self.assertNotIn('BeforeFixture849!', str(row.__dict__))

    def test_unknown_inactive_locked_and_duplicate_email_accounts_do_not_queue(self):
        from .account_recovery import request_reset
        from .account_recovery_models import AccountRecoveryRequest
        request_reset('unknown@example.test', '192.0.2.1')
        self.user.is_active = False; self.user.save(update_fields=['is_active'])
        request_reset(self.user.email, '192.0.2.2')
        self.user.is_active = True; self.user.save(update_fields=['is_active'])
        self.user.profile.is_locked = True; self.user.profile.save(update_fields=['is_locked'])
        request_reset(self.user.email, '192.0.2.3')
        self.user.profile.is_locked = False; self.user.profile.save(update_fields=['is_locked'])
        User.objects.create_user('ambiguous-recovery', email=self.user.email, password='FixtureOther849!')
        request_reset(self.user.email, '192.0.2.4')
        self.assertFalse(AccountRecoveryRequest.objects.exists())

    def test_expiry_email_and_password_change_invalidate_links(self):
        from .account_recovery import valid_reset
        row=self.queued(); url=self.link(row)
        self.assertTrue(valid_reset(row.pk, url.split('/')[-2]))
        row.expires_at=timezone.now()-timedelta(seconds=1); row.save(update_fields=['expires_at'])
        self.assertFalse(valid_reset(row.pk,url.split('/')[-2]))
        row=self.queued(ip='192.0.2.11'); token=self.link(row).split('/')[-2]
        self.user.email='changed@example.test'; self.user.save(update_fields=['email'])
        self.assertFalse(valid_reset(row.pk,token))
        row=self.queued(ip='192.0.2.12'); token=self.link(row).split('/')[-2]
        self.user.set_password('AnotherFixture849!'); self.user.save(update_fields=['password'])
        self.assertFalse(valid_reset(row.pk,token))

    def test_replacement_invalidates_old_request_and_replay_cannot_change_password(self):
        from .account_recovery import valid_reset
        first=self.queued(); first_url=self.link(first)
        second=self.queued(); second_url=self.link(second)
        self.assertFalse(valid_reset(first.pk,first_url.split('/')[-2]))
        response=self.client.post(second_url,{'new_password1':'AfterFixture849!', 'new_password2':'AfterFixture849!'})
        self.assertRedirects(response,reverse('account_password_reset_complete'))
        self.user.refresh_from_db(); self.assertTrue(self.user.check_password('AfterFixture849!'))
        self.assertNotIn('_auth_user_id',self.client.session)
        self.client.post(second_url,{'new_password1':'AttackerFixture849!', 'new_password2':'AttackerFixture849!'})
        self.user.refresh_from_db(); self.assertTrue(self.user.check_password('AfterFixture849!'))

    def test_get_does_not_consume_and_csrf_is_enforced_on_post(self):
        row=self.queued(); url=self.link(row)
        self.assertEqual(self.client.get(url).status_code,200)
        row.refresh_from_db(); self.assertIsNone(row.used_at)
        strict=Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(url,{'new_password1':'AfterFixture849!','new_password2':'AfterFixture849!'}).status_code,403)
        self.assertEqual(strict.post(reverse('account_password_reset'),{'email':self.user.email}).status_code,403)

    def test_reset_only_writes_password_and_preserves_concurrent_account_fields(self):
        from .account_recovery_forms import RecoveryPasswordForm
        row=self.queued();url=self.link(row)
        original=RecoveryPasswordForm.is_valid
        def changed(form):
            valid=original(form)
            User.objects.filter(pk=self.user.pk).update(first_name='Retained administrator edit')
            return valid
        with patch.object(RecoveryPasswordForm,'is_valid',changed):
            response=self.client.post(url,{'new_password1':'AfterFixture849!','new_password2':'AfterFixture849!'})
        self.assertEqual(response.status_code,302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name,'Retained administrator edit')
        self.assertTrue(self.user.check_password('AfterFixture849!'))

    def test_known_and_unknown_email_have_same_public_confirmation_and_ignore_host_redirects(self):
        route=reverse('account_password_reset')
        known=self.client.post(route,{'email':self.user.email,'next':'https://evil.example/'})
        unknown=self.client.post(route,{'email':'unknown@example.test'})
        self.assertEqual(known.status_code,unknown.status_code)
        self.assertEqual(known['Location'],unknown['Location'])
        self.assertEqual(known['Location'],reverse('account_password_reset_done'))

    def test_account_ip_and_global_limits_bound_outbox_and_throttle_records(self):
        from .account_recovery import request_reset
        from .account_recovery_models import AccountRecoveryRequest,AccountRecoveryThrottle
        for index in range(8):request_reset(self.user.email,f'192.0.2.{index}')
        self.assertEqual(AccountRecoveryRequest.objects.count(),3)
        for index in range(130):request_reset(f'unknown-{index}@example.test',f'198.51.100.{index}')
        self.assertLessEqual(AccountRecoveryThrottle.objects.count(),201)
        self.assertEqual(AccountRecoveryRequest.objects.count(),3)

    def test_worker_sends_single_use_link_once_and_preserves_uncertain_delivery(self):
        from .account_recovery import process_next_reset_email
        from .notification_email import NotificationEmailError
        row=self.queued()
        with patch('core.account_recovery.GraphMailClient') as mail:
            self.assertTrue(process_next_reset_email()); self.assertFalse(process_next_reset_email())
            args=mail.return_value.send.call_args.args
            self.assertEqual(args[0],self.user.email)
            self.assertIn('https://testserver'+self.link(row),args[2])
            self.assertNotIn('BeforeFixture849!',args[2])
            self.assertTrue(mail.return_value.send.call_args.kwargs['branded'])
        row.refresh_from_db(); self.assertEqual(row.status,'accepted')
        row=self.queued(ip='192.0.2.20')
        with patch('core.account_recovery.GraphMailClient') as mail:
            mail.return_value.send.side_effect=NotificationEmailError('send_outcome_unknown',uncertain=True)
            self.assertTrue(process_next_reset_email()); self.assertFalse(process_next_reset_email())
        row.refresh_from_db(); self.assertEqual(row.status,'uncertain')

    def test_worker_rechecks_account_after_oauth_and_cancels_revoked_destination(self):
        from .account_recovery import process_next_reset_email
        row=self.queued()
        def revoke(*args,**kwargs):
            User.objects.filter(pk=self.user.pk).update(email='wrong@example.test')
            kwargs['before_send']()
        with patch('core.account_recovery.GraphMailClient') as mail:
            mail.return_value.send.side_effect=revoke
            self.assertTrue(process_next_reset_email())
        row.refresh_from_db();self.assertEqual(row.status,'cancelled')

    def test_interrupted_send_is_uncertain_not_automatically_resent_after_restart(self):
        from .account_recovery import recover_interrupted_reset_emails,process_next_reset_email,retry_failed_reset_emails
        row=self.queued();row.status='sending';row.lease_id=__import__('uuid').uuid4()
        row.lease_expires_at=timezone.now()-timedelta(seconds=1)
        row.save(update_fields=['status','lease_id','lease_expires_at'])
        self.assertEqual(recover_interrupted_reset_emails(),1)
        self.assertEqual(recover_interrupted_reset_emails(),0)
        with patch('core.account_recovery.GraphMailClient') as mail:self.assertFalse(process_next_reset_email())
        mail.assert_not_called();self.assertEqual(retry_failed_reset_emails(),0)
        row.refresh_from_db();self.assertEqual(row.status,'uncertain')

    def test_definite_provider_failures_retry_bounded_same_record_and_expired_rows_cancel(self):
        from .account_recovery import process_next_reset_email,retry_failed_reset_emails
        from .account_recovery_models import AccountRecoveryRequest
        from .notification_email import NotificationEmailError
        row=self.queued()
        with patch('core.account_recovery.GraphMailClient') as mail:
            mail.return_value.send.side_effect=NotificationEmailError('authentication_unavailable',retryable=True)
            for _ in range(3):
                AccountRecoveryRequest.objects.filter(pk=row.pk).update(available_at=timezone.now()-timedelta(seconds=1))
                self.assertTrue(process_next_reset_email())
            self.assertFalse(process_next_reset_email())
        row.refresh_from_db();self.assertEqual(row.status,'failed');self.assertEqual(row.attempts,3)
        self.assertEqual(AccountRecoveryRequest.objects.count(),1)
        AccountRecoveryRequest.objects.filter(pk=row.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(retry_failed_reset_emails(),0)

    def test_invalid_token_and_weak_password_preserve_account_and_link(self):
        row=self.queued();url=self.link(row)
        self.assertEqual(self.client.post(url.replace(url.split('/')[-2],'0'*64),
            {'new_password1':'AfterFixture849!','new_password2':'AfterFixture849!'}).status_code,400)
        response=self.client.post(url,{'new_password1':'a','new_password2':'a'})
        self.assertEqual(response.status_code,400)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password('BeforeFixture849!'))
        row.refresh_from_db();self.assertIsNone(row.used_at)

    def test_existing_email_worker_does_not_starve_reset_queue_when_other_queues_are_busy(self):
        command='core.management.commands.run_invitation_email_worker.'
        with patch(command+'load_config'),patch(command+'queue_daily_digests'), \
                patch(command+'process_next_email',side_effect=[True,KeyboardInterrupt]), \
                patch(command+'process_next_workflow_email',return_value=True), \
                patch(command+'process_next_reset_email',return_value=True) as reset:
            call_command('run_invitation_email_worker',interval=1,stdout=StringIO())
        self.assertGreaterEqual(reset.call_count,1)

    def test_reset_runs_actual_oauth_and_html_send_against_local_http_fixture(self):
        from .account_recovery import process_next_reset_email
        from .notification_email import GraphMailConfig
        from .test_notification_email_transport import graph_fixture,TENANT,CLIENT,SECRET
        row=self.queued()
        with graph_fixture() as records,patch('core.notification_email.load_config',
                return_value=GraphMailConfig(TENANT,CLIENT,SECRET)):
            self.assertTrue(process_next_reset_email());self.assertFalse(process_next_reset_email())
        self.assertEqual(len(records),2)
        payload=json.loads(records[-1]['raw'])
        self.assertEqual(payload['message']['body']['contentType'],'HTML')
        body=payload['message']['body']['content']
        self.assertIn('https://testserver'+self.link(row),body)
        self.assertIn('/static/core/img/ifield-logo.webp',body)
        self.assertIn('please do not reply',body.lower())
        self.assertNotIn('BeforeFixture849!',body)
        self.assertEqual(payload['message']['toRecipients'],[{'emailAddress':{'address':self.user.email}}])

    def test_untrusted_proxy_headers_do_not_bypass_ip_limit(self):
        from .account_recovery_models import AccountRecoveryThrottle
        route=reverse('account_password_reset')
        for index in range(15):
            self.client.post(route,{'email':f'unknown-{index}@example.test'},
                REMOTE_ADDR='127.0.0.1',HTTP_X_REAL_IP=f'198.51.100.{index}',HTTP_X_FORWARDED_FOR=f'198.51.100.{index}')
        ips=AccountRecoveryThrottle.objects.filter(key__startswith='ip:')
        self.assertEqual(ips.count(),1);self.assertEqual(ips.get().hits,10)

    @override_settings(ACCOUNT_RECOVERY_TRUST_PROXY_IP=True)
    def test_configured_trusted_proxy_uses_only_one_valid_overwritten_real_ip(self):
        from .account_recovery_models import AccountRecoveryThrottle
        route=reverse('account_password_reset')
        self.client.post(route,{'email':'unknown-1@example.test'},REMOTE_ADDR='127.0.0.1',HTTP_X_REAL_IP='198.51.100.1')
        self.client.post(route,{'email':'unknown-2@example.test'},REMOTE_ADDR='127.0.0.1',HTTP_X_REAL_IP='198.51.100.2')
        self.client.post(route,{'email':'unknown-3@example.test'},REMOTE_ADDR='127.0.0.1',HTTP_X_REAL_IP='malformed,198.51.100.3')
        self.assertEqual(AccountRecoveryThrottle.objects.filter(key__startswith='ip:').count(),3)


class EmailPresentationTests(TestCase):
    @override_settings(NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',ALLOWED_HOSTS=['testserver'])
    def test_html_signature_escapes_content_and_only_links_fixed_application_origin(self):
        from .email_presentation import present_email
        plain,html=present_email('Fixture <script>','Hello <script>alert(1)</script>\nhttps://testserver/private/\nhttps://evil.example/')
        self.assertIn('please do not reply',plain.lower())
        self.assertIn('iField',plain)
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn('src="https://testserver/static/core/img/ifield-logo.webp"',html)
        self.assertIn('href="https://testserver/private/"',html)
        self.assertNotIn('href="https://evil.example/',html)
