"""AR-Q1: a rejected source must not consume unrelated users' recovery budget.

Independent post-functional security regression. Deliberately remains failing
until the owner approves and the implementation fixes the reproduced issue.
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .account_recovery_models import AccountRecoveryRequest, AccountRecoveryThrottle


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False, NOTIFICATION_EMAIL_ENABLED=True,
                   NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',
                   NOTIFICATION_EMAIL_CREDENTIALS_FILE='',
                   ACCOUNT_RECOVERY_TRUST_PROXY_IP=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RecoveryGlobalBudgetSecurityTests(TestCase):
    def test_rate_limited_source_cannot_exhaust_other_users_global_recovery_budget(self):
        user = User.objects.create_user('budget_security_registered',
                                       email='registered-security@example.test',
                                       password='Synthetic-Recovery-Security-779!')
        attacker = Client(enforce_csrf_checks=True)
        victim = Client(enforce_csrf_checks=True)
        url = reverse('account_password_reset')
        for client in [attacker, victim]:
            self.assertEqual(client.get(url).status_code, 200)

        # Loopback aliases traverse the real development middleware while giving
        # the recovery service distinct source IP identities, as a proxy does.
        for index in range(100):
            response = attacker.post(url, {'email':f'unknown-security-{index}@example.test'},
                                     REMOTE_ADDR='127.0.0.11',
                                     HTTP_X_CSRFTOKEN=attacker.cookies['csrftoken'].value)
            self.assertEqual(response.status_code, 302)
        self.assertFalse(AccountRecoveryRequest.objects.exists())

        response = victim.post(url, {'email':user.email}, REMOTE_ADDR='127.0.0.22',
                               HTTP_X_CSRFTOKEN=victim.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 302)
        # Both assertions are required. Generic success text alone cannot prove
        # that a legitimate registered user retained access to the reset queue.
        with self.subTest(control='unrelated eligible user can queue recovery'):
            self.assertEqual(AccountRecoveryRequest.objects.filter(user=user, status='queued').count(), 1)
        with self.subTest(control='denied source requests do not spend shared work capacity'):
            self.assertLessEqual(AccountRecoveryThrottle.objects.get(key='global').hits, 11)
