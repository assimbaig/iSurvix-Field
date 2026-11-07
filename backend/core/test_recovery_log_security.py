"""AR-Q2: a rejected weak password must not put a live reset bearer in logs.

Uses the actual configured FileHandler and its existing filters, not assertLogs
or a replacement handler. Run through scripts/run_backend_tests.py so the log,
database and media are disposable. No raw bearer is included in failure text.
"""
import logging
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .account_recovery import request_reset, _reset_token, valid_reset
from .account_recovery_models import AccountRecoveryRequest


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False, NOTIFICATION_EMAIL_ENABLED=True,
                   NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',
                   NOTIFICATION_EMAIL_CREDENTIALS_FILE='',
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RecoveryLogSecurityTests(TestCase):
    def test_weak_password_failure_never_logs_the_still_valid_recovery_bearer(self):
        user = User.objects.create_user('recovery_log_security',
                                       email='recovery-log-security@example.test',
                                       password='Synthetic-Log-Security-779!')
        request_reset(user.email, '127.0.0.11')
        row = AccountRecoveryRequest.objects.get(user=user)
        token = _reset_token(row)
        url = reverse('account_password_reset_confirm', args=[row.pk, token])
        handlers = [handler for handler in logging.getLogger('django.request').handlers
                    if isinstance(handler, logging.FileHandler)]
        self.assertTrue(handlers, 'The real configured request file handler must be exercised')
        offsets = []
        isolated_root = Path(settings.MEDIA_ROOT).resolve().parent
        for handler in handlers:
            handler.flush()
            log = Path(handler.baseFilename).resolve()
            self.assertTrue(log.is_relative_to(isolated_root),
                            'Run this regression through the isolated backend runner')
            self.assertTrue(handler.filters, 'Existing application log filters must remain attached')
            offsets.append((handler, log, log.stat().st_size if log.exists() else 0))

        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get(url).status_code, 200)
        response = client.post(url, {'new_password1':'123', 'new_password2':'123'},
                               HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 400)
        row.refresh_from_db()
        user.refresh_from_db()
        self.assertIsNone(row.used_at)
        self.assertTrue(user.check_password('Synthetic-Log-Security-779!'))
        self.assertIsNotNone(valid_reset(row.pk, token),
                             'The rejected weak password must leave the valid link usable')
        for handler, log, offset in offsets:
            handler.flush()
            appended = log.read_bytes()[offset:]
            self.assertTrue(appended, 'The rejected request must reach the actual request log')
            # Avoid assertNotIn, which would print the bearer and raw log bytes
            # in the failure report and create a second credential disclosure.
            self.assertFalse(token.encode('ascii') in appended,
                             'The configured request log disclosed a still-valid recovery bearer')
