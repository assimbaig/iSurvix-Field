"""Per-account, per-release notices use saved preferences and login-bound state."""
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import OperationalError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Company,IndustryCatalog,Profile,Project,ProjectMembership


FIRST='a'*40
NEXT='b'*40


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False,ISURVIX_RELEASE_ID=FIRST,NOTIFICATION_EMAIL_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ReleaseNoticeTests(TestCase):
    def setUp(self):
        self.company=Company.objects.create(name='Synthetic release notice company')
        self.industry=IndustryCatalog.objects.get(code='telecom')
        self.admin=self.person('notice-admin',Profile.Roles.ADMIN)
        self.project=Project.objects.create(name='Synthetic release notice project',company=self.company,
            administrator=self.admin)
        self.roles={Profile.Roles.ADMIN:self.admin}
        ProjectMembership.objects.create(user=self.admin,project=self.project)
        for index,role in enumerate((Profile.Roles.ENGINEER,Profile.Roles.QUALITY_ENGINEER,
                Profile.Roles.TEAM_LEAD,Profile.Roles.CLIENT,Profile.Roles.PROJECT_MANAGER)):
            self.roles[role]=self.person('notice-role-'+str(index),role,self.project)
        owner=self.person('notice-platform-owner',Profile.Roles.SUPER_ADMIN)
        owner.is_superuser=True;owner.is_staff=True;owner.save()
        self.roles[Profile.Roles.SUPER_ADMIN]=owner
        self.other=self.roles[Profile.Roles.ENGINEER]
        self.client.force_login(self.admin)

    def person(self,name,role,project=None):
        user=User.objects.create_user(name,email=name+'@example.test',password='Notice-fixture-294!')
        user.profile.role=role;user.profile.company=self.company;user.profile.project=project
        if role==Profile.Roles.ADMIN:user.profile.admin_industry=self.industry
        user.profile.save()
        if project:ProjectMembership.objects.create(user=user,project=project)
        return user

    def notice(self,client=None):
        response=(client or self.client).get(reverse('governance_home'),follow=True)
        self.assertEqual(response.status_code,200)
        self.assertIn('release_notice',response.context)
        self.assertIsNotNone(response.context['release_notice'])
        return response.context['release_notice']

    def post(self,notice,remember=True,client=None,**overrides):
        body={'release_id':notice['release_id'],'session_nonce':notice['cache_nonce'],'suppress_current':remember}
        body.update(overrides)
        return (client or self.client).post(reverse('release_notice_acknowledge'),
            json.dumps(body),content_type='application/json')

    def test_first_login_all_existing_roles_receive_current_deployed_release(self):
        for role,actor in self.roles.items():
            with self.subTest(role=role):
                browser=Client();browser.force_login(actor)
                data=self.notice(browser)
                self.assertEqual(data['release_id'],FIRST)
                self.assertEqual(data['ack_url'],reverse('release_notice_acknowledge'))
                self.assertTrue(data['changes'])
                self.assertNotIn(str(browser.session.session_key),json.dumps(data))
                self.assertNotIn('user_id',data)

    def test_remembered_choice_persists_for_account_across_refresh_login_and_devices(self):
        from .models import ReleaseNoticeAcknowledgement
        data=self.notice()
        response=self.post(data)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['dismissal'],'remembered')
        self.assertEqual(ReleaseNoticeAcknowledgement.objects.filter(user=self.admin,release_key=FIRST).count(),1)
        self.assertIsNone(self.client.get(reverse('governance_home')).context['release_notice'])
        self.client.logout();self.client.force_login(self.admin)
        self.assertIsNone(self.client.get(reverse('governance_home')).context['release_notice'])
        second=Client();second.force_login(self.admin)
        self.assertIsNone(second.get(reverse('governance_home')).context['release_notice'])

    def test_unchecked_choice_applies_only_to_current_login_and_new_login_has_new_nonce(self):
        from .models import ReleaseNoticeAcknowledgement
        data=self.notice()
        self.assertEqual(self.post(data,False).json()['dismissal'],'session_only')
        self.assertEqual(ReleaseNoticeAcknowledgement.objects.count(),0)
        self.assertIsNone(self.client.get(reverse('governance_home')).context['release_notice'])
        self.client.logout();self.client.force_login(self.admin)
        fresh=self.notice()
        self.assertNotEqual(fresh['cache_nonce'],data['cache_nonce'])
        self.assertNotEqual(fresh['actor_key'],data['actor_key'])

    def test_future_deployed_release_reappears_without_changing_older_acknowledgement(self):
        from .models import ReleaseNoticeAcknowledgement
        data=self.notice();self.assertEqual(self.post(data).status_code,200)
        with override_settings(ISURVIX_RELEASE_ID=NEXT):
            fresh=self.notice()
            self.assertEqual(fresh['release_id'],NEXT)
            self.assertNotEqual(data['cache_nonce'],fresh['cache_nonce'])
            self.assertEqual(self.post(fresh).status_code,200)
        self.assertEqual(set(ReleaseNoticeAcknowledgement.objects.values_list('release_key',flat=True)),{FIRST,NEXT})

    def test_duplicate_posts_are_idempotent_and_session_only_never_erases_saved_choice(self):
        from .models import ReleaseNoticeAcknowledgement
        data=self.notice()
        for _ in range(3):self.assertEqual(self.post(data).status_code,200)
        self.assertEqual(ReleaseNoticeAcknowledgement.objects.count(),1)
        response=self.post(data,False)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['dismissal'],'remembered')
        self.assertEqual(ReleaseNoticeAcknowledgement.objects.count(),1)

    def test_release_and_login_mismatches_do_not_acknowledge_other_contexts(self):
        from .models import ReleaseNoticeAcknowledgement
        data=self.notice()
        with override_settings(ISURVIX_RELEASE_ID=NEXT):
            response=self.post(data)
            self.assertEqual(response.status_code,409)
            self.assertEqual(response.json()['code'],'release_changed')
        self.client.logout();self.client.force_login(self.admin)
        fresh=self.notice()
        response=self.post(data)
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.json()['code'],'session_changed')
        self.assertEqual(ReleaseNoticeAcknowledgement.objects.count(),0)
        self.assertEqual(self.post(fresh).status_code,200)

    def test_account_switch_and_injected_user_cannot_change_foreign_preferences(self):
        from .models import ReleaseNoticeAcknowledgement
        old=self.notice();self.client.logout();self.client.force_login(self.other)
        fresh=self.notice()
        self.assertEqual(self.post(old).status_code,409)
        self.assertEqual(self.post(fresh,user_id=self.admin.pk).status_code,400)
        self.assertEqual(ReleaseNoticeAcknowledgement.objects.count(),0)
        self.assertEqual(self.post(fresh).status_code,200)
        self.assertFalse(ReleaseNoticeAcknowledgement.objects.filter(user=self.admin).exists())
        self.assertTrue(ReleaseNoticeAcknowledgement.objects.filter(user=self.other).exists())

    def test_csrf_and_authentication_are_required_and_get_cannot_mutate(self):
        from .models import ReleaseNoticeAcknowledgement
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.admin)
        data=self.notice(strict)
        self.assertEqual(self.post(data,client=strict).status_code,403)
        self.assertIn(Client().post(reverse('release_notice_acknowledge')).status_code,(302,401,403))
        self.assertEqual(self.client.get(reverse('release_notice_acknowledge')).status_code,405)
        self.assertEqual(ReleaseNoticeAcknowledgement.objects.count(),0)
        self.assertEqual(Client().get(reverse('login')).context.get('release_notice'),None)

    def test_invalid_payloads_do_not_create_preferences(self):
        from .models import ReleaseNoticeAcknowledgement
        data=self.notice()
        for body in (None,[],{}, {'release_id':FIRST,'session_nonce':data['cache_nonce'],'suppress_current':'true'},
                {'release_id':'x'*5000,'session_nonce':data['cache_nonce'],'suppress_current':True}):
            with self.subTest(body_type=type(body).__name__):
                response=self.client.post(reverse('release_notice_acknowledge'),json.dumps(body),content_type='application/json')
                self.assertEqual(response.status_code,400)
        self.assertEqual(ReleaseNoticeAcknowledgement.objects.count(),0)

    def test_save_failure_is_honest_retryable_and_leaves_notice_available(self):
        from .models import ReleaseNoticeAcknowledgement
        data=self.notice()
        with patch('core.release_notice.ReleaseNoticeAcknowledgement.objects.get_or_create',side_effect=OperationalError('private database detail')):
            response=self.post(data)
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['code'],'save_unavailable')
        self.assertNotContains(response,'private database detail',status_code=503)
        self.assertEqual(ReleaseNoticeAcknowledgement.objects.count(),0)
        self.assertEqual(self.notice()['cache_nonce'],data['cache_nonce'])
        self.assertEqual(self.post(data).status_code,200)

    def test_local_fallback_is_stable_and_uses_no_git_or_network_process(self):
        with override_settings(ISURVIX_RELEASE_ID='unknown'),patch('subprocess.run',side_effect=AssertionError('No Git process')):
            first=self.notice()
            self.assertEqual(first['release_id'],'local-account-recovery-exports-v1-3-1-beta')
            self.assertEqual(self.notice()['release_id'],first['release_id'])
            self.assertEqual(self.notice()['cache_nonce'],first['cache_nonce'])

    def test_anonymous_pages_do_not_query_release_preferences_or_show_notice(self):
        browser=Client()
        response=browser.get(reverse('login'))
        self.assertEqual(response.status_code,200)
        self.assertIsNone(response.context.get('release_notice'))
        self.assertNotContains(response,'What\'s new in iField')

    def test_locked_or_inactive_accounts_cannot_acknowledge_from_an_old_page(self):
        from .models import ReleaseNoticeAcknowledgement
        data=self.notice()
        Profile.objects.filter(user=self.admin).update(is_locked=True)
        self.assertEqual(self.post(data).status_code,403)
        Profile.objects.filter(user=self.admin).update(is_locked=False)
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        self.assertIn(self.post(data).status_code,(302,401,403))
        self.assertEqual(ReleaseNoticeAcknowledgement.objects.count(),0)

    def test_unavailable_preference_storage_does_not_break_the_application_page(self):
        with patch('core.release_notice.ReleaseNoticeAcknowledgement.objects.filter',side_effect=OperationalError('private storage detail')):
            response=self.client.get(reverse('governance_home'))
        self.assertEqual(response.status_code,200)
        self.assertIsNotNone(response.context['release_notice'])
        self.assertFalse(response.context['release_notice']['storage_available'])
        self.assertNotContains(response,'private storage detail')

    def test_optional_notice_account_lookup_failure_does_not_break_review_or_claim_saved(self):
        data=self.notice()
        self.client.raise_request_exception=False
        with patch('core.release_notice.role_for',side_effect=OperationalError('Synthetic account lookup unavailable')):
            response=self.client.get(reverse('governance_home'))
            failed=self.post(data)
        self.assertEqual(response.status_code,200)
        self.assertIsNone(response.context['release_notice'])
        self.assertEqual(failed.status_code,503)
        self.assertEqual(failed.json()['code'],'save_unavailable')

    def test_new_login_event_clears_session_only_choice_even_for_same_account(self):
        data=self.notice();self.assertEqual(self.post(data,False).status_code,200)
        self.client.force_login(self.admin)
        self.assertNotEqual(self.notice()['cache_nonce'],data['cache_nonce'])

    def test_notices_do_not_change_engineering_records_or_audit_history(self):
        from .models import Checklist,GovernanceAudit
        checklist=Checklist.objects.create(user=self.other,project=self.project,site_id='NOTICE-PRESERVE',
            status=Checklist.Status.FINAL,answer_data={'stable-field':'Recorded value'},
            section_approvals={'existing':{'decision':'approved'}})
        before=Checklist.objects.filter(pk=checklist.pk).values().get()
        audits=GovernanceAudit.objects.count()
        self.assertEqual(self.post(self.notice()).status_code,200)
        self.assertEqual(Checklist.objects.filter(pk=checklist.pk).values().get(),before)
        self.assertEqual(GovernanceAudit.objects.count(),audits)

    @override_settings(ROOT_URLCONF='core.test_superadmin_admin')
    def test_optional_context_without_ack_route_reads_no_preferences_or_changes_session(self):
        from django.test import RequestFactory
        from .release_notice import release_notice_context
        request=RequestFactory().get('/admin/');request.user=self.admin
        request.session=self.client.session
        original=dict(request.session);request.session.modified=False
        with self.assertNumQueries(0):
            result=release_notice_context(request)
        self.assertEqual(result,{'release_notice':None})
        self.assertEqual(dict(request.session),original)
        self.assertFalse(request.session.modified)
