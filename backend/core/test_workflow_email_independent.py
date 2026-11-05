"""Independent saved-record/API acceptance for workflow email.

Run with scripts/run_backend_tests.py: isolated database/media and controlled
loopback Graph fixtures only. These tests never authenticate to Microsoft.
"""
from datetime import datetime, timedelta, timezone as utc
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (Checklist, ChecklistTemplate, Company, GovernanceAudit,
    IndustryCatalog, Profile, Project, ProjectMembership, WorkAssignment,
    WorkflowEmailDelivery)
from .workflow_email import process_next_workflow_email, queue_daily_digests
from .notification_email import GraphMailClient, GraphMailConfig
from .test_notification_email_transport import graph_fixture, TENANT, CLIENT, SECRET


@override_settings(NOTIFICATION_EMAIL_ENABLED=True, WORKFLOW_NOTIFICATION_EMAIL_ENABLED=True,
    WORKFLOW_EMAIL_DAILY_ENABLED=True, WORKFLOW_EMAIL_DAILY_HOUR=15,
    NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver', ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentWorkflowEmailTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Independent workflow email company')
        self.industry = IndustryCatalog.objects.get(code='telecom')
        self.admin = self.person('operator', Profile.Roles.ADMIN)
        self.template = ChecklistTemplate.objects.create(name='Independent workflow schema',
            published=True, created_by=self.admin,
            definition={'title': 'Independent workflow', 'sections': [
                {'id': 'general', 'title': 'General', 'fields': [
                    {'id': 'site_id', 'label': 'Site ID', 'type': 'text', 'system': 'site_id'}]}]})
        self.project = Project.objects.create(name='Independent workflow project', company=self.company,
            administrator=self.admin, checklist_template=self.template)
        self.bind(self.admin)
        self.engineer = self.person('engineer', Profile.Roles.ENGINEER)
        self.qa = self.person('qa', Profile.Roles.QUALITY_ENGINEER)
        self.lead = self.person('lead', Profile.Roles.TEAM_LEAD)
        self.customer = self.person('customer', Profile.Roles.CLIENT)
        self.client.force_login(self.admin)

    def bind(self, user, project=None):
        project = project or self.project
        user.profile.project = project
        user.profile.save()
        ProjectMembership.objects.create(user=user, project=project, is_active=True, is_primary=True)

    def person(self, suffix, role):
        user = User.objects.create_user('independent_workflow_' + suffix,
            email='independent-' + suffix + '@example.test')
        user.profile.company = self.company
        user.profile.role = role
        user.profile.admin_industry = self.industry if role == Profile.Roles.ADMIN else None
        user.profile.save()
        if hasattr(self, 'project'):
            self.bind(user)
        return user

    def checklist(self, suffix='saved'):
        return Checklist.objects.create(project=self.project, user=self.engineer,
            quality_reviewer=self.qa, site_id='INDEPENDENT-WF-' + suffix,
            schema_snapshot=self.template.definition)

    def work(self, suffix='unstarted', checklist=None, engineer=None):
        return WorkAssignment.objects.create(project=self.project, assigned_by=self.lead,
            assigned_to=engineer or self.engineer, site_id='INDEPENDENT-WF-' + suffix,
            latitude=24, longitude=46, description='Synthetic independent assignment',
            checklist=checklist)

    def form_values(self, **extra):
        return {'action': 'create', 'mode': 'single', 'project': self.project.pk,
            'engineer': self.engineer.pk, 'quality_reviewer': self.qa.pk,
            'site_id': 'INDEPENDENT-WF-API', 'latitude': '24', 'longitude': '46',
            'coordinate_source': 'Synthetic independent register', 'coordinate_crs': 'EPSG:4326',
            'description': 'Synthetic API workflow task', **extra}

    def submit(self, checklist):
        self.client.force_login(self.engineer)
        with patch('core.workflow_email.GraphMailClient', side_effect=AssertionError('No Graph in HTTP request')):
            response = self.client.post(reverse('custom_checklist_submit', args=[checklist.pk]))
        self.assertEqual(response.status_code, 302)
        checklist.refresh_from_db()
        self.assertEqual(checklist.status, Checklist.Status.SUBMITTED)
        return WorkflowEmailDelivery.objects.filter(checklist=checklist, kind='submission', recipient=self.qa).latest('created_at')

    def test_unstarted_site_queues_before_any_checklist_and_its_link_opens_permitted_tasks(self):
        with patch('core.workflow_email.GraphMailClient', side_effect=AssertionError('Save must not send')):
            assignment = self.work()
        self.assertEqual(Checklist.objects.count(), 0)
        job = WorkflowEmailDelivery.objects.get(assignment=assignment, recipient=self.engineer)
        self.assertIsNone(job.checklist_id)
        with patch('core.workflow_email.GraphMailClient') as graph:
            self.assertTrue(process_next_workflow_email())
        body = graph.return_value.send.call_args.args[2]
        self.assertIn(assignment.site_id, body)
        self.client.force_login(self.engineer)
        page = self.client.get(reverse('governance_tasks'), {'project': self.project.pk, 'q': assignment.site_id})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, assignment.site_id)

    def test_actual_single_assignment_duplicate_click_preserves_one_saved_task_and_email(self):
        with patch('core.workflow_email.GraphMailClient', side_effect=AssertionError('HTTP must not send')):
            first = self.client.post(reverse('task_create'), self.form_values())
            duplicate = self.client.post(reverse('task_create'), self.form_values())
        self.assertEqual(first.status_code, 302)
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(WorkAssignment.objects.count(), 1)
        self.assertEqual(WorkflowEmailDelivery.objects.filter(kind='assignment', recipient=self.engineer).count(), 1)

    def test_actual_bulk_preview_is_silent_and_replayed_commit_does_not_duplicate_email(self):
        rows = [{'site_id': 'INDEPENDENT-BULK-1', 'latitude': '24', 'longitude': '46'},
                {'site_id': 'INDEPENDENT-BULK-2', 'latitude': '25', 'longitude': '47'}]
        with patch('core.workflow_email.GraphMailClient', side_effect=AssertionError('HTTP must not send')):
            preview = self.client.post(reverse('task_create'), self.form_values(action='preview',
                mode='bulk', site_id='', site_rows=json.dumps(rows)))
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(WorkflowEmailDelivery.objects.count(), 0)
            batch = preview.context['batch']
            self.assertIsNotNone(batch)
            for _ in range(2):
                response = self.client.post(reverse('task_create'), {'action': 'commit', 'mode': 'bulk',
                    'project': str(self.project.pk), 'batch_id': str(batch.pk)})
                self.assertEqual(response.status_code, 302)
        self.assertEqual(WorkAssignment.objects.count(), 2)
        self.assertEqual(WorkflowEmailDelivery.objects.filter(kind='assignment', recipient=self.engineer).count(), 2)

    def test_a_to_b_to_a_is_three_saved_transitions_but_business_audit_and_repeated_save_are_silent(self):
        second = self.person('second-engineer', Profile.Roles.ENGINEER)
        assignment = self.work()
        assignment.assigned_to = second
        assignment.save(update_fields=['assigned_to'])
        assignment.assigned_to = self.engineer
        assignment.save(update_fields=['assigned_to'])
        assignment.save(update_fields=['description'])
        GovernanceAudit.objects.create(action='task_assigned', actor=self.lead, project=self.project,
            details={'assignment_id': assignment.pk, 'engineer_id': self.engineer.pk})
        jobs = WorkflowEmailDelivery.objects.filter(kind='assignment')
        self.assertEqual(jobs.count(), 3)
        self.assertEqual(jobs.filter(recipient=self.engineer).count(), 2)
        self.assertEqual(jobs.values('event_key').distinct().count(), 3)

    def test_quality_reviewer_assignment_endpoint_delivers_to_current_qa(self):
        checklist = self.checklist()
        new_qa = self.person('replacement-qa', Profile.Roles.QUALITY_ENGINEER)
        with patch('core.workflow_email.GraphMailClient', side_effect=AssertionError('HTTP must not send')):
            response = self.client.post(reverse('quality_reviewer_assign', args=[checklist.pk]),
                {'quality_reviewer': new_qa.pk, 'reason': 'Synthetic reviewer reassignment',
                 'expected_updated_at': checklist.updated_at.isoformat()})
        self.assertEqual(response.status_code, 302)
        checklist.refresh_from_db()
        self.assertEqual(checklist.quality_reviewer_id, new_qa.pk)
        job = WorkflowEmailDelivery.objects.get(checklist=checklist, recipient=new_qa, kind='assignment')
        with patch('core.workflow_email.GraphMailClient') as graph:
            self.assertTrue(process_next_workflow_email())
        graph.return_value.send.assert_called_once()
        self.assertEqual(graph.return_value.send.call_args.args[0], new_qa.email)
        job.refresh_from_db()
        self.assertEqual(job.status, 'accepted')

    def test_daily_counts_unstarted_and_linked_tasks_once_and_is_project_scoped(self):
        checklist = self.checklist()
        self.work('linked', checklist=checklist)
        self.work('pending')
        foreign = Project.objects.create(name='Independent foreign project', company=self.company)
        foreign_engineer = self.person('foreign-engineer', Profile.Roles.ENGINEER)
        WorkAssignment.objects.create(project=foreign, assigned_by=self.lead, assigned_to=foreign_engineer,
            site_id='FOREIGN-UNSTARTED', latitude=25, longitude=45, description='Must stay outside this summary')
        WorkflowEmailDelivery.objects.all().delete()
        now = datetime(2026, 11, 5, 16, tzinfo=utc.utc)
        queue_daily_digests(now=now)
        self.assertEqual(queue_daily_digests(now=now), 0)
        WorkflowEmailDelivery.objects.exclude(recipient=self.engineer).delete()
        with patch('core.workflow_email.GraphMailClient') as graph:
            self.assertTrue(process_next_workflow_email())
        graph.return_value.send.assert_called_once()
        body = graph.return_value.send.call_args.args[2]
        self.assertIn('Current visible tasks: 2.', body)
        self.assertIn('Unstarted assignments: 1.', body)
        self.assertNotIn('FOREIGN', body)

    def test_saved_api_submission_uses_fresh_registered_address_through_real_fixture_http(self):
        checklist = self.checklist()
        job = self.submit(checklist)
        self.qa.email = 'fresh-registered-quality@example.test'
        self.qa.save(update_fields=['email'])
        before = Checklist.objects.filter(pk=checklist.pk).values('status', 'quality_approval',
            'section_approvals', 'review_history', 'answer_data').get()
        config = GraphMailConfig(TENANT, CLIENT, SECRET)
        with graph_fixture() as records, patch('core.notification_email.load_config', return_value=config):
            self.assertTrue(process_next_workflow_email())
            self.assertFalse(process_next_workflow_email())
        self.assertEqual(len(records), 2)
        sends = [record for record in records if record['path'] == '/send']
        self.assertEqual(len(sends), 1)
        payload = json.loads(sends[0]['raw'])
        self.assertEqual(payload['message']['toRecipients'][0]['emailAddress']['address'], self.qa.email)
        self.assertTrue(payload['saveToSentItems'])
        body = payload['message']['body']['content']
        self.assertIn('https://testserver' + reverse('custom_checklist', args=[checklist.pk]), body)
        self.assertNotIn(SECRET, body)
        job.refresh_from_db()
        self.assertEqual(job.status, 'accepted')
        self.assertIsNotNone(job.accepted_at)
        after = Checklist.objects.filter(pk=checklist.pk).values(*before).get()
        self.assertEqual(after, before, 'Transport acceptance must not approve or rewrite engineering work')

    def test_queued_submission_cancels_after_current_authority_is_revoked(self):
        foreign = Company.objects.create(name='Foreign notification affiliation')
        membership = ProjectMembership.objects.get(project=self.project, user=self.qa)
        changes = {
            'deactivated': lambda: User.objects.filter(pk=self.qa.pk).update(is_active=False),
            'role_changed': lambda: Profile.objects.filter(user=self.qa).update(role=Profile.Roles.ENGINEER),
            'locked': lambda: Profile.objects.filter(user=self.qa).update(is_locked=True),
            'membership_revoked': lambda: ProjectMembership.objects.filter(pk=membership.pk).update(is_active=False),
            'company_changed': lambda: Profile.objects.filter(user=self.qa).update(company=foreign),
        }
        for label, mutate in changes.items():
            with self.subTest(label=label):
                checklist = self.checklist(label)
                job = self.submit(checklist)
                mutate()
                with patch('core.workflow_email.GraphMailClient') as graph:
                    self.assertTrue(process_next_workflow_email())
                graph.assert_not_called()
                job.refresh_from_db()
                self.assertEqual(job.status, 'cancelled')
                User.objects.filter(pk=self.qa.pk).update(is_active=True)
                Profile.objects.filter(user=self.qa).update(role=Profile.Roles.QUALITY_ENGINEER,
                    is_locked=False, company=self.company)
                ProjectMembership.objects.filter(pk=membership.pk).update(is_active=True)

    def test_old_qa_notification_cancels_after_reviewer_is_reassigned(self):
        checklist = self.checklist()
        job = self.submit(checklist)
        new_qa = self.person('new-assigned-qa', Profile.Roles.QUALITY_ENGINEER)
        Checklist.objects.filter(pk=checklist.pk).update(quality_reviewer=new_qa)
        with patch('core.workflow_email.GraphMailClient') as graph:
            self.assertTrue(process_next_workflow_email())
        graph.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, 'cancelled')

    def test_foreign_project_assignment_request_creates_no_work_or_notification(self):
        other = Company.objects.create(name='Foreign request company')
        foreign_project = Project.objects.create(name='Foreign request project', company=other,
            checklist_template=self.template)
        response = self.client.post(reverse('task_create'), self.form_values(project=foreign_project.pk))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(WorkflowEmailDelivery.objects.count(), 0)
        self.assertEqual(WorkAssignment.objects.count(), 0)

    def test_duplicate_submission_click_is_silent_but_rejected_resubmission_is_a_new_event(self):
        checklist = self.checklist()
        first = self.submit(checklist)
        self.submit(checklist)
        self.assertEqual(WorkflowEmailDelivery.objects.filter(kind='submission', recipient=self.qa).count(), 1)
        self.client.force_login(self.qa)
        checklist.refresh_from_db()
        response = self.client.post(reverse('quality_review', args=[checklist.pk]),
            {'decision': 'reject', 'reason': 'Synthetic missing evidence',
             'expected_updated_at': checklist.updated_at.isoformat()})
        self.assertEqual(response.status_code, 302)
        second = self.submit(checklist)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(WorkflowEmailDelivery.objects.filter(kind='submission', recipient=self.qa).count(), 2)

    def test_actual_quality_approval_notifies_next_stage_and_does_not_rewrite_decision_on_delivery(self):
        checklist = self.checklist()
        self.submit(checklist)
        WorkflowEmailDelivery.objects.all().delete()
        self.client.force_login(self.qa)
        checklist.refresh_from_db()
        with patch('core.workflow_email.GraphMailClient', side_effect=AssertionError('HTTP must not send')):
            response = self.client.post(reverse('quality_review', args=[checklist.pk]),
                {'decision': 'approve', 'reason': 'Synthetic recorded quality approval',
                 'expected_updated_at': checklist.updated_at.isoformat()})
        self.assertEqual(response.status_code, 302)
        checklist.refresh_from_db()
        self.assertEqual(checklist.status, Checklist.Status.REVIEW)
        before = (checklist.quality_approval, checklist.review_history, checklist.section_approvals)
        self.assertEqual(set(WorkflowEmailDelivery.objects.values_list('recipient_id', flat=True)),
            {self.engineer.pk, self.lead.pk, self.admin.pk})
        with patch('core.workflow_email.GraphMailClient') as graph:
            while process_next_workflow_email():
                pass
        self.assertEqual(graph.return_value.send.call_count, 3)
        checklist.refresh_from_db()
        self.assertEqual((checklist.quality_approval, checklist.review_history, checklist.section_approvals), before)

    def report_asset(self, directory, released):
        from . import survey_processing as processing
        from .survey_processing_models import (SurveyDrawingSet, SurveyProcessingEvent,
            SurveyProcessingResult, SurveyProcessingRevision)
        template = ChecklistTemplate.objects.create(name='Independent report schema', published=True,
            checklist_required=True, definition=self.template.definition, created_by=self.admin)
        checklist = Checklist.objects.create(project=self.project, user=self.engineer,
            quality_reviewer=self.qa, site_id='INDEPENDENT-WF-report', checklist_template=template)
        checklist.status = Checklist.Status.FINAL
        checklist.client_review_required = False
        checklist.save()
        snapshot = processing.freeze_data(checklist)
        revision = SurveyProcessingRevision.objects.create(checklist=checklist, number=1,
            snapshot=snapshot, digest=processing.digest(snapshot), submitted_by=self.engineer)
        payload = {'checklist_items': [], 'findings': [], 'drawing_records': []}
        SurveyProcessingResult.objects.create(revision=revision, payload=payload, digest=processing.digest(payload))
        signature = processing.review_digest(payload)
        for actor, action in [(self.engineer, 'engineer_complete'), (self.qa, 'technical_approve')]:
            SurveyProcessingEvent.objects.create(revision=revision, actor=actor, action=action,
                payload={'review_digest': signature})
        WorkflowEmailDelivery.objects.all().delete()
        path = Path(directory) / 'INDEPENDENT-AUTHORIZATION-FIXTURE.pdf'
        path.write_bytes(b'%PDF-1.4\nSynthetic report authorization fixture only\n')
        asset = SurveyDrawingSet.objects.create(revision=revision, edition=1, released=released,
            geometry={}, review_digest=signature,
            manifest={'pdf': str(path), 'sheets': [{'number': 'INDEPENDENT-1'}]})
        return checklist, asset

    def test_released_full_report_email_links_to_actual_protected_view_and_blocks_foreign_user(self):
        with tempfile.TemporaryDirectory(dir=settings.FILE_UPLOAD_TEMP_DIR) as directory, override_settings(MEDIA_ROOT=directory):
            checklist, asset = self.report_asset(directory, released=True)
            WorkflowEmailDelivery.objects.exclude(recipient=self.customer).delete()
            self.assertEqual(WorkflowEmailDelivery.objects.count(), 1)
            with patch('core.workflow_email.GraphMailClient') as graph:
                self.assertTrue(process_next_workflow_email())
            body = graph.return_value.send.call_args.args[2]
            link = reverse('survey_processing_output', args=[checklist.pk, asset.pk, 0, 'pdf'])
            self.assertIn('https://testserver' + link, body)
            self.assertNotIn(directory, body)
            self.client.force_login(self.customer)
            response = self.client.get(link)
            self.assertEqual(response.status_code, 200)
            response.close()
            foreign = self.person('foreign-client', Profile.Roles.CLIENT)
            other = Company.objects.create(name='Foreign full-report company')
            Profile.objects.filter(user=foreign).update(company=other)
            self.client.force_login(foreign)
            denied = self.client.get(link)
            self.assertEqual(denied.status_code, 404)

    def test_draft_report_never_emails_client_and_actual_download_denies_client(self):
        with tempfile.TemporaryDirectory(dir=settings.FILE_UPLOAD_TEMP_DIR) as directory, override_settings(MEDIA_ROOT=directory):
            checklist, asset = self.report_asset(directory, released=False)
            self.assertFalse(WorkflowEmailDelivery.objects.filter(recipient=self.customer).exists())
            self.client.force_login(self.customer)
            response = self.client.get(reverse('survey_processing_output', args=[checklist.pk, asset.pk, 0, 'pdf']))
            self.assertEqual(response.status_code, 404)

    def test_membership_revoked_during_real_fixture_oauth_prevents_send_post(self):
        job = self.submit(self.checklist())
        original_token = GraphMailClient._token

        def revoke_after_token(client):
            token = original_token(client)
            ProjectMembership.objects.filter(project=self.project, user=self.qa).update(is_active=False)
            return token

        with graph_fixture() as records, patch('core.notification_email.load_config',
                return_value=GraphMailConfig(TENANT, CLIENT, SECRET)), \
                patch.object(GraphMailClient, '_token', revoke_after_token):
            self.assertTrue(process_next_workflow_email())
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]['path'].startswith('/token/'))
        job.refresh_from_db()
        self.assertEqual(job.status, 'cancelled')

    def test_email_changed_during_real_oauth_requeues_then_uses_new_address(self):
        job = self.submit(self.checklist())
        original_token = GraphMailClient._token

        def change_after_token(client):
            token = original_token(client)
            User.objects.filter(pk=self.qa.pk).update(email='changed-during-oauth@example.test')
            return token

        with graph_fixture() as records, patch('core.notification_email.load_config',
                return_value=GraphMailConfig(TENANT, CLIENT, SECRET)):
            with patch.object(GraphMailClient, '_token', change_after_token):
                self.assertTrue(process_next_workflow_email())
            job.refresh_from_db()
            self.assertEqual(job.status, 'queued')
            self.assertEqual(len(records), 1)
            job.available_at = timezone.now() - timedelta(seconds=1)
            job.save(update_fields=['available_at'])
            self.assertTrue(process_next_workflow_email())
            self.assertFalse(process_next_workflow_email())
        sends = [record for record in records if record['path'] == '/send']
        self.assertEqual(len(sends), 1)
        payload = json.loads(sends[0]['raw'])
        self.assertEqual(payload['message']['toRecipients'][0]['emailAddress']['address'],
            'changed-during-oauth@example.test')
        job.refresh_from_db()
        self.assertEqual((job.status, job.attempts), ('accepted', 2))

    def test_changed_released_report_inputs_cancel_email_and_actual_client_download(self):
        with tempfile.TemporaryDirectory(dir=settings.FILE_UPLOAD_TEMP_DIR) as directory, override_settings(MEDIA_ROOT=directory):
            checklist, asset = self.report_asset(directory, released=True)
            WorkflowEmailDelivery.objects.exclude(recipient=self.customer).delete()
            job = WorkflowEmailDelivery.objects.get()
            checklist.answer_data = {'custom': {'revised': 'Inputs changed after the approved report'}}
            checklist.save(update_fields=['answer_data'])
            with patch('core.workflow_email.GraphMailClient') as graph:
                self.assertTrue(process_next_workflow_email())
            graph.assert_not_called()
            job.refresh_from_db()
            self.assertEqual(job.status, 'cancelled')
            self.client.force_login(self.customer)
            response = self.client.get(reverse('survey_processing_output', args=[checklist.pk, asset.pk, 0, 'pdf']))
            self.assertEqual(response.status_code, 404)

    def test_daily_only_unstarted_assignment_still_queues_engineer_admin_and_lead(self):
        self.work()
        WorkflowEmailDelivery.objects.all().delete()
        self.assertEqual(Checklist.objects.count(), 0)
        queue_daily_digests(now=datetime(2026, 11, 5, 16, tzinfo=utc.utc))
        self.assertEqual(set(WorkflowEmailDelivery.objects.values_list('recipient_id', flat=True)),
            {self.engineer.pk, self.admin.pk, self.lead.pk})
        WorkflowEmailDelivery.objects.exclude(recipient=self.engineer).delete()
        with patch('core.workflow_email.GraphMailClient') as graph:
            self.assertTrue(process_next_workflow_email())
        body = graph.return_value.send.call_args.args[2]
        self.assertIn('Current visible tasks: 1.', body)
        self.assertIn('Unstarted assignments: 1.', body)

    def test_daily_recipient_revocation_cancels_saved_summary(self):
        self.work()
        WorkflowEmailDelivery.objects.all().delete()
        queue_daily_digests(now=datetime(2026, 11, 5, 16, tzinfo=utc.utc))
        WorkflowEmailDelivery.objects.exclude(recipient=self.engineer).delete()
        ProjectMembership.objects.filter(project=self.project, user=self.engineer).update(is_active=False)
        with patch('core.workflow_email.GraphMailClient') as graph:
            self.assertTrue(process_next_workflow_email())
        graph.assert_not_called()
        self.assertEqual(WorkflowEmailDelivery.objects.get().status, 'cancelled')

    def test_daily_client_summary_counts_only_currently_shared_final_tasks(self):
        final = self.checklist('client-shared-final')
        final.status = Checklist.Status.FINAL
        final.client_review_required = False
        final.save(update_fields=['status', 'client_review_required'])
        self.checklist('internal-draft')
        queue_daily_digests(now=datetime(2026, 11, 5, 16, tzinfo=utc.utc))
        WorkflowEmailDelivery.objects.exclude(recipient=self.customer).delete()
        self.assertEqual(WorkflowEmailDelivery.objects.count(), 1)
        with patch('core.workflow_email.GraphMailClient') as graph:
            self.assertTrue(process_next_workflow_email())
        body = graph.return_value.send.call_args.args[2]
        self.assertIn('Current visible tasks: 1.', body)
        self.assertIn('Draft: 0', body)
        self.assertNotIn('internal-draft', body)

    def test_platform_super_admin_is_excluded_from_operational_mail_and_task_creation(self):
        platform = self.person('platform', Profile.Roles.SUPER_ADMIN)
        User.objects.filter(pk=platform.pk).update(is_superuser=True, is_staff=True)
        self.work()
        queue_daily_digests(now=datetime(2026, 11, 5, 16, tzinfo=utc.utc))
        self.assertFalse(WorkflowEmailDelivery.objects.filter(recipient=platform).exists())
        self.client.force_login(platform)
        response = self.client.post(reverse('task_create'), self.form_values())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(WorkAssignment.objects.count(), 1)


