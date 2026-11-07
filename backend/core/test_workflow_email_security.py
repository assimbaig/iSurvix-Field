"""Independent adversarial notification tests, synthetic records/loopback only."""
from datetime import datetime, timedelta, timezone as utc
import json
import uuid
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (Checklist, Company, GovernanceAudit, IndustryCatalog,
    Profile, Project, ProjectMembership, WorkAssignment, WorkflowEmailDelivery)
from .notification_email import GraphMailClient, GraphMailConfig
from .test_notification_email_transport import graph_fixture, TENANT, CLIENT, SECRET
from .workflow_email import (process_next_workflow_email, queue_audit_event,
    queue_daily_digests, recover_interrupted_workflow_emails,
    retry_failed_workflow_emails)


@override_settings(NOTIFICATION_EMAIL_ENABLED=True, WORKFLOW_NOTIFICATION_EMAIL_ENABLED=True,
    WORKFLOW_EMAIL_DAILY_ENABLED=True, WORKFLOW_EMAIL_DAILY_HOUR=15,
    NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver', ALLOWED_HOSTS=['testserver'],
    ROOT_URLCONF='checklist.urls_local', SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class WorkflowEmailSecurityTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Synthetic security email company')
        self.industry = IndustryCatalog.objects.get(code='telecom')
        self.admin = self.person('admin', Profile.Roles.ADMIN)
        self.project = Project.objects.create(name='Synthetic security email project',
            company=self.company, administrator=self.admin)
        self.bind(self.admin)
        self.engineer = self.person('engineer', Profile.Roles.ENGINEER)
        self.qa = self.person('qa', Profile.Roles.QUALITY_ENGINEER)
        self.lead = self.person('lead', Profile.Roles.TEAM_LEAD)
        self.customer = self.person('customer', Profile.Roles.CLIENT)
        self.checklist = Checklist.objects.create(project=self.project, user=self.engineer,
            quality_reviewer=self.qa, site_id='SECURITY-EMAIL-1',
            schema_snapshot={'title': 'Synthetic', 'sections': [
                {'id': 'general', 'title': 'General', 'fields': []}]})

    def bind(self, user, project=None):
        project = project or self.project
        Profile.objects.filter(user=user).update(project=project)
        ProjectMembership.objects.create(user=user, project=project, is_primary=True)

    def person(self, suffix, role, company=None):
        user = User.objects.create_user('security_workflow_' + suffix,
            email='security-' + suffix + '@example.test')
        profile = user.profile
        profile.company = company or self.company
        profile.role = role
        if role == Profile.Roles.ADMIN:
            profile.admin_industry = self.industry
        profile.save()
        if hasattr(self, 'project'):
            self.bind(user)
        return user

    def submitted(self):
        self.checklist.status = Checklist.Status.SUBMITTED
        self.checklist.save(update_fields=['status'])
        event = GovernanceAudit.objects.create(actor=self.engineer, project=self.project,
            action='survey_submitted', details={'checklist_id': self.checklist.pk,
                'reason': 'PRIVATE-REVIEWER-REMARK', 'ai_findings': 'PRIVATE-AI-FINDING'})
        return WorkflowEmailDelivery.objects.get(source_audit=event, recipient=self.qa)

    def assert_cancelled_without_graph(self, job):
        with patch('core.workflow_email.GraphMailClient') as graph:
            self.assertTrue(process_next_workflow_email())
        graph.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, 'cancelled')
        self.assertIsNone(job.accepted_at)

    def test_foreign_company_profile_cannot_receive_even_with_active_project_membership(self):
        job = self.submitted()
        other = Company.objects.create(name='Synthetic foreign security company')
        Profile.objects.filter(user=self.qa).update(company=other)
        self.assert_cancelled_without_graph(job)

    def test_project_company_changed_after_queue_cancels_bound_company_delivery(self):
        job = self.submitted()
        other = Company.objects.create(name='Synthetic reassigned security company')
        Project.objects.filter(pk=self.project.pk).update(company=other)
        Profile.objects.filter(user=self.qa).update(company=other)
        self.assert_cancelled_without_graph(job)

    def test_expired_explicit_membership_is_not_restored_by_legacy_profile_project(self):
        job = self.submitted()
        ProjectMembership.objects.filter(project=self.project, user=self.qa).update(
            expires_at=timezone.now() - timedelta(seconds=1))
        self.assert_cancelled_without_graph(job)

    def test_registered_recipient_header_injection_is_cancelled_without_http(self):
        job = self.submitted()
        User.objects.filter(pk=self.qa.pk).update(email='quality@example.test\r\nBcc: attacker@example.test')
        self.assert_cancelled_without_graph(job)

    def test_platform_owner_promotion_cancels_operational_notification(self):
        job = self.submitted()
        User.objects.filter(pk=self.qa.pk).update(is_superuser=True)
        self.assert_cancelled_without_graph(job)

    def test_qa_reassignment_after_actual_oauth_prevents_send_to_previous_qa(self):
        job = self.submitted()
        replacement = self.person('replacement', Profile.Roles.QUALITY_ENGINEER)
        original = GraphMailClient._token

        def replaced_after_oauth(client):
            token = original(client)
            Checklist.objects.filter(pk=self.checklist.pk).update(quality_reviewer=replacement)
            return token

        with graph_fixture() as records, patch('core.notification_email.load_config',
                return_value=GraphMailConfig(TENANT, CLIENT, SECRET)), \
                patch.object(GraphMailClient, '_token', replaced_after_oauth):
            self.assertTrue(process_next_workflow_email())
        self.assertEqual([record['path'] for record in records], ['/token/' + TENANT])
        job.refresh_from_db()
        self.assertEqual(job.status, 'cancelled')

    def test_company_revocation_after_actual_oauth_prevents_send(self):
        job = self.submitted()
        other = Company.objects.create(name='Synthetic revoked email company')
        original = GraphMailClient._token

        def revoked_after_oauth(client):
            token = original(client)
            Profile.objects.filter(user=self.qa).update(company=other)
            return token

        with graph_fixture() as records, patch('core.notification_email.load_config',
                return_value=GraphMailConfig(TENANT, CLIENT, SECRET)), \
                patch.object(GraphMailClient, '_token', revoked_after_oauth):
            self.assertTrue(process_next_workflow_email())
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]['path'].startswith('/token/'))
        job.refresh_from_db()
        self.assertEqual(job.status, 'cancelled')

    def test_actual_transport_omits_remarks_ai_paths_tokens_and_attachments(self):
        job = self.submitted()
        with graph_fixture() as records, patch('core.notification_email.load_config',
                return_value=GraphMailConfig(TENANT, CLIENT, SECRET)):
            self.assertTrue(process_next_workflow_email())
            self.assertFalse(process_next_workflow_email())
        self.assertEqual(len(records), 2)
        data = json.loads(records[-1]['raw'])
        content = data['message']['body']['content']
        # Owner-requested presentation is escaped HTML; all original privacy,
        # recipient, link, no-attachment and human-decision checks remain below.
        self.assertEqual(data['message']['body']['contentType'], 'HTML')
        self.assertIn('/static/core/img/ifield-logo.webp',content)
        self.assertNotIn('<script',content.lower())
        self.assertNotIn('attachments', data['message'])
        for private in ['PRIVATE-REVIEWER-REMARK', 'PRIVATE-AI-FINDING', SECRET,
                        'synthetic-access-token', '.local/', 'F:\\']:
            self.assertNotIn(private, content)
        self.assertIn('https://testserver' + reverse('custom_checklist', args=[self.checklist.pk]), content)
        self.assertEqual(data['message']['toRecipients'], [
            {'emailAddress': {'address': self.qa.email}}])
        job.refresh_from_db()
        self.assertEqual(job.status, 'accepted')
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, Checklist.Status.SUBMITTED)
        self.assertEqual(self.checklist.quality_approval, {})

    def test_forged_unsaved_audit_values_are_not_used_instead_of_persisted_event(self):
        original = GovernanceAudit.objects.create(project=self.project,
            action='unrelated_action', details={'checklist_id': self.checklist.pk})
        forged = GovernanceAudit(pk=original.pk, project=self.project,
            action='survey_submitted', details={'checklist_id': self.checklist.pk})
        self.assertEqual(queue_audit_event(forged), 0)
        self.assertFalse(WorkflowEmailDelivery.objects.exists())

    def test_foreign_checklist_in_saved_audit_does_not_leak_to_local_recipients(self):
        other = Company.objects.create(name='Synthetic audit foreign company')
        foreign = Project.objects.create(name='Synthetic foreign audit project', company=other)
        event = GovernanceAudit.objects.create(actor=self.engineer, project=foreign,
            action='survey_submitted', details={'checklist_id': self.checklist.pk})
        self.assertFalse(WorkflowEmailDelivery.objects.filter(source_audit=event).exists())

    def test_wrong_role_cannot_approve_and_trigger_approval_email(self):
        self.submitted()
        WorkflowEmailDelivery.objects.all().delete()
        self.client.force_login(self.engineer)
        response = self.client.post(reverse('quality_review', args=[self.checklist.pk]),
            {'decision': 'approve', 'expected_updated_at': self.checklist.updated_at.isoformat()})
        self.assertIn(response.status_code, (403, 404))
        self.assertFalse(WorkflowEmailDelivery.objects.exists())
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, Checklist.Status.SUBMITTED)

    def test_csrf_failure_cannot_submit_and_queue_notification(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.engineer)
        response = client.post(reverse('custom_checklist_submit', args=[self.checklist.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(WorkflowEmailDelivery.objects.exists())
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status, Checklist.Status.DRAFT)

    def test_revoked_unstarted_assignment_cannot_email_old_engineer(self):
        work = WorkAssignment.objects.create(project=self.project, assigned_by=self.lead,
            assigned_to=self.engineer, site_id='SECURITY-UNSTARTED', latitude=1, longitude=2)
        job = WorkflowEmailDelivery.objects.get(assignment=work)
        replacement = self.person('new-engineer', Profile.Roles.ENGINEER)
        WorkAssignment.objects.filter(pk=work.pk).update(assigned_to=replacement)
        self.assert_cancelled_without_graph(job)

    def test_uncertain_interruption_is_not_requeued_by_failed_retry_or_event_replay(self):
        job = self.submitted()
        WorkflowEmailDelivery.objects.filter(pk=job.pk).update(status='sending',
            lease_id=uuid.uuid4(), lease_expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(recover_interrupted_workflow_emails(), 1)
        self.assertEqual(recover_interrupted_workflow_emails(), 0)
        self.assertEqual(retry_failed_workflow_emails(), 0)
        self.assertEqual(queue_audit_event(job.source_audit), 0)
        with patch('core.workflow_email.GraphMailClient') as graph:
            self.assertFalse(process_next_workflow_email())
        graph.assert_not_called()
        self.assertEqual(WorkflowEmailDelivery.objects.count(), 1)
        job.refresh_from_db()
        self.assertEqual(job.status, 'uncertain')

    def test_daily_excludes_other_company_even_with_forged_active_membership(self):
        other = Company.objects.create(name='Synthetic foreign daily company')
        foreign = self.person('foreign-daily', Profile.Roles.ENGINEER, company=other)
        self.checklist.user = foreign
        self.checklist.save(update_fields=['user'])
        queue_daily_digests(now=datetime(2026, 11, 6, 16, tzinfo=utc.utc))
        self.assertFalse(WorkflowEmailDelivery.objects.filter(recipient=foreign).exists())
        self.assertFalse(WorkflowEmailDelivery.objects.filter(recipient=self.customer).exists())

    def report_asset(self, directory):
        from . import survey_processing as processing
        from .models import ChecklistTemplate
        from .survey_processing_models import (SurveyDrawingSet, SurveyProcessingEvent,
            SurveyProcessingResult, SurveyProcessingRevision)
        template = ChecklistTemplate.objects.create(name='Synthetic security report schema',
            published=True, created_by=self.admin, checklist_required=True,
            definition={'title': 'Synthetic security report', 'sections': [
                {'id': 'general', 'title': 'General', 'fields': [
                    {'id': 'note', 'label': 'Note', 'type': 'text', 'required': False}]}]})
        self.checklist.checklist_template = template
        self.checklist.schema_snapshot = template.definition
        self.checklist.status = Checklist.Status.FINAL
        self.checklist.client_review_required = False
        self.checklist.save()
        snapshot = processing.freeze_data(self.checklist)
        revision = SurveyProcessingRevision.objects.create(checklist=self.checklist, number=1,
            snapshot=snapshot, digest=processing.digest(snapshot), submitted_by=self.engineer)
        payload = {'checklist_items': [], 'findings': [], 'drawing_records': []}
        SurveyProcessingResult.objects.create(revision=revision, payload=payload,
            digest=processing.digest(payload))
        signature = processing.review_digest(payload)
        for actor, action in [(self.engineer, 'engineer_complete'), (self.qa, 'technical_approve')]:
            SurveyProcessingEvent.objects.create(revision=revision, actor=actor, action=action,
                payload={'review_digest': signature})
        WorkflowEmailDelivery.objects.all().delete()
        path = Path(directory) / 'synthetic-security-auth-fixture.pdf'
        path.write_bytes(b'%PDF-1.4\nSynthetic authorization fixture, not drawing accuracy evidence\n')
        asset = SurveyDrawingSet.objects.create(revision=revision, edition=1, released=True,
            geometry={}, review_digest=signature,
            manifest={'pdf': str(path), 'sheets': [{'number': 'SECURITY-1'}]})
        WorkflowEmailDelivery.objects.exclude(recipient=self.customer).delete()
        return asset, WorkflowEmailDelivery.objects.get()

    def test_client_report_access_revoked_after_oauth_prevents_send_and_download(self):
        with tempfile.TemporaryDirectory(dir=settings.FILE_UPLOAD_TEMP_DIR) as directory, \
                override_settings(MEDIA_ROOT=directory):
            asset, job = self.report_asset(directory)
            original = GraphMailClient._token

            def revoked_after_oauth(client):
                token = original(client)
                Checklist.objects.filter(pk=self.checklist.pk).update(status=Checklist.Status.REJECTED)
                return token

            with graph_fixture() as records, patch('core.notification_email.load_config',
                    return_value=GraphMailConfig(TENANT, CLIENT, SECRET)), \
                    patch.object(GraphMailClient, '_token', revoked_after_oauth):
                self.assertTrue(process_next_workflow_email())
            self.assertEqual(len(records), 1, 'Released content must be checked again before send POST')
            job.refresh_from_db()
            self.assertEqual(job.status, 'cancelled')
            self.client.force_login(self.customer)
            response = self.client.get(reverse('survey_processing_output',
                args=[self.checklist.pk, asset.pk, 0, 'pdf']))
            response.close()
            self.assertEqual(response.status_code, 404)

    def test_released_report_record_cannot_be_rewritten_to_change_a_queued_notification(self):
        from .survey_processing_models import SurveyDrawingSet
        with tempfile.TemporaryDirectory(dir=settings.FILE_UPLOAD_TEMP_DIR) as directory, \
                override_settings(MEDIA_ROOT=directory):
            asset, job = self.report_asset(directory)
            with self.assertRaises(ValidationError):
                SurveyDrawingSet.objects.filter(pk=asset.pk).update(released=False)
            asset.refresh_from_db()
            self.assertTrue(asset.released)
            self.assertEqual(job.kind, 'report_released')

    def test_client_report_becomes_stale_during_oauth_and_is_not_emailed(self):
        with tempfile.TemporaryDirectory(dir=settings.FILE_UPLOAD_TEMP_DIR) as directory, \
                override_settings(MEDIA_ROOT=directory):
            asset, job = self.report_asset(directory)
            original = GraphMailClient._token

            def changed_after_oauth(client):
                token = original(client)
                Checklist.objects.filter(pk=self.checklist.pk).update(
                    answer_data={'custom': {'new': 'Synthetic revised human data'}})
                return token

            with graph_fixture() as records, patch('core.notification_email.load_config',
                    return_value=GraphMailConfig(TENANT, CLIENT, SECRET)), \
                    patch.object(GraphMailClient, '_token', changed_after_oauth):
                self.assertTrue(process_next_workflow_email())
            self.assertEqual(len(records), 1)
            job.refresh_from_db()
            self.assertEqual(job.status, 'cancelled')

    def test_report_notification_does_not_make_download_public_or_foreign_project_visible(self):
        with tempfile.TemporaryDirectory(dir=settings.FILE_UPLOAD_TEMP_DIR) as directory, \
                override_settings(MEDIA_ROOT=directory):
            asset, job = self.report_asset(directory)
            with patch('core.workflow_email.GraphMailClient') as graph:
                self.assertTrue(process_next_workflow_email())
            url = reverse('survey_processing_output', args=[self.checklist.pk, asset.pk, 0, 'pdf'])
            self.assertIn('https://testserver' + url, graph.return_value.send.call_args.args[2])
            anonymous = self.client.get(url)
            self.assertEqual(anonymous.status_code, 302)
            other = Company.objects.create(name='Synthetic foreign report company')
            foreign = self.person('foreign-report', Profile.Roles.CLIENT, company=other)
            self.client.force_login(foreign)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.force_login(self.customer)
            allowed = self.client.get(url)
            self.assertEqual(allowed.status_code, 200)
            allowed.close()
