"""Company templates and combined summaries use real saved notification events."""
from datetime import datetime,time,timezone as utc
from unittest.mock import patch
from django.core.exceptions import PermissionDenied,ValidationError
from django.test import TestCase,override_settings
from django.utils import timezone
from . import test_workflow_email as fixtures
from .models import WorkflowEmailDelivery,Project,Company

@override_settings(NOTIFICATION_EMAIL_ENABLED=True,WORKFLOW_NOTIFICATION_EMAIL_ENABLED=True,WORKFLOW_EMAIL_DAILY_ENABLED=True,NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CustomNotificationTests(TestCase):
    setUp=fixtures.WorkflowEmailTests.setUp
    user=fixtures.WorkflowEmailTests.user
    event=fixtures.WorkflowEmailTests.event
    submit=fixtures.WorkflowEmailTests.submit
    model=fixtures.WorkflowEmailTests.model
    def save(self,**data):
        from .custom_notifications import save_settings
        return save_settings(self.admin,self.company,expected_version=0,templates={},combined_daily_enabled=True,daily_time=time(18),timezone_name='Asia/Riyadh',**data)
    def test_template_rejects_lookup_html_header_injection_and_unknown_tokens(self):
        from .custom_notifications import validate_templates
        for value in ['{recipient.__class__}','{unknown}','<script>x</script>','{recipient_name!r}','{recipient_name:100000}']:
            with self.subTest(value=value),self.assertRaises(ValidationError):validate_templates({'submission':{'subject':value,'body':'{default_body}'}})
        with self.assertRaises(ValidationError):validate_templates({'submission':{'subject':'Bad\nBcc: injected','body':'{default_body}'}})
    def test_company_admin_cannot_change_foreign_config_or_stale_version(self):
        from .custom_notifications import save_settings
        config=self.save()
        self.assertEqual(config.version,1)
        with self.assertRaises(PermissionDenied):save_settings(self.admin,self.foreign,expected_version=0,templates={},combined_daily_enabled=False,daily_time=time(18),timezone_name='UTC')
        with self.assertRaises(ValidationError):self.save()
    def test_custom_template_uses_validated_saved_records_and_no_raw_audit_details(self):
        from .custom_notifications import save_settings
        from .workflow_email import _message,_fresh
        save_settings(self.admin,self.company,expected_version=0,templates={'submission':{'subject':'Review {site_id}','body':'Hello {recipient_name}\n{default_body}'}},combined_daily_enabled=False,daily_time=time(18),timezone_name='UTC')
        self.submit()
        delivery=WorkflowEmailDelivery.objects.filter(kind='submission',recipient=self.qa).get()
        subject,body=_message(delivery,*_fresh(delivery))
        self.assertEqual(subject,'Review '+self.c.site_id)
        self.assertIn('Hello mail-qa',body)
        self.assertIn('https://testserver',body)
    def test_end_of_business_day_combines_authorized_projects_once(self):
        from .workflow_email import queue_daily_digests,_message,_fresh
        day=datetime(2026,11,6,15,0,tzinfo=utc.utc)
        # Activation, evidence event and cutoffs share one controlled lifecycle;
        # this cannot start failing merely because the real calendar advances.
        with patch('core.custom_notifications.timezone.now',return_value=day.replace(hour=9)) as clock:
            self.save()
            clock.return_value=day.replace(hour=12)
            self.submit()
            clock.return_value=day.replace(hour=14)
            self.assertEqual(queue_daily_digests(clock.return_value),0)
            clock.return_value=day
            queue_daily_digests(day);queue_daily_digests(day)
            digest=WorkflowEmailDelivery.objects.get(kind='daily_combined',recipient=self.qa)
            self.assertIsNone(digest.project_id)
            subject,body=_message(digest,*_fresh(digest))
            self.assertIn(self.project.name,body)
            self.assertIn('Submission',body)
            self.assertEqual(WorkflowEmailDelivery.objects.filter(kind='daily_combined',recipient=self.qa).count(),1)
    def test_generic_project_business_event_is_queued_without_engineering_acceptance(self):
        from .governance_views import audit
        audit(self.engineer,'project_client_assigned',self.project,client_organization_id=999)
        self.assertTrue(WorkflowEmailDelivery.objects.filter(kind='project_update',recipient=self.admin).exists())
        self.c.refresh_from_db();self.assertEqual(self.c.status,'DRAFT')

class SubjectContractTests(TestCase):
    def test_multiline_body_tokens_and_oversize_expansion_are_rejected_at_save_validation(self):
        from .custom_notifications import validate_templates
        for subject in ('{default_body}','{summary}','{task_url}','{project_name}{project_name}'):
            with self.subTest(subject=subject),self.assertRaises(ValidationError):
                validate_templates({'submission':{'subject':subject,'body':'{default_body}'}})

@override_settings(NOTIFICATION_EMAIL_ENABLED=True,WORKFLOW_NOTIFICATION_EMAIL_ENABLED=True,WORKFLOW_EMAIL_DAILY_ENABLED=True,NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TransportAndRecoveryTests(TestCase):
    setUp=CustomNotificationTests.setUp
    user=CustomNotificationTests.user
    event=CustomNotificationTests.event
    submit=CustomNotificationTests.submit
    model=CustomNotificationTests.model
    save=CustomNotificationTests.save
    def test_repeated_summary_and_multibyte_oversize_templates_rejected(self):
        from .custom_notifications import validate_templates
        for body in ('{summary}{summary}','漢'*11000+'{default_body}'):
            with self.subTest(body=body[:30]),self.assertRaises(ValidationError):
                validate_templates({'daily_combined':{'subject':'Daily report','body':body}})
    def test_offline_worker_catches_last_completed_day_before_next_cutoff(self):
        from .workflow_email import queue_daily_digests
        start=datetime(2026,11,5,9,tzinfo=utc.utc)
        with patch('core.custom_notifications.timezone.now',return_value=start):self.save()
        self.submit()
        WorkflowEmailDelivery.objects.filter(kind='submission').update(created_at=start)
        queue_daily_digests(datetime(2026,11,6,8,tzinfo=utc.utc))
        self.assertTrue(WorkflowEmailDelivery.objects.filter(kind='daily_combined',digest_day=start.date()).exists())
    def test_setting_created_today_does_not_backfill_unrequested_previous_days(self):
        from .workflow_email import queue_daily_digests
        start=datetime(2026,11,6,9,tzinfo=utc.utc)
        with patch('core.custom_notifications.timezone.now',return_value=start):self.save()
        self.submit()
        WorkflowEmailDelivery.objects.filter(kind='submission').update(created_at=start.replace(day=5))
        queue_daily_digests(start)
        self.assertFalse(WorkflowEmailDelivery.objects.filter(kind='daily_combined').exists())

@override_settings(NOTIFICATION_EMAIL_ENABLED=True,WORKFLOW_NOTIFICATION_EMAIL_ENABLED=True,WORKFLOW_EMAIL_DAILY_ENABLED=True,NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CombinedDigestScaleTests(TestCase):
    setUp=CustomNotificationTests.setUp
    user=CustomNotificationTests.user
    event=CustomNotificationTests.event
    submit=CustomNotificationTests.submit
    model=CustomNotificationTests.model
    save=CustomNotificationTests.save
    def test_thousand_distinct_events_are_counted_without_loading_task_payload_per_event(self):
        import hashlib,time as clock
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from .models import GovernanceAudit
        from .workflow_email import queue_daily_digests,_fresh,_message
        day=datetime(2026,11,6,15,tzinfo=utc.utc)
        with patch('core.custom_notifications.timezone.now',return_value=day.replace(hour=9)):self.save()
        self.submit()
        audits=GovernanceAudit.objects.bulk_create([GovernanceAudit(actor=self.engineer,action='survey_submitted',project=self.project,details={'checklist_id':self.c.pk}) for n in range(999)])
        WorkflowEmailDelivery.objects.bulk_create([WorkflowEmailDelivery(dedupe_key=hashlib.sha256(f'audit:{a.pk}:{self.qa.pk}'.encode()).hexdigest(),event_key=f'audit:{a.pk}',kind='submission',project=self.project,company=self.company,checklist=self.c,recipient=self.qa,expected_role='QUALITY_ENGINEER',source_audit=a) for a in audits])
        WorkflowEmailDelivery.objects.filter(kind='submission').update(created_at=day.replace(hour=12),status='accepted')
        queue_daily_digests(day);queue_daily_digests(day)
        digest=WorkflowEmailDelivery.objects.get(kind='daily_combined',recipient=self.qa)
        start=clock.perf_counter()
        with CaptureQueriesContext(connection) as queries:subject,body=_message(digest,*_fresh(digest))
        self.assertIn('Authorized notification events: 1000.',body)
        self.assertLess(len(body.encode('utf-8')),65536)
        self.assertLess(len(queries),45)
        self.assertEqual(WorkflowEmailDelivery.objects.filter(kind='daily_combined',recipient=self.qa).count(),1)
        print(f'Combined digest benchmark: events=1000 queries={len(queries)} body_bytes={len(body.encode("utf-8"))} seconds={clock.perf_counter()-start:.3f}')
        self.qa.profile.company=self.foreign;self.qa.profile.save()
        self.assertIsNone(_fresh(digest))
    def test_many_multibyte_project_groups_report_explicit_shortening_with_all_totals(self):
        from types import SimpleNamespace
        from .workflow_email import queue_daily_digests
        from .custom_notifications import combined_message
        day=datetime(2026,11,6,15,tzinfo=utc.utc)
        with patch('core.custom_notifications.timezone.now',return_value=day.replace(hour=9)):self.save()
        self.submit();WorkflowEmailDelivery.objects.filter(kind='submission').update(created_at=day.replace(hour=12))
        queue_daily_digests(day)
        digest=WorkflowEmailDelivery.objects.get(kind='daily_combined',recipient=self.qa)
        jobs=[SimpleNamespace(project=SimpleNamespace(name='漢'*120+str(n)),kind='submission',status='accepted') for n in range(2000)]
        with patch('core.custom_notifications.authorized_events',return_value=iter(jobs)):subject,body=combined_message(digest,self.qa)
        self.assertIn('Authorized notification events: 2000.',body)
        self.assertIn('Message size limit:',body)
        self.assertIn('All 2000 authorized events',body)
        self.assertLess(len(body.encode('utf-8')),40000)

@override_settings(NOTIFICATION_EMAIL_ENABLED=True,NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',ALLOWED_HOSTS=['testserver'],PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CustomInvitationIntegrationTests(TestCase):
    def test_saved_custom_invitation_always_contains_actual_one_use_link_once(self):
        import uuid,hashlib
        from django.contrib.auth.models import User
        from .models import IndustryCatalog,InvitationEmailDelivery,GovernanceAudit
        from .onboarding_service import apply_application,review_application,provision_application,invite_application
        from .custom_notifications import save_settings
        from .invitation_email import process_next_email
        owner=User.objects.create_superuser('custom-invite-owner','owner@example.test','fixture')
        app=apply_application(owner,request_key=uuid.uuid4(),name='Custom invite fixture',email='invitee@example.test',industry=IndustryCatalog.objects.get(code='telecom'))
        review_application(owner,app.pk,approve=True);app=provision_application(owner,app.pk)
        save_settings(owner,app.company,expected_version=0,templates={'invitation':{'subject':'Welcome {company_name}','body':'Join our team.'}},combined_daily_enabled=False,daily_time=time(18),timezone_name='UTC')
        app,token=invite_application(owner,app.pk)
        with patch('core.invitation_email.GraphMailClient') as graph:
            self.assertTrue(process_next_email());self.assertFalse(process_next_email())
        graph.return_value.send.assert_called_once()
        email,subject,body=graph.return_value.send.call_args.args
        self.assertEqual(subject,'Welcome Custom invite fixture')
        self.assertIn('/governance/invite/'+token+'/',body)
        self.assertEqual(body.count(token),1)
        self.assertNotIn(token,str(list(GovernanceAudit.objects.values_list('details',flat=True))))
        self.assertEqual(InvitationEmailDelivery.objects.get().status,'accepted')

@override_settings(NOTIFICATION_EMAIL_ENABLED=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class NotificationSettingsIntegrationTests(TestCase):
    setUp=CustomNotificationTests.setUp
    user=CustomNotificationTests.user
    def test_saved_form_configuration_retains_message_errors_and_versions(self):
        from django.urls import reverse
        from .models import CompanyNotificationSettings
        self.client.force_login(self.admin)
        url=reverse('notification_settings_company',args=[self.company.pk])
        response=self.client.get(url);self.assertEqual(response.status_code,200)
        data={'version':0,'kind':'submission','subject':'Review {site_id}','body':'{default_body}','combined_daily_enabled':'on','daily_time':'18:00','timezone_name':'Asia/Karachi'}
        response=self.client.post(url,data);self.assertEqual(response.status_code,302)
        config=CompanyNotificationSettings.objects.get(company=self.company)
        self.assertEqual(config.timezone_name,'Asia/Karachi');self.assertEqual(config.templates['submission']['subject'],'Review {site_id}')
        stale=self.client.post(url,data);self.assertEqual(stale.status_code,409);self.assertContains(stale,'Review {site_id}',status_code=409)
        data['version']=config.version;data['timezone_name']='Not/AZone'
        invalid=self.client.post(url,data);self.assertEqual(invalid.status_code,400)
        self.assertContains(invalid,'Not/AZone',status_code=400)
        config.refresh_from_db();self.assertEqual(config.timezone_name,'Asia/Karachi')
        self.assertFalse(WorkflowEmailDelivery.objects.exists())

class CombinedTemplateCompletenessTests(TestCase):
    def test_combined_template_cannot_remove_the_actual_report(self):
        from .custom_notifications import validate_templates
        for body in ('Hello','{{summary}}'):
            with self.subTest(body=body),self.assertRaises(ValidationError):validate_templates({'daily_combined':{'subject':'Daily report','body':body}})

@override_settings(NOTIFICATION_EMAIL_ENABLED=True,WORKFLOW_NOTIFICATION_EMAIL_ENABLED=True,WORKFLOW_EMAIL_DAILY_ENABLED=True,NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MultiDayDigestRecoveryTests(TestCase):
    setUp=CustomNotificationTests.setUp
    user=CustomNotificationTests.user
    event=CustomNotificationTests.event
    submit=CustomNotificationTests.submit
    model=CustomNotificationTests.model
    save=CustomNotificationTests.save
    def prepare(self):
        activated=datetime(2026,11,2,9,tzinfo=utc.utc)
        with patch('core.custom_notifications.timezone.now',return_value=activated):self.save()
        self.submit()
        for _ in range(3):self.event('survey_submitted')
        for day,job in zip(range(2,6),WorkflowEmailDelivery.objects.filter(kind='submission').order_by('created_at')):
            WorkflowEmailDelivery.objects.filter(pk=job.pk).update(created_at=activated.replace(day=day,hour=12))
    def test_bounded_restart_catchup_retains_each_day_and_no_duplicates(self):
        from .models import CompanyNotificationSettings
        from .workflow_email import queue_daily_digests,_fresh,_message
        self.prepare();instant=datetime(2026,11,6,8,tzinfo=utc.utc)
        queue_daily_digests(instant)
        self.assertEqual(WorkflowEmailDelivery.objects.filter(kind='daily_combined').count(),3)
        self.assertEqual(CompanyNotificationSettings.objects.get(company=self.company).last_digest_day.day,4)
        queue_daily_digests(instant);queue_daily_digests(instant)
        digests=WorkflowEmailDelivery.objects.filter(kind='daily_combined').order_by('digest_day')
        self.assertEqual([row.digest_day.day for row in digests],[2,3,4,5])
        for delivery in digests:self.assertIn('Authorized notification events: 1.',_message(delivery,*_fresh(delivery))[1])
    def test_failed_queue_transaction_does_not_advance_saved_day(self):
        from .models import CompanyNotificationSettings
        from .workflow_email import queue_daily_digests
        self.prepare();instant=datetime(2026,11,6,8,tzinfo=utc.utc)
        with patch('core.workflow_email._audit',side_effect=RuntimeError('Controlled transactional failure')):
            with self.assertRaises(RuntimeError):queue_daily_digests(instant)
        self.assertIsNone(CompanyNotificationSettings.objects.get(company=self.company).last_digest_day)
        self.assertIsNone(CompanyNotificationSettings.objects.get(company=self.company).last_digest_end)
        self.assertFalse(WorkflowEmailDelivery.objects.filter(kind='daily_combined').exists())
        queue_daily_digests(instant)
        self.assertEqual(WorkflowEmailDelivery.objects.filter(kind='daily_combined').count(),3)

@override_settings(NOTIFICATION_EMAIL_ENABLED=True,WORKFLOW_NOTIFICATION_EMAIL_ENABLED=True,WORKFLOW_EMAIL_DAILY_ENABLED=True,NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CompanyNotificationEventTests(TestCase):
    setUp=CustomNotificationTests.setUp
    user=CustomNotificationTests.user
    event=CustomNotificationTests.event
    submit=CustomNotificationTests.submit
    model=CustomNotificationTests.model
    save=CustomNotificationTests.save
    def test_company_only_client_event_is_bound_to_saved_company(self):
        from .models import ClientOrganization,GovernanceAudit
        from .workflow_email import _fresh,_message,queue_audit_event
        client=ClientOrganization.objects.create(name='Local client',company=self.company,industry=self.industry,created_by=self.admin)
        event=GovernanceAudit.objects.create(action='client_organization_created',actor=self.admin,details={'company_id':self.company.pk,'client_organization_id':client.pk})
        job=WorkflowEmailDelivery.objects.get(kind='company_update',recipient=self.admin)
        queue_audit_event(event)
        self.assertEqual(WorkflowEmailDelivery.objects.filter(source_audit=event).count(),1)
        self.assertIsNone(job.project_id)
        self.assertIn(self.company.name,_message(job,*_fresh(job))[1])
        ClientOrganization.objects.filter(pk=client.pk).update(company=self.foreign)
        self.assertIsNone(_fresh(job))
    def test_registered_users_own_invitation_is_in_combined_report_without_bearer(self):
        from .models import ProjectInvitation,InvitationEmailDelivery
        from .workflow_email import queue_daily_digests,_fresh,_message
        from datetime import timedelta
        day=datetime(2026,11,6,15,tzinfo=utc.utc)
        with patch('core.custom_notifications.timezone.now',return_value=day.replace(hour=9)):self.save()
        invitation=ProjectInvitation.objects.create(company=self.company,project=self.project,email=self.engineer.email,role='ENGINEER',accepted_by=self.engineer,accepted_at=day,expires_at=day+timedelta(days=1),token_hash='a'*64)
        row=InvitationEmailDelivery.objects.create(invitation=invitation,status='accepted')
        InvitationEmailDelivery.objects.filter(pk=row.pk).update(created_at=day.replace(hour=12))
        queue_daily_digests(day)
        digest=WorkflowEmailDelivery.objects.get(kind='daily_combined',recipient=self.engineer)
        body=_message(digest,*_fresh(digest))[1]
        self.assertIn('Account invitation',body)
        self.assertIn('Authorized notification events: 1.',body)
        self.assertNotIn('/governance/invite/',body)
        self.assertNotIn('a'*64,body)

@override_settings(NOTIFICATION_EMAIL_ENABLED=True,WORKFLOW_NOTIFICATION_EMAIL_ENABLED=True,WORKFLOW_EMAIL_DAILY_ENABLED=True,NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class NotificationScheduleBoundaryTests(TestCase):
    setUp=CustomNotificationTests.setUp
    user=CustomNotificationTests.user
    event=CustomNotificationTests.event
    submit=CustomNotificationTests.submit
    model=CustomNotificationTests.model
    def transition(self,first_zone,next_zone,first_time=time(18),next_time=time(18)):
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        from .custom_notifications import save_settings,delivery_window
        from .workflow_email import queue_daily_digests,_message,_fresh
        day=datetime(2026,11,1,0,tzinfo=utc.utc)
        with patch('core.custom_notifications.timezone.now',return_value=day):
            config=save_settings(self.admin,self.company,expected_version=0,templates={},combined_daily_enabled=True,daily_time=first_time,timezone_name=first_zone)
        old_end=datetime.combine(day.date(),first_time,tzinfo=ZoneInfo(first_zone)).astimezone(utc.utc)
        new_end=datetime.combine(day.date(),next_time,tzinfo=ZoneInfo(next_zone)).astimezone(utc.utc)
        middle=min(old_end,new_end)+(max(old_end,new_end)-min(old_end,new_end))/2
        source_times=[min(old_end,new_end)-timedelta(hours=1),middle,min(old_end,new_end)+timedelta(days=1,hours=-1)]
        self.submit();self.event('survey_submitted');self.event('survey_submitted')
        for instant,job in zip(source_times,WorkflowEmailDelivery.objects.filter(kind='submission').order_by('created_at','pk')):
            WorkflowEmailDelivery.objects.filter(pk=job.pk).update(created_at=instant,status='accepted')
        queue_daily_digests(day.replace(hour=20))
        first=WorkflowEmailDelivery.objects.get(kind='daily_combined',digest_day=day.date(),recipient=self.qa)
        first_key=first.event_key
        WorkflowEmailDelivery.objects.filter(pk=first.pk).update(status='accepted')
        config.refresh_from_db()
        with patch('core.custom_notifications.timezone.now',return_value=day.replace(hour=21)):
            save_settings(self.admin,self.company,expected_version=config.version,templates={},combined_daily_enabled=True,daily_time=next_time,timezone_name=next_zone)
        queue_daily_digests(day.replace(day=2,hour=20));queue_daily_digests(day.replace(day=2,hour=20))
        jobs=list(WorkflowEmailDelivery.objects.filter(kind='daily_combined',recipient=self.qa).order_by('digest_day'))
        windows=[delivery_window(job)[:2] for job in jobs]
        memberships=[sum(int(start<=instant<end) for start,end in windows) for instant in source_times]
        self.assertEqual(memberships,[1,1,1])
        self.assertEqual(len(jobs),2)
        self.assertEqual(windows[0][1],windows[1][0])
        first.refresh_from_db();self.assertEqual(first.event_key,first_key)
        config.refresh_from_db();self.assertEqual(config.last_digest_end,windows[-1][1])
    def test_riyadh_to_karachi_counts_each_event_once(self):self.transition('Asia/Riyadh','Asia/Karachi')
    def test_karachi_to_riyadh_counts_each_event_once(self):self.transition('Asia/Karachi','Asia/Riyadh')
    def test_earlier_daily_cutoff_counts_each_event_once(self):self.transition('UTC','UTC',time(18),time(16))
    def test_later_daily_cutoff_counts_each_event_once(self):self.transition('UTC','UTC',time(16),time(18))
    def test_empty_day_boundary_is_retained_when_schedule_changes(self):
        from .custom_notifications import save_settings,delivery_window
        from .workflow_email import queue_daily_digests
        day=datetime(2026,11,1,0,tzinfo=utc.utc)
        with patch('core.custom_notifications.timezone.now',return_value=day):
            config=save_settings(self.admin,self.company,expected_version=0,templates={},combined_daily_enabled=True,daily_time=time(18),timezone_name='Asia/Riyadh')
        queue_daily_digests(day.replace(hour=20))
        self.assertFalse(WorkflowEmailDelivery.objects.filter(kind='daily_combined').exists())
        config.refresh_from_db();empty_end=config.last_digest_end
        self.assertEqual(empty_end,day.replace(hour=15))
        self.submit();WorkflowEmailDelivery.objects.filter(kind='submission').update(created_at=day.replace(hour=16))
        save_settings(self.admin,self.company,expected_version=config.version,templates={},combined_daily_enabled=True,daily_time=time(18),timezone_name='Asia/Karachi')
        queue_daily_digests(day.replace(day=2,hour=20))
        digest=WorkflowEmailDelivery.objects.get(kind='daily_combined',recipient=self.qa)
        self.assertEqual(delivery_window(digest)[0],empty_end)

class ExtremeNotificationScheduleWindowTests(TestCase):
    def test_valid_iana_offset_and_cutoff_change_can_span_more_than_three_days(self):
        from types import SimpleNamespace
        from zoneinfo import ZoneInfo
        from .custom_notifications import delivery_window
        start=datetime(2026,11,1,0,tzinfo=ZoneInfo('Pacific/Kiritimati'))
        end=datetime(2026,11,2,23,59,tzinfo=ZoneInfo('Etc/GMT+12'))
        delivery=SimpleNamespace(company_id=1,digest_day=end.date(),event_key='combined:1:'+end.date().isoformat()+'|'+start.isoformat()+'|'+end.isoformat()+'|Etc/GMT+12')
        actual_start,actual_end,_=delivery_window(delivery)
        self.assertEqual(actual_end.astimezone(utc.utc)-actual_start.astimezone(utc.utc),end.astimezone(utc.utc)-start.astimezone(utc.utc))
