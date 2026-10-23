"""Wrong passwords cannot permanently lock the only global administrator."""
import copy
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth.models import User
from django.db import connection,connections,OperationalError
from django.db.migrations.executor import MigrationExecutor
from django.test import Client,TestCase,override_settings
from django.urls import reverse
from django.utils import timezone
from .account_views import record_failed_login
from .models import Profile


@override_settings(ROOT_URLCONF='checklist.urls',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],LOGIN_FAILURE_LIMIT=5,LOGIN_LOCKOUT_SECONDS=900)
class LoginThrottleTests(TestCase):
    def setUp(self):
        self.password='Synthetic-administrator-password-489!'
        self.user=User.objects.create_user('only_global_admin',password=self.password,is_superuser=True,is_staff=True)
        self.user.profile.role=Profile.Roles.SUPER_ADMIN;self.user.profile.save()
        self.now=timezone.now()
        self.browser=Client(enforce_csrf_checks=True)
        self.browser.get(reverse('login'))

    def attempt(self,password='wrong',now=None,username=None):
        with patch('core.account_views.timezone.now',return_value=now or self.now):
            return self.browser.post(reverse('login'),{'username':username or self.user.username,'password':password,
                'csrfmiddlewaretoken':self.browser.cookies['csrftoken'].value})

    def profile(self):
        self.user.profile.refresh_from_db()
        return self.user.profile

    def test_five_anonymous_csrf_valid_failures_cannot_permanently_lock_sole_super_admin(self):
        for attempt in range(5):
            response=self.attempt()
            self.assertEqual(response.status_code,200)
            self.assertEqual(self.profile().failed_attempts,attempt+1)
            self.assertFalse(self.profile().is_locked)
            self.assertNotIn('_auth_user_id',self.browser.session)
        deadline=self.profile().login_locked_until
        self.assertEqual(deadline,self.now+timedelta(minutes=15))
        for password in ['wrong',self.password]:
            self.assertEqual(self.attempt(password,now=self.now+timedelta(minutes=1)).status_code,200)
            self.assertNotIn('_auth_user_id',self.browser.session)
            self.assertEqual(self.profile().login_locked_until,deadline)
            self.assertEqual(self.profile().failed_attempts,5)
        response=self.attempt(self.password,now=deadline+timedelta(seconds=1))
        self.assertEqual(response.status_code,302)
        self.assertEqual(int(self.browser.session['_auth_user_id']),self.user.pk)
        self.assertEqual(self.profile().failed_attempts,0)
        self.assertIsNone(self.profile().login_locked_until)
        self.user.refresh_from_db();self.assertTrue(self.user.is_superuser and self.user.is_staff)

    def test_expired_window_wrong_password_starts_a_fresh_counter(self):
        for unused in range(5):self.attempt()
        deadline=self.profile().login_locked_until
        self.attempt(now=deadline+timedelta(seconds=1))
        self.assertEqual(self.profile().failed_attempts,1)
        self.assertIsNone(self.profile().login_locked_until)
        self.assertFalse(self.profile().is_locked)

    def test_success_before_threshold_clears_failures_and_ignores_forged_role(self):
        for unused in range(4):self.attempt()
        self.user.is_superuser=False;self.user.is_staff=False;self.user.save()
        self.user.profile.role=Profile.Roles.ADMIN;self.user.profile.save()
        response=self.browser.post(reverse('login'),{'username':self.user.username,'password':self.password,
            'role':'SUPER_ADMIN','csrfmiddlewaretoken':self.browser.cookies['csrftoken'].value})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.profile().failed_attempts,0)
        self.user.refresh_from_db();self.assertFalse(self.user.is_superuser or self.user.is_staff)

    def test_manual_or_historical_locks_remain_locked_with_generic_errors(self):
        self.user.profile.is_locked=True;self.user.profile.failed_attempts=5
        self.user.profile.login_locked_until=self.now-timedelta(days=1)
        self.user.profile.save()
        unknown=self.attempt(username='does_not_exist').context['form'].non_field_errors()
        for password in ['wrong',self.password]:
            response=self.attempt(password,now=self.now+timedelta(days=1))
            self.assertEqual(list(response.context['form'].non_field_errors()),list(unknown))
            self.assertNotIn('_auth_user_id',self.browser.session)
            self.assertTrue(self.profile().is_locked)
            self.assertEqual(self.profile().failed_attempts,5)

    @override_settings(LOGIN_FAILURE_LIMIT=3,LOGIN_LOCKOUT_SECONDS=60)
    def test_configurable_limit_window_and_counter_saturation(self):
        for unused in range(9):self.attempt()
        self.assertEqual(self.profile().failed_attempts,3)
        self.assertEqual(self.profile().login_locked_until,self.now+timedelta(seconds=60))

    def test_csrf_rejection_and_database_contention_do_not_mutate_or_authenticate(self):
        self.assertEqual(self.browser.post(reverse('login'),{'username':self.user.username,'password':'wrong'}).status_code,403)
        self.assertEqual(self.profile().failed_attempts,0)
        with patch('core.account_views.record_failed_login',side_effect=OperationalError('synthetic busy')):
            response=self.attempt()
        self.assertEqual(response.status_code,503)
        self.assertEqual(response['Retry-After'],'1')
        self.assertEqual(self.profile().failed_attempts,0)
        self.assertNotIn('_auth_user_id',self.browser.session)


class LoginThrottleConcurrentTests(unittest.TestCase):
    def test_concurrent_sqlite_failures_are_counted_once_and_deadline_is_not_extended(self):
        alias='login_concurrency_'+uuid.uuid4().hex
        with tempfile.TemporaryDirectory(prefix='ifield-login-concurrency-') as directory:
            config=copy.deepcopy(connection.settings_dict)
            config['NAME']=str(Path(directory)/'login.sqlite3')
            config['OPTIONS']={**config.get('OPTIONS',{}),'timeout':10}
            connections.databases[alias]=config
            database=connections[alias]
            try:
                executor=MigrationExecutor(database)
                executor.migrate([('core','0052_temporary_login_throttle')])
                historical=executor.loader.project_state([('core','0052_temporary_login_throttle')]).apps
                u=historical.get_model('auth','User').objects.using(alias).create(username='concurrent_admin',is_active=True)
                historical.get_model('core','Profile').objects.using(alias).create(user_id=u.pk,role='ADMIN')
                moment=timezone.now()
                manager=Profile.objects.db_manager(alias)
                def failure(unused):
                    try:record_failed_login('concurrent_admin',now=moment)
                    finally:connections[alias].close()
                with patch.object(Profile,'objects',manager),override_settings(LOGIN_FAILURE_LIMIT=5,LOGIN_LOCKOUT_SECONDS=900):
                    with ThreadPoolExecutor(max_workers=8) as workers:list(workers.map(failure,range(8)))
                    row=Profile.objects.get(user_id=u.pk)
                    self.assertEqual(row.failed_attempts,5)
                    self.assertEqual(row.login_locked_until,moment+timedelta(minutes=15))
                    self.assertFalse(row.is_locked)
                    record_failed_login('concurrent_admin',now=moment+timedelta(minutes=2))
                    row.refresh_from_db()
                    self.assertEqual(row.failed_attempts,5)
                    self.assertEqual(row.login_locked_until,moment+timedelta(minutes=15))
            finally:
                database.close()
                del connections[alias]
                connections.databases.pop(alias,None)
