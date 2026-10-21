"""Real HTTP regression for saved independent activities before reviewer setup."""
from copy import deepcopy

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Checklist, ChecklistTemplate, Company, Profile, Project, ProjectMembership
from .revision_models import ChecklistReviewPolicy


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ReviewPolicyEmptyStateTests(TestCase):
    def setUp(self):
        company = Company.objects.create(name='Synthetic review setup company')
        source = ChecklistTemplate.objects.create(name='Synthetic review setup checklist', published=True,
            definition={'title': 'Synthetic setup', 'sections': [{'id': 'general', 'title': 'General',
                'fields': [{'id': 'note', 'label': 'Recorded note', 'type': 'text'}]}]})
        self.project = Project.objects.create(name='Synthetic review setup project', company=company,
                                              checklist_template=source, review_layers=3)
        self.admin = self.person('admin', Profile.Roles.ADMIN)
        self.engineer = self.person('engineer', Profile.Roles.ENGINEER)
        self.quality = self.person('qa', Profile.Roles.QUALITY_ENGINEER)
        self.lead = self.person('lead', Profile.Roles.TEAM_LEAD)
        self.project.administrator = self.admin
        self.project.save(update_fields=['administrator'])
        self.checklist = Checklist.objects.create(project=self.project, user=self.engineer,
            site_id='SYN-REVIEW-NOT-ASSIGNED', governance_mode='independent',
            answer_data={'custom': {'note': 'Preserved engineer observation'}})
        self.url = reverse('roadmap_activity', args=[self.checklist.pk])

    def person(self, suffix, role):
        user = User.objects.create_user('review_setup_' + suffix)
        user.profile.role = role
        user.profile.company = self.project.company
        user.profile.project = self.project
        user.profile.save()
        ProjectMembership.objects.create(project=self.project, user=user, is_active=True, is_primary=True)
        return user

    def test_admin_can_open_missing_policy_and_find_working_configuration(self):
        original = deepcopy(self.checklist.answer_data)
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertContains(response, 'No review team is assigned.', status_code=200)
        self.assertContains(response, 'Not recorded. Assign a review team first.')
        self.assertContains(response, '<dt>Client release</dt><dd>Not assigned</dd>', html=True)
        self.assertContains(response, 'Save review team for this activity')
        self.assertFalse(ChecklistReviewPolicy.objects.filter(checklist=self.checklist).exists())
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.answer_data, original)

        response = self.client.post(reverse('roadmap_policy_assign', args=[self.checklist.pk]), {
            'l2_reviewer': self.quality.pk, 'l3_approver': self.lead.pk,
            'reason': 'Named QA and Team Lead assigned for this synthetic activity.',
            'expected_updated_at': self.checklist.updated_at.isoformat(),
        })
        self.assertRedirects(response, self.url)
        policy = ChecklistReviewPolicy.objects.get(checklist=self.checklist)
        self.assertEqual((policy.l2_reviewer_id, policy.l3_approver_id),
                         (self.quality.pk, self.lead.pk))
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.answer_data, original)

    def test_assigned_engineer_sees_missing_policy_without_admin_controls(self):
        self.client.force_login(self.engineer)
        response = self.client.get(self.url)
        self.assertContains(response, 'No review team is assigned.', status_code=200)
        self.assertNotContains(response, 'Save review team for this activity')
        self.assertFalse(ChecklistReviewPolicy.objects.filter(checklist=self.checklist).exists())

    def test_existing_policy_reason_fallback_remains_visible(self):
        ChecklistReviewPolicy.objects.create(checklist=self.checklist, workflow_version=2,
            l2_reviewer=self.quality, l3_approver=self.lead, configured_by=self.admin,
            reason='Existing assignment reason must remain visible.', applicability_reason='')
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertContains(response, 'Existing assignment reason must remain visible.', status_code=200)
        self.assertNotContains(response, 'No review team is assigned.')
