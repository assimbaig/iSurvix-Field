"""Independent persisted notice behavior with real authentication and sessions."""
import json
from unittest.mock import patch
from django.contrib.auth.models import User
from django.db import OperationalError
from django.test import Client,TestCase,override_settings
from django.urls import reverse
from .models import Profile,ReleaseNoticeAcknowledgement


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False,ISURVIX_RELEASE_ID='a'*40,NOTIFICATION_EMAIL_ENABLED=False,
    WORKFLOW_NOTIFICATION_EMAIL_ENABLED=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentReleaseNoticeQA(TestCase):
    def setUp(self):
        self.first=User.objects.create_user('qa_notice_first',password='Synthetic-notice-QA!')
        self.second=User.objects.create_user('qa_notice_second',password='Synthetic-notice-QA!')
        for user in (self.first,self.second):
            user.profile.role=Profile.Roles.ENGINEER;user.profile.save()
        self.assertTrue(self.client.login(username=self.first.username,password='Synthetic-notice-QA!'))

    def notice(self,client=None):
        response=(client or self.client).get(reverse('governance_home'),follow=True)
        self.assertEqual(response.status_code,200)
        return response.context['release_notice']

    def acknowledge(self,notice,remember=True,client=None,extra=None):
        payload={'release_id':notice['release_id'],'session_nonce':notice['cache_nonce'],'suppress_current':remember}
        if extra:payload.update(extra)
        return (client or self.client).post(reverse('release_notice_acknowledge'),json.dumps(payload),content_type='application/json')

    def test_real_new_login_invalidates_session_only_nonce_without_creating_preference(self):
        first=self.notice();self.assertEqual(self.acknowledge(first,False).status_code,200)
        self.assertIsNone(self.notice())
        self.client.logout();self.assertTrue(self.client.login(username=self.first.username,password='Synthetic-notice-QA!'))
        second=self.notice();self.assertNotEqual(second['cache_nonce'],first['cache_nonce'])
        self.assertEqual(self.acknowledge(first).status_code,409)
        self.assertFalse(ReleaseNoticeAcknowledgement.objects.exists())

    def test_saved_preference_hides_other_device_but_never_another_account_or_release(self):
        current=self.notice();device=Client();self.assertTrue(device.login(username=self.first.username,password='Synthetic-notice-QA!'))
        self.assertIsNotNone(self.notice(device));self.assertEqual(self.acknowledge(current).status_code,200)
        self.assertIsNone(self.notice(device))
        other=Client();self.assertTrue(other.login(username=self.second.username,password='Synthetic-notice-QA!'))
        self.assertIsNotNone(self.notice(other))
        with override_settings(ISURVIX_RELEASE_ID='b'*40):
            upcoming=self.notice(device);self.assertEqual(upcoming['release_id'],'b'*40)
            self.assertEqual(self.acknowledge(upcoming,client=device).status_code,200)
        self.assertEqual(set(ReleaseNoticeAcknowledgement.objects.filter(user=self.first).values_list('release_key',flat=True)),{'a'*40,'b'*40})
        self.assertFalse(ReleaseNoticeAcknowledgement.objects.filter(user=self.second).exists())

    def test_ambiguous_save_failure_remains_unsaved_and_session_only_continuation_works(self):
        current=self.notice()
        with patch('core.release_notice.ReleaseNoticeAcknowledgement.objects.get_or_create',side_effect=OperationalError('PRIVATE-SYNTHETIC-DB-DETAIL')):
            response=self.acknowledge(current)
        self.assertEqual(response.status_code,503)
        self.assertNotIn('PRIVATE-SYNTHETIC-DB-DETAIL',response.content.decode())
        self.assertIsNotNone(self.notice());self.assertFalse(ReleaseNoticeAcknowledgement.objects.exists())
        self.assertEqual(self.acknowledge(current,False).json()['dismissal'],'session_only')
        self.assertIsNone(self.notice());self.assertFalse(ReleaseNoticeAcknowledgement.objects.exists())

    def test_duplicate_json_keys_and_cross_account_payload_never_persist(self):
        current=self.notice();url=reverse('release_notice_acknowledge')
        duplicate='{"release_id":"'+current['release_id']+'","session_nonce":"'+current['cache_nonce']+'","suppress_current":false,"suppress_current":true}'
        self.assertEqual(self.client.post(url,duplicate,content_type='application/json').status_code,400)
        self.assertEqual(self.acknowledge(current,extra={'user_id':self.second.pk}).status_code,400)
        self.assertFalse(ReleaseNoticeAcknowledgement.objects.exists())

    def test_idempotent_stale_tab_choice_cannot_erase_existing_saved_preference(self):
        current=self.notice()
        for _ in range(3):self.assertEqual(self.acknowledge(current).status_code,200)
        self.assertEqual(self.acknowledge(current,False).json()['dismissal'],'remembered')
        self.assertEqual(ReleaseNoticeAcknowledgement.objects.filter(user=self.first,release_key='a'*40).count(),1)

    def test_two_devices_unchecked_race_retains_already_saved_current_preference(self):
        first=self.notice();second_device=Client()
        self.assertTrue(second_device.login(username=self.first.username,password='Synthetic-notice-QA!'))
        second=self.notice(second_device)
        self.assertNotEqual(first['cache_nonce'],second['cache_nonce'])
        self.assertEqual(self.acknowledge(first).status_code,200)
        response=self.acknowledge(second,False,client=second_device)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['dismissal'],'remembered')
        self.assertEqual(ReleaseNoticeAcknowledgement.objects.filter(user=self.first,release_key='a'*40).count(),1)
        self.assertIsNone(self.notice(second_device))