from . import test_engineer_category_submission_acceptance as category_fixtures


@override_settings(NOTIFICATION_EMAIL_ENABLED=True, WORKFLOW_NOTIFICATION_EMAIL_ENABLED=True,
    NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver', ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentCategoryWorkflowEmailTests(TestCase):
    # Reuse established synthetic capture setup/helpers without inheriting tests.
    person = category_fixtures.EngineerCategorySubmissionAcceptanceTests.person
    add_photo = category_fixtures.EngineerCategorySubmissionAcceptanceTests.add_photo
    raw = category_fixtures.EngineerCategorySubmissionAcceptanceTests.raw
    post = category_fixtures.EngineerCategorySubmissionAcceptanceTests.post
    state = category_fixtures.EngineerCategorySubmissionAcceptanceTests.state
    upload = category_fixtures.EngineerCategorySubmissionAcceptanceTests.upload
    submit = category_fixtures.EngineerCategorySubmissionAcceptanceTests.submit
    route = category_fixtures.EngineerCategorySubmissionAcceptanceTests.route
    assert_submitted = category_fixtures.EngineerCategorySubmissionAcceptanceTests.assert_submitted

    def setUp(self):
        category_fixtures.EngineerCategorySubmissionAcceptanceTests.setUp(self)
        for user in (self.admin, self.engineer, self.quality, self.lead, self.customer):
            user.email = user.username + '@example.test'
            user.save(update_fields=['email'])
        WorkflowEmailDelivery.objects.all().delete()

    def test_category_http_submission_queues_qa_before_inference_and_replay_is_silent(self):
        from .survey_processing_models import SurveyProcessingResult
        self.upload('Civil')
        with patch('core.workflow_email.GraphMailClient', side_effect=AssertionError('HTTP must not send')):
            response, request_digest = self.submit()
        self.assertEqual(response.status_code, 201, response.content)
        revision = self.assert_submitted()
        self.assertFalse(SurveyProcessingResult.objects.filter(revision=revision).exists())
        job = WorkflowEmailDelivery.objects.get(kind='submission', recipient=self.quality)
        self.assertEqual(job.status, 'queued')
        self.assertFalse(WorkflowEmailDelivery.objects.filter(recipient=self.customer).exists())
        self.client.force_login(self.quality)
        immediate_qa = self.client.get(reverse('photo_capture_review_state', args=[self.checklist.pk]))
        self.assertEqual(immediate_qa.status_code, 200)
        self.assertEqual(immediate_qa.json()['revision_id'], revision.pk)
        self.client.force_login(self.engineer)
        replay, _ = self.submit(digest=request_digest)
        self.assertEqual(replay.status_code, 200, replay.content)
        self.assertEqual(WorkflowEmailDelivery.objects.filter(kind='submission', recipient=self.quality).count(), 1)

    def test_category_return_and_resubmission_queue_distinct_saved_handoffs(self):
        self.upload('Civil')
        first, _ = self.submit()
        self.assertEqual(first.status_code, 201, first.content)
        first_job = WorkflowEmailDelivery.objects.get(kind='submission', recipient=self.quality)
        response = self.route(self.quality, 'reject', 'Synthetic evidence returned for correction')
        self.assertEqual(response.status_code, 302, response.content)
        self.assertTrue(WorkflowEmailDelivery.objects.filter(kind='rejection', recipient=self.engineer).exists())
        self.client.force_login(self.engineer)
        second, _ = self.submit()
        self.assertEqual(second.status_code, 201, second.content)
        jobs = WorkflowEmailDelivery.objects.filter(kind='submission', recipient=self.quality)
        self.assertEqual(jobs.count(), 2)
        self.assertEqual(jobs.values('event_key').distinct().count(), 2)
        self.assertTrue(jobs.filter(pk=first_job.pk).exists())
