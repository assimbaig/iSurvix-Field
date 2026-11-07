"""Approved AR-Q1 admission repair; isolated counters and real HTTP requests."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import time
from unittest.mock import patch
from django.contrib.auth.models import User
from django.db import OperationalError,connections
from django.test import Client,TestCase,TransactionTestCase,override_settings
from django.urls import reverse
from django.utils import timezone
from .account_recovery import request_reset,_fingerprint,_email_key,WINDOW,valid_reset,_reset_token
from .account_recovery_models import AccountRecoveryRequest,AccountRecoveryThrottle

CONFIG=dict(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,NOTIFICATION_EMAIL_ENABLED=True,NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',NOTIFICATION_EMAIL_CREDENTIALS_FILE='',ACCOUNT_RECOVERY_TRUST_PROXY_IP=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])

@override_settings(**CONFIG)
class RecoveryAdmissionTests(TestCase):
 def setUp(self):
  self.user=User.objects.create_user('admission-victim',email='admission-victim@example.test',password='Synthetic-Admission-879!')
 def test_distributed_requests_for_limited_account_do_not_spend_global_or_create_ip_keys(self):
  attacker=Client(enforce_csrf_checks=True);victim=Client(enforce_csrf_checks=True);url=reverse('account_password_reset')
  for client in [attacker,victim]:self.assertEqual(client.get(url).status_code,200)
  for number in range(50):
   response=attacker.post(url,{'email':'same-unknown@example.test'},REMOTE_ADDR='127.0.1.'+str(number+1),HTTP_X_CSRFTOKEN=attacker.cookies['csrftoken'].value)
   self.assertEqual(response.status_code,302)
  self.assertEqual(AccountRecoveryThrottle.objects.get(key='global').hits,3)
  self.assertEqual(AccountRecoveryThrottle.objects.count(),5,'Denied new IPs must not create throttle keys after the account budget is exhausted')
  response=victim.post(url,{'email':self.user.email},REMOTE_ADDR='127.0.2.1',HTTP_X_CSRFTOKEN=victim.cookies['csrftoken'].value)
  self.assertEqual(response.status_code,302);self.assertEqual(AccountRecoveryRequest.objects.filter(user=self.user,status='queued').count(),1)
  self.assertEqual(AccountRecoveryThrottle.objects.get(key='global').hits,4)
 def test_global_limit_preserves_bounded_key_cardinality_under_unique_source_flood(self):
  for number in range(150):request_reset('unique-'+str(number)+'@example.test','192.0.2.'+str(number+1))
  self.assertEqual(AccountRecoveryThrottle.objects.get(key='global').hits,100)
  self.assertEqual(AccountRecoveryThrottle.objects.count(),201)
  denied_email='new-after-global@example.test';request_reset(denied_email,'198.51.100.2')
  self.assertEqual(AccountRecoveryThrottle.objects.count(),201)
  self.assertFalse(AccountRecoveryThrottle.objects.filter(key='account:'+_email_key(denied_email)).exists())
 def test_ip_denials_keep_original_window_and_reset_after_expiry_without_losing_history(self):
  start=timezone.now();ip='192.0.2.80';ip_key='ip:'+_fingerprint('ip.v1',ip)
  with patch('core.account_recovery.timezone.now',return_value=start):
   request_reset(self.user.email,ip)
   row=AccountRecoveryRequest.objects.get(user=self.user);old_token=_reset_token(row)
   for number in range(9):request_reset('window-'+str(number)+'@example.test',ip)
  with patch('core.account_recovery.timezone.now',return_value=start+timedelta(minutes=30)):
   request_reset('denied@example.test',ip)
   self.assertEqual(AccountRecoveryThrottle.objects.get(key='global').hits,10)
   self.assertEqual(AccountRecoveryThrottle.objects.get(key=ip_key).window_started_at,start)
  after=start+WINDOW+timedelta(seconds=1)
  with patch('core.account_recovery.timezone.now',return_value=after):
   self.assertIsNone(valid_reset(row.pk,old_token));request_reset(self.user.email,ip)
   for key in ['global',ip_key,'account:'+_email_key(self.user.email)]:
    counter=AccountRecoveryThrottle.objects.get(key=key);self.assertEqual(counter.hits,1);self.assertEqual(counter.window_started_at,after)
  self.assertEqual(AccountRecoveryRequest.objects.filter(user=self.user).count(),2)
 def test_local_denials_do_not_change_generic_http_response_or_direct_call_return(self):
  url=reverse('account_password_reset');client=Client(enforce_csrf_checks=True);client.get(url)
  responses=[]
  for number in range(12):
   r=client.post(url,{'email':self.user.email},REMOTE_ADDR='127.0.0.70',HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value);responses.append((r.status_code,r.url))
  self.assertEqual(len(set(responses)),1);self.assertEqual(AccountRecoveryRequest.objects.filter(user=self.user).count(),3)
  self.assertEqual(AccountRecoveryThrottle.objects.get(key='global').hits,3)
  self.assertIsNone(request_reset(self.user.email,'127.0.0.71'))

@override_settings(**CONFIG)
class ConcurrentRecoveryAdmissionTests(TransactionTestCase):
 def test_concurrent_callers_cannot_overspend_account_or_shared_budget(self):
  user=User.objects.create_user('concurrent-admission',email='concurrent-admission@example.test',password='Synthetic-Admission-721!')
  def request(number):
   try:
    for attempt in range(100):
     try:request_reset(user.email,'198.51.100.'+str(number+1));return
     except OperationalError as error:
      if 'lock' not in str(error).lower():raise
      # SQLite returns transient table contention instead of blocking its shared
      # in-memory test connection. Retry a whole rolled-back request, never an
      # individual counter write or assertion.
      time.sleep(.005)
    raise AssertionError('Concurrent admission did not settle within its bounded retry budget')
   finally:connections.close_all()
  with ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(request,range(15)))
  self.assertEqual(AccountRecoveryRequest.objects.filter(user=user).count(),3)
  self.assertEqual(AccountRecoveryThrottle.objects.get(key='global').hits,3)
  self.assertEqual(AccountRecoveryThrottle.objects.get(key='account:'+_email_key(user.email)).hits,3)
  self.assertEqual(AccountRecoveryThrottle.objects.count(),5)
