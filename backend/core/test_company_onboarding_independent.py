"""Independent saved-record contracts for controlled company onboarding."""
import json
import uuid
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import (Company, CompanyApplication, GovernanceAudit, IndustryCatalog,
                     Profile, Project, ProjectInvitation)
from .onboarding_service import (apply_application, invite_application,
                                 provision_application, review_application)


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentCompanyOnboardingTests(TestCase):
    def setUp(self):
        self.industry = IndustryCatalog.objects.get(code='telecom')
        self.owner = self.person('onboarding_owner', Profile.Roles.SUPER_ADMIN, True)
        self.admin = self.person('onboarding_admin', Profile.Roles.ADMIN)

    def person(self, name, role, owner=False):
        user = User.objects.create_user(name, email=name+'@example.test', password='Fixture-Onboard-944!')
        User.objects.filter(pk=user.pk).update(is_superuser=owner, is_staff=owner)
        profile=user.profile; profile.role=role
        if role == Profile.Roles.ADMIN:
            profile.company=Company.objects.create(name='Existing administrative tenant')
            profile.admin_industry=self.industry
        profile.save(); user.refresh_from_db()
        return user

    def apply(self, suffix='A', key=None):
        return apply_application(self.owner, request_key=key or uuid.uuid4(),
            name='Independent applicant '+suffix, email='applicant-'+suffix.lower()+'@example.test',
            industry=self.industry)

    def ready(self, suffix='A'):
        application=self.apply(suffix)
        review_application(self.owner, application.pk, approve=True, reason='Checked contact and industry')
        provision_application(self.owner, application.pk)
        return application

    def csrf_client(self, user=None):
        client=Client(enforce_csrf_checks=True)
        client.get('/login/')
        if user: client.force_login(user)
        return client

    def post(self, client, route, data, args=None):
        return client.post(reverse(route,args=args), data,
            HTTP_X_CSRFTOKEN=client.cookies[settings.CSRF_COOKIE_NAME].value)

    def test_application_replay_is_idempotent_and_payload_change_does_not_mutate(self):
        key=uuid.uuid4(); first=self.apply(key=key); second=self.apply(key=key)
        self.assertEqual(first.pk,second.pk)
        self.assertEqual(CompanyApplication.objects.count(),1)
        with self.assertRaises(ValidationError):
            apply_application(self.owner,request_key=key,name='Changed company',
                              email='different@example.test',industry=self.industry)
        first.refresh_from_db(); self.assertEqual(first.name,'Independent applicant A')
        self.assertIsNone(first.company_id)

    def test_provision_requires_human_review_and_is_replay_safe(self):
        application=self.apply()
        before=Company.objects.count()
        with self.assertRaises(ValidationError): provision_application(self.owner,application.pk)
        self.assertEqual(Company.objects.count(),before)
        review_application(self.owner,application.pk,approve=True,reason='Verified contact')
        first=provision_application(self.owner,application.pk)
        second=provision_application(self.owner,application.pk)
        self.assertEqual(first.company_id,second.company_id)
        self.assertEqual(Company.objects.count(),before+1)
        self.assertEqual(Project.objects.count(),0)

    def test_separate_companies_receive_separate_project_free_admin_invitations(self):
        results=[]
        for suffix in ['A','B']:
            app=self.ready(suffix)
            app,token=invite_application(self.owner,app.pk)
            self.assertTrue(token)
            invitation=ProjectInvitation.objects.get(pk=app.invitation_id)
            self.assertEqual(invitation.company_id,app.company_id)
            self.assertEqual(invitation.admin_industry_id,self.industry.pk)
            self.assertEqual(invitation.role,Profile.Roles.ADMIN)
            self.assertIsNone(invitation.project_id)
            self.assertNotEqual(invitation.token_hash,token)
            replay,replayed_token=invite_application(self.owner,app.pk)
            self.assertEqual(replay.invitation_id,invitation.pk)
            self.assertIsNone(replayed_token)
            results.append((app.company_id,invitation.pk))
        self.assertNotEqual(results[0][0],results[1][0])
        self.assertNotEqual(results[0][1],results[1][1])
        self.assertEqual(ProjectInvitation.objects.count(),2)

    def test_invitation_acceptance_preserves_company_and_industry_and_no_global_authority(self):
        app=self.ready(); app,token=invite_application(self.owner,app.pk)
        client=self.csrf_client()
        response=self.post(client,'governance_accept_invite',{
            'username':'independent_new_company_admin','password1':'Company-Fixture-827!',
            'password2':'Company-Fixture-827!','email':app.email},args=[token])
        self.assertEqual(response.status_code,302)
        user=User.objects.get(username='independent_new_company_admin')
        self.assertFalse(user.is_staff); self.assertFalse(user.is_superuser)
        self.assertEqual(user.profile.company_id,app.company_id)
        self.assertEqual(user.profile.admin_industry_id,self.industry.pk)
        self.assertEqual(user.profile.role,Profile.Roles.ADMIN)
        self.assertIsNone(user.profile.project_id)
        self.assertEqual(Project.objects.count(),0)

    def test_customer_and_forged_platform_role_cannot_create_or_mutate_application(self):
        application=self.apply()
        impostor=self.person('onboarding_fake_owner',Profile.Roles.SUPER_ADMIN)
        for actor in [self.admin,impostor]:
            with self.subTest(actor=actor.username):
                with self.assertRaises(PermissionDenied):
                    apply_application(actor,request_key=uuid.uuid4(),name='Forbidden',
                                      email='forbidden@example.test',industry=self.industry)
                with self.assertRaises(PermissionDenied):
                    review_application(actor,application.pk,approve=True)
                with self.assertRaises(PermissionDenied): provision_application(actor,application.pk)
                with self.assertRaises(PermissionDenied): invite_application(actor,application.pk)
        self.assertEqual(CompanyApplication.objects.count(),1)
        self.assertEqual(ProjectInvitation.objects.count(),0)

    def test_current_platform_revocation_is_rechecked_with_cached_actor(self):
        application=self.apply(); self.owner.profile
        User.objects.filter(pk=self.owner.pk).update(is_superuser=False)
        with self.assertRaises(PermissionDenied):
            review_application(self.owner,application.pk,approve=True)
        application.refresh_from_db(); self.assertEqual(application.status,'applied')

    def test_rejected_application_cannot_be_provisioned_or_invited(self):
        application=self.apply()
        review_application(self.owner,application.pk,approve=False,reason='Contact not verified')
        with self.assertRaises(ValidationError): provision_application(self.owner,application.pk)
        with self.assertRaises(ValidationError): invite_application(self.owner,application.pk)
        application.refresh_from_db(); self.assertEqual(application.status,'rejected')
        self.assertIsNone(application.company_id); self.assertIsNone(application.invitation_id)

    def test_disabled_industry_cannot_be_used_to_provision_or_invite(self):
        application=self.apply()
        review_application(self.owner,application.pk,approve=True)
        IndustryCatalog.objects.filter(pk=self.industry.pk).update(is_active=False)
        with self.assertRaises(ValidationError): provision_application(self.owner,application.pk)
        application.refresh_from_db(); self.assertIsNone(application.company_id)

    def test_existing_company_is_never_claimed_by_applicant_name(self):
        application=self.apply()
        review_application(self.owner,application.pk,approve=True)
        occupied=Company.objects.create(name=application.name)
        with self.assertRaises(ValidationError): provision_application(self.owner,application.pk)
        application.refresh_from_db(); self.assertIsNone(application.company_id)
        self.assertTrue(Company.objects.filter(pk=occupied.pk).exists())

    def test_audit_failure_rolls_back_company_provision(self):
        application=self.apply()
        review_application(self.owner,application.pk,approve=True)
        before=Company.objects.count()
        with patch.object(GovernanceAudit.objects,'create',side_effect=RuntimeError('Isolated audit outage')):
            with self.assertRaises(RuntimeError): provision_application(self.owner,application.pk)
        application.refresh_from_db()
        self.assertIsNone(application.company_id)
        self.assertEqual(Company.objects.count(),before)
        self.assertEqual(application.status,'reviewed')

    def test_audits_record_actor_and_no_invitation_token(self):
        application=self.ready(); application,token=invite_application(self.owner,application.pk)
        events=GovernanceAudit.objects.filter(actor=self.owner)
        self.assertGreaterEqual(events.count(),4)
        content=json.dumps(list(events.values_list('details',flat=True)))
        self.assertNotIn(token,content)
        self.assertNotIn(ProjectInvitation.objects.get(pk=application.invitation_id).token_hash,content)
        self.assertIn(str(application.pk),content)

    def test_http_boundaries_csrf_and_saved_data(self):
        owner=self.csrf_client(self.owner); admin=self.csrf_client(self.admin)
        self.assertEqual(owner.get(reverse('company_onboarding')).status_code,200)
        self.assertEqual(admin.get(reverse('company_onboarding')).status_code,403)
        payload={'request_key':str(uuid.uuid4()),'name':'Independent HTTP company',
                 'email':'http-company@example.test','industry':self.industry.pk}
        self.assertEqual(owner.post(reverse('company_onboarding_apply'),payload).status_code,403)
        response=self.post(owner,'company_onboarding_apply',payload)
        self.assertEqual(response.status_code,302)
        application=CompanyApplication.objects.get(email=payload['email'])
        response=self.post(admin,'company_onboarding_action',{'action':'approve'},[application.pk])
        self.assertEqual(response.status_code,403)
        response=self.post(owner,'company_onboarding_action',{'action':'approve','review_note':'Checked'},[application.pk])
        self.assertEqual(response.status_code,302)
        application.refresh_from_db(); self.assertEqual(application.status,'reviewed')
        self.assertContains(owner.get(reverse('company_onboarding_detail',args=[application.pk])),application.name)
