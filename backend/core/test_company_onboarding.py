"""Company intake and replay contracts against isolated persisted records."""
import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Company, GovernanceAudit, IndustryCatalog, Profile, Project, ProjectInvitation


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CompanyOnboardingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser('intake-owner', 'owner@example.test', 'Fixture849!')
        self.industry = IndustryCatalog.objects.get(code='telecom')
        self.client.force_login(self.owner)

    def apply(self, name='Synthetic onboarding A', email='admin-a@example.test', key=None):
        from .onboarding_service import apply_application
        return apply_application(self.owner, request_key=key or uuid.uuid4(), name=name,
                                 email=email, industry=self.industry)

    def provision(self, application):
        from .onboarding_service import review_application, provision_application
        review_application(self.owner, application.pk, approve=True)
        return provision_application(self.owner, application.pk)

    def test_two_companies_remain_separate_through_invite_acceptance(self):
        from .onboarding_service import invite_application
        for index in (1, 2):
            application = self.provision(self.apply(f'Synthetic company {index}', f'admin{index}@example.test'))
            application, token = invite_application(self.owner, application.pk)
            response = self.client.post(reverse('governance_accept_invite', args=[token]), {
                'username': f'onboarded-admin-{index}', 'email': application.email,
                'password1': 'Synthetic-credential-849!', 'password2': 'Synthetic-credential-849!',
            })
            self.assertEqual(response.status_code, 302)
            person = User.objects.get(username=f'onboarded-admin-{index}')
            self.assertEqual(person.profile.company_id, application.company_id)
            self.assertEqual(person.profile.admin_industry_id, self.industry.pk)
            self.assertEqual(person.profile.role, Profile.Roles.ADMIN)
            self.assertFalse(person.is_staff or person.is_superuser)
            self.client.force_login(self.owner)
        self.assertEqual(Company.objects.filter(name__startswith='Synthetic company').count(), 2)
        self.assertEqual(Project.objects.count(), 0)

    def test_replayed_apply_and_each_transition_create_one_company_and_invitation(self):
        from .onboarding_service import invite_application
        from .onboarding_models import CompanyApplication
        key = uuid.uuid4()
        first = self.apply(key=key)
        self.assertEqual(self.apply(key=key).pk, first.pk)
        self.provision(first)
        self.provision(first)
        invited, token = invite_application(self.owner, first.pk)
        replay, replay_token = invite_application(self.owner, first.pk)
        self.assertTrue(token)
        self.assertIsNone(replay_token)
        self.assertEqual(invited.invitation_id, replay.invitation_id)
        self.assertEqual(CompanyApplication.objects.count(), 1)
        self.assertEqual(Company.objects.count(), 1)
        self.assertEqual(ProjectInvitation.objects.count(), 1)
        for action in ['company_application.applied', 'company_application.reviewed',
                       'company_application.provisioned', 'company_application.invited']:
            self.assertEqual(GovernanceAudit.objects.filter(action=action).count(), 1)

    def test_changed_replay_payload_is_rejected(self):
        key = uuid.uuid4()
        self.apply(key=key)
        with self.assertRaises(ValidationError):
            self.apply(key=key, email='other@example.test')

    def test_normalized_pending_name_does_not_attach_other_contact(self):
        application = self.apply(name='  Synthetic   Company  ')
        self.assertEqual(self.apply(name='synthetic company').pk, application.pk)
        with self.assertRaises(ValidationError):
            self.apply(name='Synthetic Company', email='foreign@example.test')

    def test_existing_company_cannot_be_claimed_by_application(self):
        Company.objects.create(name='Already owned company')
        with self.assertRaises(ValidationError):
            self.apply(name='already owned company')

    def test_unreviewed_application_cannot_provision_or_invite(self):
        from .onboarding_service import provision_application, invite_application
        application = self.apply()
        for service in (provision_application, invite_application):
            with self.assertRaises(ValidationError):
                service(self.owner, application.pk)
        self.assertFalse(Company.objects.exists())

    def test_rejection_preserves_request_and_allows_new_application(self):
        from .onboarding_service import review_application
        application = self.apply()
        with self.assertRaises(ValidationError):
            review_application(self.owner, application.pk, approve=False)
        review_application(self.owner, application.pk, approve=False, reason='Need company evidence')
        self.assertNotEqual(self.apply().pk, application.pk)
        application.refresh_from_db()
        self.assertEqual(application.status, 'rejected')
        self.assertFalse(Company.objects.exists())

    def test_customer_admin_and_stale_owner_are_denied(self):
        from .onboarding_service import apply_application
        admin = User.objects.create_user('intake-admin')
        admin.profile.role = Profile.Roles.ADMIN
        admin.profile.save()
        for person in (admin, self.owner):
            if person.pk == self.owner.pk:
                User.objects.filter(pk=person.pk).update(is_superuser=False)
            with self.assertRaises(PermissionDenied):
                apply_application(person, request_key=uuid.uuid4(), name='Forbidden intake',
                                  email='forbidden@example.test', industry=self.industry)
        self.assertFalse(Company.objects.exists())

    def test_audit_failure_rolls_back_company_provisioning(self):
        from .onboarding_service import provision_application, review_application
        application = self.apply()
        review_application(self.owner, application.pk, approve=True)
        with patch('core.onboarding_service.audit', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                provision_application(self.owner, application.pk)
        self.assertFalse(Company.objects.exists())
        application.refresh_from_db()
        self.assertEqual(application.status, 'reviewed')

    def test_owner_http_intake_and_status_screen(self):
        self.assertContains(self.client.get(reverse('governance_home')), reverse('company_onboarding'))
        payload = {'request_key': str(uuid.uuid4()), 'name': 'Synthetic HTTP company',
                   'email': 'http-admin@example.test', 'industry': self.industry.pk}
        response = self.client.post(reverse('company_onboarding_apply'), payload)
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(response.url), 'Synthetic HTTP company')
        self.assertContains(self.client.get(reverse('company_onboarding')), 'Synthetic HTTP company')

    def test_http_authority_override_is_rejected_without_side_effect(self):
        response = self.client.post(reverse('company_onboarding_apply'), {
            'request_key': str(uuid.uuid4()), 'name': 'Synthetic override company',
            'email': 'override@example.test', 'industry': self.industry.pk, 'is_superuser': '1',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Company.objects.exists())

    def test_inactive_industry_blocks_provisioning_without_company(self):
        from .onboarding_service import provision_application, review_application
        application = self.apply()
        review_application(self.owner, application.pk, approve=True)
        IndustryCatalog.objects.filter(pk=self.industry.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            provision_application(self.owner, application.pk)
        self.assertFalse(Company.objects.exists())
