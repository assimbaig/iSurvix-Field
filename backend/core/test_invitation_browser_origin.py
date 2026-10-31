"""Invitation bearer protection must allow real same-origin CSRF form posts."""
from datetime import timedelta
import hashlib

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Company, IndustryCatalog, Profile, ProjectInvitation


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class InvitationBrowserOriginTests(TestCase):
    def setUp(self):
        owner=User.objects.create_superuser('origin-owner', 'owner@example.test', 'Fixture849!')
        self.token='synthetic-origin-token-1234567890'
        self.invite=ProjectInvitation.objects.create(
            token_hash=hashlib.sha256(self.token.encode()).hexdigest(),
            email='new-admin@example.test', role=Profile.Roles.ADMIN,
            company=Company.objects.create(name='Origin fixture company'),
            admin_industry=IndustryCatalog.objects.get(code='telecom'),
            created_by=owner, expires_at=timezone.now()+timedelta(hours=72))
        self.url=reverse('governance_accept_invite',args=[self.token])
        self.browser=Client(enforce_csrf_checks=True)
        self.page=self.browser.get(self.url)

    def post(self, origin):
        return self.browser.post(self.url,{
            'username':'origin-company-admin','email':self.invite.email,'password1':'Synthetic-Origin-849!',
            'password2':'Synthetic-Origin-849!',
            'csrfmiddlewaretoken':self.browser.cookies[settings.CSRF_COOKIE_NAME].value,
        },HTTP_ORIGIN=origin)

    def test_policy_suppresses_bearer_path_without_making_form_origin_opaque(self):
        # no-referrer makes browser form Origin:null and prevents acceptance;
        # path-bearing policies can disclose the invitation bearer to resources.
        self.assertIn(self.page.headers.get('Referrer-Policy'), {'origin','strict-origin'})
        self.assertIn('no-store',self.page.headers['Cache-Control'])

    def test_valid_csrf_same_origin_accepts_and_consumes_once(self):
        self.assertEqual(self.post('http://testserver').status_code,302)
        self.invite.refresh_from_db()
        self.assertIsNotNone(self.invite.accepted_at)
        person=User.objects.get(username='origin-company-admin')
        self.assertEqual(person.profile.company_id,self.invite.company_id)
        self.assertFalse(person.is_superuser or person.is_staff)
        self.assertEqual(self.post('http://testserver').status_code,404)

    def test_null_and_foreign_origins_remain_rejected_with_valid_csrf_token(self):
        for origin in ['null','https://foreign.example.test']:
            with self.subTest(origin=origin):
                self.assertEqual(self.post(origin).status_code,403)
        self.invite.refresh_from_db()
        self.assertIsNone(self.invite.accepted_at)
        self.assertFalse(User.objects.filter(username='origin-company-admin').exists())
