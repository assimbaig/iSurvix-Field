"""Independent adversarial release-notice and upgrade-retention checks.

Synthetic state only. Security findings are reported, never fixed here without
the owner's separate approval.
"""
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, OperationalError, transaction
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import Profile, ReleaseNoticeAcknowledgement
from .release_notice_models import SESSION_KEY
from .test_invitation_email_upgrade import BUILD, ROOT


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False, ISURVIX_RELEASE_ID='a'*40,
    NOTIFICATION_EMAIL_ENABLED=False, WORKFLOW_NOTIFICATION_EMAIL_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ReleaseNoticeSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('security_notice_first', password='Synthetic-notice-security!')
        self.user.profile.role = Profile.Roles.ENGINEER
        self.user.profile.save()
        self.other = User.objects.create_user('security_notice_other', password='Synthetic-notice-security!')
        self.other.profile.role = Profile.Roles.CLIENT
        self.other.profile.save()
        self.client = Client(enforce_csrf_checks=True, raise_request_exception=False)
        self.client.force_login(self.user)

    def notice(self, client=None):
        response = (client or self.client).get(reverse('governance_home'), follow=True)
        self.assertEqual(response.status_code, 200)
        return response.context['release_notice']

    def post(self, notice, *, client=None, remember=True, **extra):
        browser = client or self.client
        payload = {'release_id': notice['release_id'], 'session_nonce': notice['cache_nonce'],
                   'suppress_current': remember, **extra}
        return browser.post(reverse('release_notice_acknowledge'), json.dumps(payload),
            content_type='application/json', HTTP_X_CSRFTOKEN=browser.cookies['csrftoken'].value)

    def test_deeply_nested_small_json_is_rejected_without_server_error(self):
        self.notice()
        body = '['*2047 + '0' + ']'*2047
        self.assertLess(len(body.encode()), 4096)
        response = self.client.post(reverse('release_notice_acknowledge'), body,
            content_type='application/json', HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ReleaseNoticeAcknowledgement.objects.exists())

    def test_strict_csrf_authentication_and_methods_protect_preference(self):
        current = self.notice()
        raw = json.dumps({'release_id': current['release_id'], 'session_nonce': current['cache_nonce'], 'suppress_current': True})
        self.assertEqual(self.client.post(reverse('release_notice_acknowledge'), raw,
            content_type='application/json').status_code, 403)
        self.assertEqual(self.client.get(reverse('release_notice_acknowledge')).status_code, 405)
        self.assertIn(Client().post(reverse('release_notice_acknowledge'), raw,
            content_type='application/json').status_code, (302, 401, 403))
        self.assertFalse(ReleaseNoticeAcknowledgement.objects.exists())
        self.assertEqual(self.post(current).status_code, 200)

    def test_nonce_from_unviewed_other_account_or_other_device_cannot_be_used(self):
        fresh = Client();fresh.force_login(self.user)
        invalid = fresh.post(reverse('release_notice_acknowledge'), json.dumps({
            'release_id': 'a'*40, 'session_nonce': 'A'*32, 'suppress_current': True}), content_type='application/json')
        self.assertEqual(invalid.status_code, 409)
        first = self.notice()
        device = Client(enforce_csrf_checks=True);device.force_login(self.user)
        second = self.notice(device)
        other = Client(enforce_csrf_checks=True);other.force_login(self.other)
        foreign = self.notice(other)
        self.assertNotEqual(first['cache_nonce'], second['cache_nonce'])
        self.assertNotEqual(first['actor_key'], foreign['actor_key'])
        self.assertEqual(self.post(second).status_code, 409)
        self.assertEqual(self.post(foreign).status_code, 409)
        self.assertFalse(ReleaseNoticeAcknowledgement.objects.exists())
        self.assertEqual(self.post(foreign, client=other).status_code, 200)
        self.assertEqual(list(ReleaseNoticeAcknowledgement.objects.values_list('user_id', flat=True)), [self.other.pk])

    def test_client_cannot_preacknowledge_arbitrary_future_versions_or_another_user(self):
        current = self.notice()
        for index in range(1, 15):
            with self.subTest(version=index):
                self.assertEqual(self.post(current, release_id=f'{index:040x}').status_code, 409)
        for extra in ({'user_id': self.other.pk}, {'actor_key': current['actor_key']}, {'company_id': 1}):
            with self.subTest(field=next(iter(extra))):
                self.assertEqual(self.post(current, **extra).status_code, 400)
        self.assertFalse(ReleaseNoticeAcknowledgement.objects.exists())

    def test_duplicate_json_oversize_and_nonboolean_values_remain_rejected(self):
        current = self.notice()
        url = reverse('release_notice_acknowledge')
        token = self.client.cookies['csrftoken'].value
        duplicate = ('{"release_id":"'+current['release_id']+'","session_nonce":"'+current['cache_nonce']
            +'","suppress_current":false,"suppress_current":true}')
        for raw in (duplicate, ' ' * 4097, '{', 'null', '[]', '"text"'):
            with self.subTest(size=len(raw)):
                self.assertEqual(self.client.post(url, raw, content_type='application/json',
                    HTTP_X_CSRFTOKEN=token).status_code, 400)
        for value in (0, 1, 'true', None, [], {}):
            with self.subTest(value_type=type(value).__name__):
                self.assertEqual(self.post(current, remember=value).status_code, 400)
        self.assertFalse(ReleaseNoticeAcknowledgement.objects.exists())

    def test_nonce_release_and_session_shapes_are_validated_without_echoing_private_state(self):
        current = self.notice()
        for nonce in ('', '\ud800', '短'*20, 'A'*81, True, 99, ['A'*32]):
            with self.subTest(kind=type(nonce).__name__):
                self.assertEqual(self.post(current, session_nonce=nonce).status_code, 400)
        for release in ('', True, None, 'a'*81, 'local-<script>', 'b'*40):
            with self.subTest(release_type=type(release).__name__):
                self.assertIn(self.post(current, release_id=release).status_code, (400, 409))
        rendered = json.dumps(current)
        self.assertNotIn(self.client.session.session_key, rendered)
        self.assertNotIn(self.user.username, rendered)
        self.assertNotIn('user_id', current)
        self.assertFalse(ReleaseNoticeAcknowledgement.objects.exists())

    def test_poisoned_session_slot_cannot_hide_another_account_notice(self):
        current = self.notice()
        for corrupt in (
            {'user_id': self.other.pk, 'release_key': 'a'*40, 'nonce': 'A'*32,
                'actor_key': 'B'*24, 'dismissed': True, 'remembered': True},
            {'user_id': True, 'release_key': 'a'*40, 'nonce': 'A'*32,
                'actor_key': 'B'*24, 'dismissed': True, 'remembered': True},
            {'user_id': self.user.pk, 'release_key': 'a'*40, 'nonce': 'A'*32,
                'actor_key': 'B'*24, 'dismissed': 'true', 'remembered': False},
        ):
            with self.subTest(shape=type(corrupt['user_id']).__name__):
                session = self.client.session;session[SESSION_KEY] = corrupt;session.save()
                fresh = self.notice()
                self.assertIsNotNone(fresh)
                self.assertNotEqual(fresh['cache_nonce'], 'A'*32)
        self.assertFalse(ReleaseNoticeAcknowledgement.objects.exists())

    def test_persisted_lock_inactivity_and_fake_superadmin_role_block_old_page_ack(self):
        current = self.notice()
        Profile.objects.filter(user=self.user).update(is_locked=True)
        self.assertEqual(self.post(current).status_code, 403)
        Profile.objects.filter(user=self.user).update(is_locked=False, role=Profile.Roles.SUPER_ADMIN)
        self.assertEqual(self.post(current).status_code, 403)
        Profile.objects.filter(user=self.user).update(role=Profile.Roles.ENGINEER)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertIn(self.post(current).status_code, (302, 401, 403))
        self.assertFalse(ReleaseNoticeAcknowledgement.objects.exists())

    def test_saved_choice_is_idempotent_and_old_session_cannot_erase_it(self):
        current = self.notice()
        for _ in range(3):
            self.assertEqual(self.post(current).status_code, 200)
        self.assertEqual(self.post(current, remember=False).json()['dismissal'], 'remembered')
        self.assertEqual(ReleaseNoticeAcknowledgement.objects.filter(user=self.user, release_key='a'*40).count(), 1)
        self.assertFalse(ReleaseNoticeAcknowledgement.objects.filter(user=self.other).exists())

    def test_new_login_and_next_release_rotate_context_without_mutating_previous_choice(self):
        current = self.notice()
        self.assertEqual(self.post(current).status_code, 200)
        self.client.logout();self.client.force_login(self.user)
        self.assertIsNone(self.notice())
        with override_settings(ISURVIX_RELEASE_ID='b'*40):
            next_notice = self.notice()
            self.assertNotEqual(current['cache_nonce'], next_notice['cache_nonce'])
            self.assertEqual(self.post(current).status_code, 409)
            self.assertEqual(self.post(next_notice).status_code, 200)
        self.assertEqual(set(ReleaseNoticeAcknowledgement.objects.filter(user=self.user).values_list('release_key', flat=True)), {'a'*40, 'b'*40})

    def test_database_failure_never_claims_saved_or_leaks_provider_detail(self):
        current = self.notice()
        with patch('core.release_notice.ReleaseNoticeAcknowledgement.objects.get_or_create',
                   side_effect=OperationalError('PRIVATE-PROVIDER-DETAIL-SENTINEL')):
            response = self.post(current)
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()['ok'])
        self.assertNotIn('PRIVATE-PROVIDER-DETAIL-SENTINEL', response.content.decode())
        self.assertIsNotNone(self.notice())
        self.assertFalse(ReleaseNoticeAcknowledgement.objects.exists())
        with self.assertLogs('core.release_notice', level='WARNING') as logged:
            with patch('core.release_notice.ReleaseNoticeAcknowledgement.objects.filter',
                       side_effect=OperationalError('PRIVATE-PROVIDER-DETAIL-SENTINEL')):
                result = self.client.get(reverse('governance_home'))
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.context['release_notice']['storage_available'])
        self.assertNotIn('PRIVATE-PROVIDER-DETAIL-SENTINEL', '\n'.join(logged.output))

    def test_model_unique_constraint_prevents_duplicate_account_release_rows(self):
        ReleaseNoticeAcknowledgement.objects.create(user=self.user, release_key='a'*40)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ReleaseNoticeAcknowledgement.objects.create(user=self.user, release_key='a'*40)
        ReleaseNoticeAcknowledgement.objects.create(user=self.other, release_key='a'*40)
        self.assertEqual(ReleaseNoticeAcknowledgement.objects.count(), 2)


class ReleaseNoticeRetentionSecurityTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        parent = ROOT/'.local/release-notice-security-tests'
        parent.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(dir=parent)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        build = BUILD.replace("call_command('migrate','core','0060_invitation_email_delivery'",
            "call_command('migrate','core','0062_release_notice_acknowledgement'")
        result = subprocess.run([sys.executable, '-c', build, str(ROOT), str(cls.root),
            '0061_workflow_email_delivery'], capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise AssertionError('Isolated security migration fixture failed: '+result.stderr[-1600:])
        spec = importlib.util.spec_from_file_location('security_notice_retention', ROOT/'deploy/customer/upgrade_fixture.py')
        cls.proof = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.proof)
        cls.before = json.loads((cls.root/'before.json').read_text())

    def fixture_without_new_default_metadata(self):
        target = self.root/(self._testMethodName+'.sqlite3')
        shutil.copyfile(self.root/'target.sqlite3', target)
        with closing(sqlite3.connect(target)) as db, db:
            db.execute("DELETE FROM auth_permission WHERE content_type_id IN "
                "(SELECT id FROM django_content_type WHERE app_label='core' AND model='releasenoticeacknowledgement')")
            db.execute("DELETE FROM django_content_type WHERE app_label='core' AND model='releasenoticeacknowledgement'")
        return target

    def test_missing_migration_cannot_bypass_guard_by_omitting_new_metadata(self):
        target = self.fixture_without_new_default_metadata()
        with closing(sqlite3.connect(target)) as db, db:
            db.execute("DELETE FROM django_migrations WHERE app='core' AND name='0062_release_notice_acknowledgement'")
        with self.assertRaises(ValueError):
            self.proof.assert_retained(self.before, target)

    def test_nonempty_new_preferences_cannot_bypass_guard_by_omitting_new_metadata(self):
        target = self.fixture_without_new_default_metadata()
        with closing(sqlite3.connect(target)) as db, db:
            db.execute("INSERT INTO core_releasenoticeacknowledgement(release_key,acknowledged_at,user_id) "
                "SELECT 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','2026-11-06',id FROM auth_user LIMIT 1")
        with self.assertRaises(ValueError):
            self.proof.assert_retained(self.before, target)

    def test_extra_new_column_cannot_bypass_guard_by_omitting_new_metadata(self):
        target = self.fixture_without_new_default_metadata()
        with closing(sqlite3.connect(target)) as db, db:
            db.execute('ALTER TABLE core_releasenoticeacknowledgement ADD COLUMN unreviewed TEXT')
        with self.assertRaises(ValueError):
            self.proof.assert_retained(self.before, target)

    def test_old_privilege_rows_remain_protected_even_when_new_metadata_is_omitted(self):
        target = self.fixture_without_new_default_metadata()
        with closing(sqlite3.connect(target)) as db, db:
            db.execute('UPDATE auth_user SET is_superuser=1')
        with self.assertRaises(ValueError):
            self.proof.assert_retained(self.before, target)
