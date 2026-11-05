"""Saved workflow events, scoped recipients and durable notification recovery."""
from datetime import datetime, timedelta, timezone as utc
from io import StringIO
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import transaction
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Checklist, Company, GovernanceAudit, IndustryCatalog, Profile, Project, WorkAssignment
from .notification_email import NotificationEmailError


@override_settings(NOTIFICATION_EMAIL_ENABLED=True, WORKFLOW_NOTIFICATION_EMAIL_ENABLED=True,
    WORKFLOW_EMAIL_DAILY_ENABLED=True, WORKFLOW_EMAIL_DAILY_HOUR=15,
    NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver', ALLOWED_HOSTS=['testserver'],
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class WorkflowEmailTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Synthetic notification company')
        self.foreign = Company.objects.create(name='Synthetic foreign notification company')
        self.industry = IndustryCatalog.objects.get_or_create(code='telecom', defaults={'name': 'Telecom'})[0]
        self.admin = self.user('mail-admin', Profile.Roles.ADMIN)
        self.project = Project.objects.create(name='Synthetic notification project', company=self.company, administrator=self.admin)
        self.admin.profile.project = self.project; self.admin.profile.save()
        self.engineer = self.user('mail-engineer', Profile.Roles.ENGINEER)
        self.qa = self.user('mail-qa', Profile.Roles.QUALITY_ENGINEER)
        self.lead = self.user('mail-lead', Profile.Roles.TEAM_LEAD)
        self.customer = self.user('mail-client', Profile.Roles.CLIENT)
        self.c = Checklist.objects.create(project=self.project, user=self.engineer, site_id='SYNTHETIC-WF-1', quality_reviewer=self.qa,
            schema_snapshot={'title': 'Synthetic', 'sections': [{'id': 'civil', 'title': 'Civil', 'fields': []}]})

    def user(self, name, role):
        user = User.objects.create_user(name, email=name + '@example.test')
        profile = user.profile; profile.company = self.company; profile.role = role
        profile.admin_industry = self.industry if role == Profile.Roles.ADMIN else None
        profile.project = getattr(self, 'project', None); profile.save()
        return user

    def model(self):
        from .models import WorkflowEmailDelivery
        return WorkflowEmailDelivery

    def event(self, action, actor=None, **details):
        from .governance_views import audit
        return audit(actor or self.engineer, action, self.project, checklist_id=self.c.pk, **details)

    def submit(self):
        self.c.status = Checklist.Status.SUBMITTED; self.c.save(update_fields=['status', 'updated_at'])
        return self.event('survey_submitted')

    def test_actual_submission_endpoint_queues_qa_without_network(self):
        self.client.force_login(self.engineer)
        with patch('core.workflow_email.GraphMailClient', side_effect=AssertionError('Request must not send email')):
            response = self.client.post(reverse('custom_checklist_submit', args=[self.c.pk]))
        self.assertEqual(response.status_code, 302)
        self.c.refresh_from_db(); self.assertEqual(self.c.status, Checklist.Status.SUBMITTED)
        self.assertTrue(self.model().objects.filter(kind='submission', recipient=self.qa, status='queued').exists())

    def test_repeated_queue_for_same_saved_event_has_one_delivery_per_recipient(self):
        from .workflow_email import queue_audit_event
        event = self.submit()
        count = self.model().objects.count()
        queue_audit_event(event); queue_audit_event(event)
        self.assertEqual(self.model().objects.count(), count)
        self.assertEqual(self.model().objects.filter(source_audit=event, recipient=self.qa).count(), 1)

    def test_rolled_back_action_has_no_saved_notification(self):
        try:
            with transaction.atomic():
                self.submit()
                raise ValueError('Synthetic failed action')
        except ValueError:
            pass
        self.assertEqual(self.model().objects.count(), 0)
        self.assertFalse(GovernanceAudit.objects.filter(action='survey_submitted').exists())

    def test_assignment_notifies_assigned_engineer_once(self):
        work = WorkAssignment.objects.create(project=self.project, checklist=self.c, assigned_to=self.engineer,
            assigned_by=self.lead, site_id=self.c.site_id, latitude=0, longitude=0, description='Synthetic task')
        self.event('task_assigned', actor=self.lead, assignment_id=work.pk, engineer_id=self.engineer.pk)
        self.assertEqual(self.model().objects.filter(kind='assignment', recipient=self.engineer).count(), 1)

    def test_unstarted_assignment_emails_engineer_without_requiring_a_checklist(self):
        from .workflow_email import process_next_workflow_email
        work = WorkAssignment.objects.create(project=self.project, assigned_to=self.engineer, assigned_by=self.lead,
            site_id='SYNTHETIC-UNSTARTED', latitude=0, longitude=0, description='Synthetic unstarted task')
        job = self.model().objects.get(kind='assignment', recipient=self.engineer)
        self.assertIsNone(job.checklist_id)
        self.assertEqual(job.assignment_id, work.pk)
        with patch('core.workflow_email.GraphMailClient') as graph:
            self.assertTrue(process_next_workflow_email())
        self.assertIn(work.site_id, graph.return_value.send.call_args.args[2])
        self.assertIn('/governance/tasks/', graph.return_value.send.call_args.args[2])

    def test_genuine_assignment_a_b_a_has_three_transition_notifications(self):
        second = self.user('mail-engineer-b', Profile.Roles.ENGINEER)
        work = WorkAssignment.objects.create(project=self.project, assigned_to=self.engineer, assigned_by=self.lead,
            site_id='SYNTHETIC-REASSIGN', latitude=0, longitude=0, description='Synthetic reassignment')
        work.assigned_to = second; work.save(update_fields=['assigned_to'])
        work.assigned_to = self.engineer; work.save(update_fields=['assigned_to'])
        work.save(update_fields=['description'])
        self.assertEqual(self.model().objects.filter(kind='assignment').count(), 3)
        self.assertEqual(self.model().objects.filter(kind='assignment', recipient=self.engineer).count(), 2)

    def test_unstarted_assignment_daily_scope_is_counted_once_and_reassignment_is_rechecked(self):
        from .workflow_email import queue_daily_digests, process_next_workflow_email
        work = WorkAssignment.objects.create(project=self.project, assigned_to=self.engineer, assigned_by=self.lead,
            site_id='SYNTHETIC-DAILY-UNSTARTED', latitude=0, longitude=0, description='Synthetic task')
        self.model().objects.all().delete()
        queue_daily_digests(now=datetime(2026, 11, 5, 16, tzinfo=utc.utc))
        self.model().objects.exclude(recipient=self.engineer).delete()
        with patch('core.workflow_email.GraphMailClient') as graph:
            process_next_workflow_email()
        body = graph.return_value.send.call_args.args[2]
        self.assertIn('Current visible tasks: 2.', body)
        self.assertIn('Unstarted assignments: 1.', body)
        work.checklist = self.c; work.save(update_fields=['checklist'])
        self.model().objects.all().delete()
        queue_daily_digests(now=datetime(2026, 11, 6, 16, tzinfo=utc.utc))
        self.model().objects.exclude(recipient=self.engineer).delete()
        with patch('core.workflow_email.GraphMailClient') as graph:
            process_next_workflow_email()
        self.assertIn('Current visible tasks: 1.', graph.return_value.send.call_args.args[2])

    def test_qa_rejection_notifies_engineer_without_changing_decisions(self):
        from .quality_workflow import review_quality
        self.submit()
        self.model().objects.all().delete()
        self.c.refresh_from_db()
        review_quality(self.qa, self.c, 'reject', 'Synthetic missing evidence', self.c.updated_at.isoformat())
        self.c.refresh_from_db()
        self.assertEqual(self.c.status, Checklist.Status.REJECTED)
        self.assertTrue(self.model().objects.filter(kind='rejection', recipient=self.engineer).exists())
        self.assertFalse(self.model().objects.filter(recipient=self.customer).exists())

    def test_resubmission_creates_new_event_notifications_without_reusing_old_event(self):
        first = self.submit()
        self.c.status = Checklist.Status.REJECTED; self.c.save(update_fields=['status', 'updated_at'])
        second = self.submit()
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(self.model().objects.filter(kind='submission', recipient=self.qa).count(), 2)

    def test_current_registered_email_is_used_not_a_queued_snapshot(self):
        from .workflow_email import process_next_workflow_email
        self.submit()
        self.qa.email = 'updated-qa@example.test'; self.qa.save(update_fields=['email'])
        with patch('core.workflow_email.GraphMailClient') as graph:
            self.assertTrue(process_next_workflow_email())
        self.assertEqual(graph.return_value.send.call_args.args[0], 'updated-qa@example.test')

    def test_recipient_revoked_during_oauth_is_rechecked_before_send_post(self):
        from .workflow_email import process_next_workflow_email
        from .notification_email import GraphMailConfig
        from .http_deadline import Response
        self.submit()
        def revoke():
            self.qa.profile.is_locked = True; self.qa.profile.save(update_fields=['is_locked'])
            return 'synthetic.token'
        config = GraphMailConfig('11111111-2222-4333-8444-555555555555', '66666666-7777-4888-8999-aaaaaaaaaaaa', 'synthetic-secret')
        with patch('core.notification_email.load_config', return_value=config), patch('core.notification_email.GraphMailClient._token', side_effect=revoke), patch('core.notification_email.bounded_request', return_value=Response(202, b'')) as outbound:
            process_next_workflow_email()
        outbound.assert_not_called()
        self.assertEqual(self.model().objects.get(recipient=self.qa).status, 'cancelled')

    def test_recipient_email_changed_during_oauth_is_not_sent_to_old_address(self):
        from .workflow_email import process_next_workflow_email
        from .notification_email import GraphMailConfig
        from .http_deadline import Response
        self.submit()
        def change_email():
            self.qa.email = 'new-during-oauth@example.test'; self.qa.save(update_fields=['email'])
            return 'synthetic.token'
        config = GraphMailConfig('11111111-2222-4333-8444-555555555555', '66666666-7777-4888-8999-aaaaaaaaaaaa', 'synthetic-secret')
        with patch('core.notification_email.load_config', return_value=config), patch('core.notification_email.GraphMailClient._token', side_effect=change_email), patch('core.notification_email.bounded_request', return_value=Response(202, b'')) as outbound:
            process_next_workflow_email()
        outbound.assert_not_called()
        self.assertEqual(self.model().objects.get(recipient=self.qa).status, 'queued')

    def test_revoked_membership_cancels_before_dispatch(self):
        from .models import ProjectMembership
        from .workflow_email import process_next_workflow_email
        self.submit()
        ProjectMembership.objects.create(user=self.qa, project=self.project, is_active=False)
        with patch('core.workflow_email.GraphMailClient') as graph:
            process_next_workflow_email()
        graph.assert_not_called()
        self.assertEqual(self.model().objects.get(recipient=self.qa).status, 'cancelled')

    def test_changed_role_company_or_assignee_cannot_receive_stale_job(self):
        from .workflow_email import process_next_workflow_email
        for change in ('role', 'company', 'assignee'):
            with self.subTest(change=change):
                self.model().objects.all().delete()
                self.qa.profile.role = Profile.Roles.QUALITY_ENGINEER; self.qa.profile.company = self.company; self.qa.profile.save()
                self.c.quality_reviewer = self.qa; self.c.save(update_fields=['quality_reviewer', 'updated_at'])
                self.submit()
                if change == 'role':
                    self.qa.profile.role = Profile.Roles.ENGINEER; self.qa.profile.save()
                elif change == 'company':
                    self.qa.profile.company = self.foreign; self.qa.profile.save()
                else:
                    self.c.quality_reviewer = None; self.c.save(update_fields=['quality_reviewer', 'updated_at'])
                with patch('core.workflow_email.GraphMailClient') as graph:
                    process_next_workflow_email()
                graph.assert_not_called()

    def test_missing_email_never_counts_as_accepted(self):
        from .workflow_email import process_next_workflow_email
        self.submit(); self.qa.email = ''; self.qa.save(update_fields=['email'])
        with patch('core.workflow_email.GraphMailClient') as graph:
            process_next_workflow_email()
        graph.assert_not_called()
        self.assertEqual(self.model().objects.get(recipient=self.qa).status, 'cancelled')

    def test_retryable_failure_and_uncertain_delivery_have_separate_states(self):
        from .workflow_email import process_next_workflow_email
        self.submit()
        with patch('core.workflow_email.GraphMailClient') as graph:
            graph.return_value.send.side_effect = NotificationEmailError('authentication_unavailable', retryable=True)
            process_next_workflow_email()
        job = self.model().objects.get(recipient=self.qa); self.assertEqual(job.status, 'queued'); self.assertEqual(job.attempts, 1)
        job.available_at = timezone.now() - timedelta(seconds=1); job.save(update_fields=['available_at'])
        with patch('core.workflow_email.GraphMailClient') as graph:
            graph.return_value.send.side_effect = NotificationEmailError('send_outcome_unknown', uncertain=True)
            process_next_workflow_email()
        job.refresh_from_db(); self.assertEqual(job.status, 'uncertain')
        with patch('core.workflow_email.GraphMailClient') as graph:
            self.assertFalse(process_next_workflow_email())
        graph.assert_not_called()

    def test_interrupted_lease_becomes_uncertain_once(self):
        import uuid
        from .workflow_email import recover_interrupted_workflow_emails
        self.submit()
        job = self.model().objects.get(recipient=self.qa)
        job.status = 'sending'; job.lease_id = uuid.uuid4(); job.lease_expires_at = timezone.now() - timedelta(seconds=1); job.save()
        self.assertEqual(recover_interrupted_workflow_emails(), 1)
        self.assertEqual(recover_interrupted_workflow_emails(), 0)
        job.refresh_from_db(); self.assertEqual(job.status, 'uncertain')

    def test_unrelated_audits_and_disabled_feature_do_not_queue_messages(self):
        self.event('photo_draft_accepted')
        with override_settings(WORKFLOW_NOTIFICATION_EMAIL_ENABLED=False):
            self.submit()
        self.assertEqual(self.model().objects.count(), 0)

    def test_foreign_checklist_id_in_an_event_is_not_accepted(self):
        other = Project.objects.create(name='Synthetic foreign project', company=self.foreign)
        source = GovernanceAudit.objects.create(actor=self.engineer, action='survey_submitted', project=other, details={'checklist_id': self.c.pk})
        self.assertFalse(self.model().objects.filter(source_audit=source).exists())

    def test_daily_report_is_per_day_project_recipient_and_never_includes_draft_client_data(self):
        from .workflow_email import queue_daily_digests, process_next_workflow_email
        now = datetime(2026, 11, 5, 16, tzinfo=utc.utc)
        self.assertGreater(queue_daily_digests(now=now), 0)
        count = self.model().objects.count(); self.assertEqual(queue_daily_digests(now=now), 0)
        self.assertEqual(self.model().objects.count(), count)
        self.assertFalse(self.model().objects.filter(kind='daily', recipient=self.customer).exists())
        with patch('core.workflow_email.GraphMailClient') as graph:
            while process_next_workflow_email():
                pass
        self.assertTrue(graph.return_value.send.called)
        for args in graph.return_value.send.call_args_list:
            self.assertNotIn('Synthetic foreign', args.args[2])
            self.assertIn('https://testserver/', args.args[2])

    def test_daily_report_respects_configured_hour_and_disabled_switch(self):
        from .workflow_email import queue_daily_digests
        self.assertEqual(queue_daily_digests(now=datetime(2026, 11, 5, 14, tzinfo=utc.utc)), 0)
        with override_settings(WORKFLOW_EMAIL_DAILY_ENABLED=False):
            self.assertEqual(queue_daily_digests(now=datetime(2026, 11, 5, 16, tzinfo=utc.utc)), 0)

    def test_existing_worker_processes_workflow_queue_without_a_second_service(self):
        self.submit()
        with patch('core.management.commands.run_invitation_email_worker.load_config'), patch('core.management.commands.run_invitation_email_worker.queue_daily_digests'), patch('core.workflow_email.GraphMailClient') as graph:
            output = StringIO(); call_command('run_invitation_email_worker', once=True, stdout=output)
        self.assertIn('Processed one workflow email', output.getvalue())
        self.assertEqual(graph.return_value.send.call_count, 1)
        self.assertEqual(self.model().objects.get(recipient=self.qa).status, 'accepted')

    def test_saved_submission_runs_actual_oauth_and_send_http_fixture_once(self):
        from .workflow_email import process_next_workflow_email
        from .notification_email import GraphMailConfig
        from .test_notification_email_transport import graph_fixture, TENANT, CLIENT, SECRET
        self.submit()
        with graph_fixture() as records, patch('core.notification_email.load_config',
                return_value=GraphMailConfig(TENANT, CLIENT, SECRET)):
            self.assertTrue(process_next_workflow_email())
            self.assertFalse(process_next_workflow_email())
        self.assertEqual(len(records), 2)
        payload = json.loads(records[1]['raw'])
        self.assertEqual(payload['message']['toRecipients'][0]['emailAddress']['address'], self.qa.email)
        self.assertNotIn('attachments', payload['message'])
        self.assertIn('https://testserver/custom-checklist/', payload['message']['body']['content'])
        self.assertEqual(self.model().objects.get(recipient=self.qa).status, 'accepted')
        self.c.refresh_from_db(); self.assertEqual(self.c.status, Checklist.Status.SUBMITTED)

    def test_three_definite_failures_stop_until_explicit_retry(self):
        from .workflow_email import process_next_workflow_email, retry_failed_workflow_emails
        self.submit()
        with patch('core.workflow_email.GraphMailClient') as graph:
            graph.return_value.send.side_effect = NotificationEmailError('authentication_unavailable', retryable=True)
            for _ in range(3):
                self.model().objects.filter(status='queued').update(available_at=timezone.now() - timedelta(seconds=1))
                self.assertTrue(process_next_workflow_email())
            self.assertFalse(process_next_workflow_email())
        job = self.model().objects.get(recipient=self.qa)
        self.assertEqual(job.status, 'failed'); self.assertEqual(job.attempts, 3)
        self.assertEqual(retry_failed_workflow_emails(), 1)
        job.refresh_from_db(); self.assertEqual(job.status, 'queued'); self.assertEqual(job.attempts, 0)

    def report(self, directory, *, released):
        from .models import ChecklistTemplate
        from . import survey_processing as pipeline
        from .survey_processing_models import SurveyProcessingRevision, SurveyProcessingResult, SurveyProcessingEvent, SurveyDrawingSet
        self.c.schema_snapshot['sections'][0]['fields'] = [{'id': 'note', 'label': 'Note', 'type': 'text', 'required': False}]
        template = ChecklistTemplate.objects.create(name='Synthetic notification drawing template', created_by=self.admin,
            published=True, checklist_required=True, definition=self.c.schema_snapshot)
        self.c.checklist_template = template; self.c.status = Checklist.Status.FINAL; self.c.client_review_required = False; self.c.save()
        snapshot = pipeline.freeze_data(self.c)
        revision = SurveyProcessingRevision.objects.create(checklist=self.c, number=1, snapshot=snapshot,
            digest=pipeline.digest(snapshot), submitted_by=self.engineer)
        payload = {'checklist_items': [], 'findings': [], 'drawing_records': []}
        SurveyProcessingResult.objects.create(revision=revision, payload=payload, digest=pipeline.digest(payload))
        signature = pipeline.review_digest(payload)
        SurveyProcessingEvent.objects.create(revision=revision, actor=self.engineer, action='engineer_complete', payload={'review_digest': signature})
        SurveyProcessingEvent.objects.create(revision=revision, actor=self.qa, action='technical_approve', payload={'review_digest': signature})
        self.model().objects.all().delete()
        path = Path(directory) / 'SYNTHETIC-REPORT.pdf'; path.write_bytes(b'%PDF-1.4\nSYNTHETIC AUTHORIZATION FIXTURE ONLY\n')
        asset = SurveyDrawingSet.objects.create(revision=revision, edition=1, released=released, geometry={},
            review_digest=signature, manifest={'pdf': str(path), 'sheets': [{'number': 'SYNTHETIC-1'}]})
        return asset

    def test_draft_report_never_queues_client_and_released_report_uses_protected_pdf_link(self):
        from .workflow_email import process_next_workflow_email
        with tempfile.TemporaryDirectory(dir=settings.FILE_UPLOAD_TEMP_DIR) as media, override_settings(MEDIA_ROOT=media):
            asset = self.report(media, released=False)
            self.assertTrue(self.model().objects.filter(kind='report_ready', recipient=self.qa).exists())
            self.assertFalse(self.model().objects.filter(recipient=self.customer).exists())
            from .survey_processing_models import SurveyDrawingSet
            released = SurveyDrawingSet.objects.create(revision=asset.revision, edition=2, released=True,
                review_digest=asset.review_digest, geometry={}, manifest=asset.manifest)
            self.model().objects.exclude(recipient=self.customer).delete()
            with patch('core.workflow_email.GraphMailClient') as graph:
                process_next_workflow_email()
            self.assertEqual(graph.return_value.send.call_count, 1)
            body = graph.return_value.send.call_args.args[2]
            protected = reverse('survey_processing_output', args=[self.c.pk, released.pk, 0, 'pdf'])
            self.assertIn('https://testserver' + protected, body)
            self.assertNotIn(media, body)
            self.client.force_login(self.customer)
            response = self.client.get(protected)
            self.assertEqual(response.status_code, 200); response.close()

    def test_changed_inputs_cancel_client_released_report_notification(self):
        from .workflow_email import process_next_workflow_email
        with tempfile.TemporaryDirectory(dir=settings.FILE_UPLOAD_TEMP_DIR) as media, override_settings(MEDIA_ROOT=media):
            self.report(media, released=True)
            self.model().objects.exclude(recipient=self.customer).delete()
            self.c.answer_data = {'custom': {'synthetic-change': 'changed after release'}}; self.c.save()
            with patch('core.workflow_email.GraphMailClient') as graph:
                process_next_workflow_email()
            graph.assert_not_called()
            self.assertEqual(self.model().objects.get(recipient=self.customer).status, 'cancelled')


@override_settings(NOTIFICATION_EMAIL_ENABLED=True, WORKFLOW_NOTIFICATION_EMAIL_ENABLED=True,
    NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver', ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class WorkflowTaskEntryIntegrationTests(TestCase):
    def setUp(self):
        from .test_task_creation import TaskCreationTests
        self.fixture = TaskCreationTests
        self.fixture.setUp(self)

    def person(self, name, role):
        return self.fixture.person(self, name, role)

    def values(self, **extra):
        return self.fixture.values(self, **extra)

    def test_single_task_view_queues_assignment_before_engineer_opens_site(self):
        from .models import WorkflowEmailDelivery
        response = self.client.post(reverse('task_create'), self.values())
        self.assertEqual(response.status_code, 302)
        work = WorkAssignment.objects.get()
        self.assertEqual(WorkflowEmailDelivery.objects.filter(assignment=work, recipient=self.engineer, kind='assignment').count(), 1)
        self.assertEqual(WorkflowEmailDelivery.objects.get(assignment=work).status, 'queued')

    def test_actual_bulk_preview_commit_and_replay_queue_one_email_per_created_site(self):
        from .models import WorkflowEmailDelivery
        response = self.client.post(reverse('task_create'), self.values(action='preview', mode='bulk', site_id='',
            site_rows=json.dumps([{'site_id': 'MAIL-BULK-A', 'latitude': '24', 'longitude': '46'},
                                  {'site_id': 'MAIL-BULK-B', 'latitude': '25', 'longitude': '47'}])))
        self.assertEqual(response.status_code, 200)
        batch = response.context['batch']; self.assertIsNotNone(batch)
        self.assertEqual(WorkflowEmailDelivery.objects.count(), 0)
        for _ in range(2):
            result = self.client.post(reverse('task_create'), {'action': 'commit', 'mode': 'bulk',
                'project': self.project.pk, 'batch_id': batch.pk})
            self.assertEqual(result.status_code, 302)
        self.assertEqual(WorkflowEmailDelivery.objects.filter(kind='assignment', recipient=self.engineer).count(), 2)
