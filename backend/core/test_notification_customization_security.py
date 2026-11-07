"""Independent AppSec checks with isolated records; no real mail calls."""
from datetime import datetime, time, timezone as utc, date, timedelta
from collections import Counter
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from . import test_workflow_email as fixtures
from .models import Profile, CompanyNotificationSettings, GovernanceAudit, WorkflowEmailDelivery


@override_settings(NOTIFICATION_EMAIL_ENABLED=True, WORKFLOW_NOTIFICATION_EMAIL_ENABLED=True,
 WORKFLOW_EMAIL_DAILY_ENABLED=True, NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',
 PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class NotificationCustomizationSecurityTests(TestCase):
    setUp=fixtures.WorkflowEmailTests.setUp
    user=fixtures.WorkflowEmailTests.user
    event=fixtures.WorkflowEmailTests.event
    submit=fixtures.WorkflowEmailTests.submit

    def config(self, templates=None, zone='UTC'):
        from .custom_notifications import save_settings
        return save_settings(self.admin,self.company,expected_version=0,templates=templates or {},
            combined_daily_enabled=True,daily_time=time(18),timezone_name=zone)

    def test_foreign_company_and_non_admin_cannot_read_or_write_settings(self):
        self.client.force_login(self.admin)
        url=reverse('notification_settings_company',args=[self.foreign.pk])
        self.assertEqual(self.client.get(url).status_code,403)
        self.assertEqual(self.client.post(url,{}).status_code,403)
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.get(reverse('notification_settings_company',args=[self.company.pk])).status_code,403)
        self.assertFalse(CompanyNotificationSettings.objects.exists())

    def test_csrf_and_forged_authority_parameters_cannot_save(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        url=reverse('notification_settings_company',args=[self.company.pk])
        self.assertEqual(client.post(url,{'version':0}).status_code,403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url,{'company':self.foreign.pk,'version':0}).status_code,400)
        self.assertFalse(CompanyNotificationSettings.objects.exists())

    def test_placeholder_language_cannot_lookup_objects_or_inject_headers(self):
        from .custom_notifications import validate_templates
        for value in ('{recipient_name.__class__}','{recipient_name[0]}','{default_body!r}','{summary:>99999999}',
                      '{}','{0}','{task_url}\r\nBcc: attacker@example.test','<img src=x onerror=alert(1)>'):
            with self.subTest(value=value),self.assertRaises(ValidationError):
                validate_templates({'submission':{'subject':value,'body':'{summary}'}})

    def test_audit_contains_digest_not_custom_message_content(self):
        self.config({'submission':{'subject':'SECRET-PRESENTATION','body':'SECRET-BODY {site_id}'}})
        event=GovernanceAudit.objects.get(action='notification_settings.updated')
        self.assertNotIn('SECRET-',str(event.details))
        self.assertIn('templates_sha256',event.details)

    def test_digest_rechecks_role_company_and_project_access(self):
        from .workflow_email import queue_daily_digests,_fresh,_message
        instant=datetime(2026,11,6,19,tzinfo=utc.utc)
        with patch('core.custom_notifications.timezone.now',return_value=instant.replace(hour=9)) as clock:
            self.config()
            clock.return_value=instant.replace(hour=12)
            self.submit()
            clock.return_value=instant
            queue_daily_digests(instant);queue_daily_digests(instant)
            digest=WorkflowEmailDelivery.objects.get(kind='daily_combined',recipient=self.qa)
            self.assertIsNotNone(_fresh(digest))
            self.assertEqual(WorkflowEmailDelivery.objects.filter(kind='daily_combined',recipient=self.qa).count(),1)
            self.qa.profile.project=None;self.qa.profile.save()
            self.assertIsNone(_fresh(digest))
            self.qa.profile.project=self.project;self.qa.profile.role=Profile.Roles.ENGINEER;self.qa.profile.save()
            self.assertIsNone(_fresh(digest))
            self.qa.profile.role=Profile.Roles.QUALITY_ENGINEER;self.qa.profile.company=self.foreign;self.qa.profile.save()
            self.assertIsNone(_fresh(digest))

    def test_dst_windows_have_real_23_and_25_hour_utc_durations(self):
        from .custom_notifications import business_window
        config=CompanyNotificationSettings(timezone_name='America/New_York',daily_time=time(18))
        for day,hours in ((date(2026,3,8),23),(date(2026,11,1),25)):
            start,end=business_window(config,day)
            self.assertEqual((end.astimezone(utc.utc)-start.astimezone(utc.utc)).total_seconds()/3600,hours)

    def digest(self,templates=None):
        from .workflow_email import queue_daily_digests
        instant=datetime(2026,11,6,19,tzinfo=utc.utc)
        with patch('core.custom_notifications.timezone.now',return_value=instant.replace(hour=9)):
            self.config(templates)
        self.c.status='SUBMITTED';self.c.save(update_fields=['status','updated_at'])
        self.event('survey_submitted',private_note='SECRET-AUDIT-DETAIL',authorization='Bearer SECRET-TOKEN')
        WorkflowEmailDelivery.objects.filter(kind='submission').update(created_at=instant.replace(hour=12),status='accepted')
        queue_daily_digests(instant)
        return WorkflowEmailDelivery.objects.get(kind='daily_combined',recipient=self.qa)

    def test_custom_daily_summary_retains_totals_without_raw_audit_fields(self):
        from .workflow_email import _fresh,_message
        digest=self.digest({'daily_combined':{'subject':'Daily report','body':'Company summary\n{summary}'}})
        subject,body=_message(digest,*_fresh(digest))
        self.assertIn('Authorized notification events: 1.',body)
        self.assertIn('All-event totals by action and mail status:',body)
        self.assertIn('Submission | Accepted by mail server | 1',body)
        self.assertNotIn('SECRET-',body)
        self.assertNotIn('Bearer',body)

    def test_digest_before_send_recheck_cancels_after_account_lock(self):
        from .workflow_email import process_next_workflow_email
        digest=self.digest()
        WorkflowEmailDelivery.objects.exclude(pk=digest.pk).update(status='accepted')
        def interrupt(recipient,subject,body,*,before_send):
            self.qa.profile.is_locked=True;self.qa.profile.save()
            return before_send()
        with patch('core.workflow_email.GraphMailClient') as client:
            client.return_value.send.side_effect=interrupt
            self.assertTrue(process_next_workflow_email())
        digest.refresh_from_db()
        self.assertEqual(digest.status,'cancelled')
        self.assertEqual(digest.error_code,'recipient_unavailable')

    def schedule_change(self,origin,destination,first_hour,next_hour):
        from .custom_notifications import save_settings,delivery_window,authorized_events
        from .workflow_email import queue_daily_digests
        first=datetime(2026,11,6,first_hour,tzinfo=utc.utc)
        second=datetime(2026,11,7,next_hour,tzinfo=utc.utc)
        with patch('core.custom_notifications.timezone.now',return_value=first.replace(hour=8)):
            self.config(zone=origin)
        self.c.status='SUBMITTED';self.c.save(update_fields=['status','updated_at'])
        source_ids=[]
        for stamp in (first-timedelta(minutes=30),first+timedelta(minutes=30),second-timedelta(minutes=30),second+timedelta(minutes=30)):
            audit=self.event('survey_submitted')
            job=WorkflowEmailDelivery.objects.get(kind='submission',recipient=self.qa,source_audit=audit)
            WorkflowEmailDelivery.objects.filter(pk=job.pk).update(created_at=stamp,status='accepted')
            source_ids.append(job.pk)
        queue_daily_digests(first+timedelta(minutes=1))
        with patch('core.custom_notifications.timezone.now',return_value=first+timedelta(minutes=2)):
            save_settings(self.admin,self.company,expected_version=1,templates={},combined_daily_enabled=True,daily_time=time(18),timezone_name=destination)
        queue_daily_digests(second+timedelta(minutes=1))
        queue_daily_digests(second+timedelta(days=1,minutes=1))
        queue_daily_digests(second+timedelta(days=1,minutes=1))
        digests=list(WorkflowEmailDelivery.objects.filter(kind='daily_combined',recipient=self.qa).order_by('digest_day'))
        self.assertEqual(len(digests),3)
        windows=[delivery_window(job)[:2] for job in digests]
        self.assertEqual(windows[0][1],windows[1][0])
        self.assertEqual(windows[1][1],windows[2][0])
        observed=Counter(job.pk for start,end in windows for job in authorized_events(self.qa,self.company.pk,start,end))
        self.assertEqual(observed,Counter(source_ids))

    def test_riyadh_to_karachi_cutoff_counts_each_event_once(self):
        self.schedule_change('Asia/Riyadh','Asia/Karachi',15,13)

    def test_karachi_to_riyadh_cutoff_counts_each_event_once(self):
        self.schedule_change('Asia/Karachi','Asia/Riyadh',13,15)

    def test_valid_timezone_and_cutoff_edit_can_exceed_48_hours_without_cancelling_report(self):
        from .custom_notifications import save_settings
        from .workflow_email import queue_daily_digests,_fresh
        first=datetime(2026,11,5,19,tzinfo=utc.utc)
        with patch('core.custom_notifications.timezone.now',return_value=first):
            self.config(zone='Asia/Karachi')
        CompanyNotificationSettings.objects.filter(company=self.company).update(
            daily_time=time(0),last_digest_day=date(2026,11,6),last_digest_end=first)
        save_settings(self.admin,self.company,expected_version=1,templates={},combined_daily_enabled=True,
            daily_time=time(23,59),timezone_name='Asia/Riyadh')
        self.submit()
        WorkflowEmailDelivery.objects.filter(kind='submission').update(created_at=first+timedelta(hours=1),status='accepted')
        queue_daily_digests(datetime(2026,11,7,21,tzinfo=utc.utc))
        digest=WorkflowEmailDelivery.objects.get(kind='daily_combined',recipient=self.qa)
        self.assertIsNotNone(_fresh(digest))
