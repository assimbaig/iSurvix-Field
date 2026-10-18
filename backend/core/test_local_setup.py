"""Local first-run setup must never replace an existing administrator."""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from .models import Profile


@override_settings(ROOT_URLCONF='checklist.urls_local', LOCAL_AI_ENABLED=True)
class LocalSetupTests(TestCase):
    def data(self):
        return {'username': 'chosen_administrator', 'password1': 'Test-fixture-pass-629!',
                'password2': 'Test-fixture-pass-629!'}

    def test_first_run_requires_csrf_and_creates_chosen_account_once(self):
        strict = Client(enforce_csrf_checks=True)
        self.assertRedirects(strict.get('/local/'), '/local/setup/')
        self.assertEqual(strict.post('/local/setup/', self.data()).status_code, 403)
        self.assertEqual(User.objects.count(), 0)
        strict.get('/local/setup/')
        data = self.data()
        data['csrfmiddlewaretoken'] = strict.cookies['csrftoken'].value
        response = strict.post('/local/setup/', data)
        self.assertEqual(response.status_code, 302)
        user = User.objects.get()
        self.assertTrue(user.is_superuser and user.is_staff)
        self.assertEqual(user.profile.role, Profile.Roles.SUPER_ADMIN)
        self.assertTrue(user.check_password(data['password1']))
        other = Client()
        self.assertEqual(other.post('/local/setup/', self.data()).status_code, 302)
        self.assertEqual(User.objects.count(), 1)

    def test_remote_and_disabled_setup_rejected(self):
        self.assertIn(self.client.get('/local/setup/', REMOTE_ADDR='192.168.1.20').status_code, (403, 404))
        with override_settings(LOCAL_AI_ENABLED=False):
            self.assertEqual(self.client.get('/local/setup/').status_code, 404)
        self.assertEqual(User.objects.count(), 0)

    def test_invalid_password_creates_nothing(self):
        response = self.client.post('/local/setup/', {'username': 'chosen', 'password1': 'a', 'password2': 'b'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)
