"""Company authority comes from current stored identity, never a cached principal."""
from datetime import timedelta
from io import BytesIO
from pathlib import Path
import tempfile
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .access import accessible_projects, can_access_project, company_id_for, is_super_admin, role_for
from .company_service import grant_membership
from .models import Company, Project, Profile, ProjectInvitation, ProjectMembership, Checklist, ChecklistTemplate, GovernanceAudit, GeoLocation, EvidenceRuleRelease, WorkflowTemplateQualification


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CompanyBoundaryCoreTests(TestCase):
    def setUp(self):
        self.a = Company.objects.create(name='Boundary employer A')
        self.b = Company.objects.create(name='Boundary employer B')
        self.pa = Project.objects.create(name='Boundary project A', company=self.a)
        self.pb = Project.objects.create(name='Boundary project B', company=self.b)
        self.admin = self.person('boundary_admin_a', Profile.Roles.ADMIN, self.pa)
        self.engineer = self.person('boundary_engineer_a', Profile.Roles.ENGINEER, self.pa)
        self.admin_b = self.person('boundary_admin_b', Profile.Roles.ADMIN, self.pb)

    def person(self, name, role, project=None, superuser=False):
        user = User.objects.create_user(name, password='Synthetic-boundary-783!', is_superuser=superuser)
        profile = user.profile
        profile.role = role
        profile.project = project
        profile.company = project.company if project else None
        profile.save()
        if project:
            ProjectMembership.objects.create(user=user, project=project, is_primary=True)
        return user

    def test_cached_company_and_primary_are_not_a_previous_tenant_capability(self):
        self.assertEqual(company_id_for(self.engineer), self.a.pk)
        self.assertTrue(can_access_project(self.engineer, self.pa))
        # A controlled fixture rebind simulates a changed persisted account. It
        # must not leave the in-memory object authorized in its former employer.
        Profile.objects.filter(user=self.engineer).update(company=self.b, project=self.pb)
        ProjectMembership.objects.create(user=self.engineer, project=self.pb)
        self.assertEqual(company_id_for(self.engineer), self.b.pk)
        self.assertEqual(set(accessible_projects(self.engineer).values_list('pk', flat=True)), {self.pb.pk})
        self.assertFalse(can_access_project(self.engineer, self.pa))

    def test_cached_principal_loses_project_access_when_account_is_disabled(self):
        self.assertTrue(can_access_project(self.engineer, self.pa))
        User.objects.filter(pk=self.engineer.pk).update(is_active=False)
        self.assertIsNone(role_for(self.engineer))
        self.assertFalse(can_access_project(self.engineer, self.pa))

    def test_cached_principal_loses_project_access_when_profile_is_locked(self):
        self.assertTrue(can_access_project(self.engineer, self.pa))
        Profile.objects.filter(user=self.engineer).update(is_locked=True)
        self.assertIsNone(role_for(self.engineer))
        self.assertFalse(can_access_project(self.engineer, self.pa))

    def test_cached_superuser_demotion_cannot_keep_company_wide_bypass(self):
        actor = self.person('boundary_global_admin', Profile.Roles.SUPER_ADMIN, superuser=True)
        self.assertTrue(is_super_admin(actor))
        self.assertTrue(can_access_project(actor, self.pb))
        User.objects.filter(pk=actor.pk).update(is_superuser=False)
        self.assertFalse(is_super_admin(actor))
        self.assertIsNone(role_for(actor))
        self.assertFalse(can_access_project(actor, self.pb))

    def test_cross_company_injected_membership_never_grants_access(self):
        ProjectMembership.objects.create(user=self.engineer, project=self.pb)
        self.assertEqual(set(accessible_projects(self.engineer).values_list('pk', flat=True)), {self.pa.pk})

    def test_cached_target_cannot_be_granted_after_persisted_company_change(self):
        _ = self.engineer.profile.company_id
        Profile.objects.filter(user=self.engineer).update(company=self.b)
        before = list(ProjectMembership.objects.filter(user=self.engineer).values('project_id', 'is_active'))
        with self.assertRaises(ValidationError):
            grant_membership(self.admin, self.engineer, self.pa)
        self.assertEqual(list(ProjectMembership.objects.filter(user=self.engineer).values('project_id', 'is_active')), before)
        self.assertEqual(Profile.objects.get(user=self.engineer).company_id, self.b.pk)

    def test_inactive_target_retains_company_affiliation_for_grant_validation(self):
        User.objects.filter(pk=self.engineer.pk).update(is_active=False)
        Profile.objects.filter(user=self.engineer).update(company=self.b)
        self.assertEqual(company_id_for(self.engineer), self.b.pk)
        with self.assertRaises(ValidationError):
            grant_membership(self.admin, self.engineer, self.pa)

    def invitation(self, suffix, company):
        return ProjectInvitation.objects.create(
            token_hash=suffix * 64, email=f'{suffix}-private@example.test',
            role=Profile.Roles.ENGINEER, project=self.pa, company=company,
            created_by=self.admin_b if company == self.b else self.admin,
            expires_at=timezone.now() + timedelta(hours=1))

    def test_scoped_invitation_list_hides_cross_company_snapshot(self):
        own = self.invitation('a', self.a)
        legacy = self.invitation('c', None)
        foreign = self.invitation('b', self.b)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('governance_home'), {'view': 'administration'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.context['invitations'].values_list('pk', flat=True)), {own.pk, legacy.pk})
        self.assertNotContains(response, foreign.email)

    def test_scoped_invitation_revoke_rejects_cross_company_snapshot(self):
        foreign = self.invitation('b', self.b)
        self.client.force_login(self.admin)
        response = self.client.post(reverse('governance_revoke_invite', args=[foreign.pk]))
        self.assertEqual(response.status_code, 404)
        foreign.refresh_from_db()
        self.assertIsNone(foreign.revoked_at)

    def test_legacy_unclassified_company_scope_stays_explicit_and_revocable(self):
        unclassified = Project.objects.create(name='Explicit legacy unclassified project')
        other = Project.objects.create(name='Unassigned legacy unclassified project')
        user = self.person('boundary_legacy_unclassified', Profile.Roles.ENGINEER, unclassified)
        self.assertTrue(can_access_project(user, unclassified))
        self.assertFalse(can_access_project(user, other))
        ProjectMembership.objects.filter(user=user, project=unclassified).update(is_active=False)
        self.assertFalse(can_access_project(user, unclassified))

    def release_affiliations(self):
        ProjectMembership.objects.filter(project=self.pa).update(is_active=False, is_primary=False)
        Profile.objects.filter(project=self.pa).update(project=None)
        Project.objects.filter(pk=self.pa.pk).update(administrator=None)
        self.pa.refresh_from_db()
        actor = self.person('boundary_reclassification_super', Profile.Roles.SUPER_ADMIN, superuser=True)
        self.client.force_login(actor)

    def test_reclassification_cannot_transfer_retained_survey_answers_to_another_company(self):
        record = Checklist.objects.create(user=self.engineer, project=self.pa, site_id='RETAINED-A',
            status=Checklist.Status.FINAL, answer_data={'condition': 'Preserved A answer'},
            review_history=[{'action': 'Synthetic A approval'}])
        self.release_affiliations()
        response = self.client.post(reverse('governance_project_company', args=[self.pa.pk]), {'company': self.b.pk})
        self.assertEqual(response.status_code, 409)
        self.pa.refresh_from_db(); record.refresh_from_db()
        self.assertEqual(self.pa.company_id, self.a.pk)
        self.assertEqual(record.answer_data, {'condition': 'Preserved A answer'})
        self.assertEqual(record.review_history, [{'action': 'Synthetic A approval'}])

    def test_reclassification_cannot_transfer_retained_company_audit_history(self):
        self.release_affiliations()
        event = GovernanceAudit.objects.create(actor=self.admin, project=self.pa,
            action='retained_company_a_history', details={'note': 'Company A private history'})
        response = self.client.post(reverse('governance_project_company', args=[self.pa.pk]), {'company': self.b.pk})
        self.assertEqual(response.status_code, 409)
        self.pa.refresh_from_db(); event.refresh_from_db()
        self.assertEqual(self.pa.company_id, self.a.pk)
        self.assertEqual(event.details, {'note': 'Company A private history'})

    def test_reclassification_cannot_transfer_legacy_invitation_history(self):
        invitation = self.invitation('c', None)
        self.release_affiliations()
        response = self.client.post(reverse('governance_project_company', args=[self.pa.pk]), {'company': self.b.pk})
        self.assertEqual(response.status_code, 409)
        self.pa.refresh_from_db(); invitation.refresh_from_db()
        self.assertEqual(self.pa.company_id, self.a.pk)
        self.assertIsNone(invitation.company_id)
        self.assertIsNone(invitation.revoked_at)

    def test_explicit_company_change_of_a_truly_unused_project_remains_possible(self):
        project = Project.objects.create(name='Unused explicitly classified fixture', company=self.a)
        self.release_affiliations()
        response = self.client.post(reverse('governance_project_company', args=[project.pk]), {'company': self.b.pk})
        self.assertEqual(response.status_code, 302)
        project.refresh_from_db()
        self.assertEqual(project.company_id, self.b.pk)

    def test_bound_private_template_and_branding_cannot_follow_empty_project_to_company_b(self):
        from PIL import Image
        from .template_views import template_scope
        with tempfile.TemporaryDirectory(prefix='company-template-boundary-', dir=Path(__file__).resolve().parents[2]/'.local') as media:
            with override_settings(MEDIA_ROOT=media):
                definition = {'title': 'Private A template', 'sections': [
                    {'id': 'section-a', 'title': 'Private A section', 'fields': [
                        {'id': 'condition-a', 'label': 'A private requirement', 'type': 'text'}]}]}
                template = ChecklistTemplate.objects.create(name='Company A private template',
                    created_by=self.admin, definition=definition)
                image = BytesIO(); Image.new('RGB', (12, 12), 'blue').save(image, format='PNG')
                expected = image.getvalue()
                template.company_logo.save('private-company-a.png', ContentFile(expected), save=True)
                template.published = True; template.save(update_fields=['published'])
                project = Project.objects.create(name='No-work A project with private template',
                    company=self.a, checklist_template=template)
                actor = self.person('template_transfer_super', Profile.Roles.SUPER_ADMIN, superuser=True)
                self.client.force_login(actor)
                response = self.client.post(reverse('governance_project_company', args=[project.pk]),
                    {'company': self.b.pk})
                project.refresh_from_db()
                # On the old implementation this succeeds after the company
                # transfer and makes A's private template a managed B asset.
                if response.status_code == 302:
                    grant_membership(actor, self.admin_b, project)
                self.client.force_login(self.admin_b)
                self.assertFalse(template_scope(self.admin_b).filter(pk=template.pk).exists())
                logo = self.client.get(reverse('checklist_template_logo', args=[template.pk, 'company']))
                self.assertEqual(logo.status_code, 404)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(project.company_id, self.a.pk)
                self.assertEqual(project.checklist_template_id, template.pk)
                template.refresh_from_db()
                self.assertEqual(template.definition, definition)
                with template.company_logo.open('rb') as saved:
                    self.assertEqual(saved.read(), expected)

    def attempt_standalone_company_transfer(self, project):
        actor = self.person('standalone_record_boundary_super', Profile.Roles.SUPER_ADMIN, superuser=True)
        self.client.force_login(actor)
        return self.client.post(reverse('governance_project_company', args=[project.pk]), {'company': self.b.pk})

    def test_retained_site_location_cannot_transfer_to_another_company(self):
        project = Project.objects.create(name='A project with location only', company=self.a)
        location = GeoLocation.objects.create(project=project, created_by=self.admin,
            name='Company A private site location', latitude='24.5', longitude='46.5',
            notes='Preserve A site details')
        response = self.attempt_standalone_company_transfer(project)
        self.assertEqual(response.status_code, 409)
        project.refresh_from_db(); location.refresh_from_db()
        self.assertEqual(project.company_id, self.a.pk)
        self.assertEqual(location.latitude, Decimal('24.5'))
        self.assertEqual(location.longitude, Decimal('46.5'))
        self.assertEqual(location.notes, 'Preserve A site details')

    def test_retained_evidence_rule_release_cannot_transfer_to_another_company(self):
        project = Project.objects.create(name='A project with rule release only', company=self.a)
        references = [{'reference': 'Company A private evidence reference'}]
        record = EvidenceRuleRelease.objects.create(project=project, version=1,
            references=references, digest='d'*64, published_by=self.admin, reason='Synthetic A rule history')
        response = self.attempt_standalone_company_transfer(project)
        self.assertEqual(response.status_code, 409)
        project.refresh_from_db(); record.refresh_from_db()
        self.assertEqual(project.company_id, self.a.pk)
        self.assertEqual(record.references, references)

    def test_retained_qualification_cannot_transfer_to_another_company(self):
        project = Project.objects.create(name='A project with qualification only', company=self.a)
        template = ChecklistTemplate.objects.create(name='A qualification template', created_by=self.admin,
            definition={'title': 'A criteria', 'sections': [{'id': 's', 'title': 'A section',
                'fields': [{'id': 'f', 'label': 'A criterion', 'type': 'text'}]}]})
        record = WorkflowTemplateQualification.objects.create(project=project, template=template,
            workflow_type=Checklist.WorkflowType.TELECOM_SURVEY, definition_digest='d'*64,
            criteria_reference='Company A private criteria', inspection_method='A reviewed method',
            reviewed_by=self.admin, reason='Synthetic A qualification history')
        response = self.attempt_standalone_company_transfer(project)
        self.assertEqual(response.status_code, 409)
        project.refresh_from_db(); record.refresh_from_db()
        self.assertEqual(project.company_id, self.a.pk)
        self.assertEqual(record.criteria_reference, 'Company A private criteria')
        self.assertEqual(record.inspection_method, 'A reviewed method')
