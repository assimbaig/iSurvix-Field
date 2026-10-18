"""Industry-bound administration is enforced behind every project selector."""
from django.test import TestCase,override_settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from .models import Profile,Project,Company,IndustryCatalog,ProjectMembership
from .access import accessible_projects
from .company_service import grant_membership
from .governance_forms import InvitationForm

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False)
class AdminIndustryTests(TestCase):
    def setUp(self):
        self.telecom=IndustryCatalog.objects.get_or_create(code='telecom',defaults={'name':'Telecom'})[0]
        self.construction=IndustryCatalog.objects.get_or_create(code='construction',defaults={'name':'Construction'})[0]
        self.company=Company.objects.create(name='Synthetic industry company')
        self.a=Project.objects.create(name='Synthetic telecom',company=self.company,industry='telecom')
        self.b=Project.objects.create(name='Synthetic construction',company=self.company,industry='construction')
        self.super=User.objects.create_user('industry_super',is_superuser=True)
        self.admin=User.objects.create_user('industry_admin')
        self.admin.profile.role=Profile.Roles.ADMIN
        self.admin.profile.company=self.company
        self.admin.profile.save()
        grant_membership(self.super,self.admin,self.a,True)
        grant_membership(self.super,self.admin,self.b)
    def test_binding_filters_prior_grants_and_cross_industry_service_grants(self):
        self.assertEqual(accessible_projects(self.admin).count(),2)
        self.admin.profile.admin_industry=self.telecom
        self.admin.profile.save(update_fields=['admin_industry'])
        self.assertEqual(list(accessible_projects(self.admin)),[self.a])
        with self.assertRaises(ValidationError):grant_membership(self.super,self.admin,self.b)
        self.assertTrue(ProjectMembership.objects.filter(user=self.admin,project=self.b,is_active=True).exists())
    def test_only_super_can_bind_and_admin_cannot_self_change(self):
        self.client.force_login(self.admin)
        url=reverse('governance_admin_industry',args=[self.admin.pk])
        self.assertEqual(self.client.post(url,{'admin_industry':self.telecom.pk}).status_code,403)
        self.client.force_login(self.super)
        self.assertEqual(self.client.post(url,{'admin_industry':self.telecom.pk}).status_code,302)
        self.admin.profile.refresh_from_db()
        self.assertEqual(self.admin.profile.admin_industry_id,self.telecom.pk)
    def test_new_admin_invitation_requires_matching_industry(self):
        base={'email':'synthetic_invite@example.test','role':Profile.Roles.ADMIN,'project':self.a.pk}
        self.assertFalse(InvitationForm(base,actor=self.super).is_valid())
        self.assertFalse(InvitationForm({**base,'admin_industry':self.construction.pk},actor=self.super).is_valid())
        self.assertTrue(InvitationForm({**base,'admin_industry':self.telecom.pk},actor=self.super).is_valid())
        self.admin.profile.admin_industry=self.telecom
        self.admin.profile.save(update_fields=['admin_industry'])
        form=InvitationForm({'email':'synthetic_member@example.test','role':Profile.Roles.ENGINEER,'project':self.b.pk},actor=self.admin)
        self.assertFalse(form.is_valid())

    def test_admin_invitation_acceptance_keeps_industry_and_scope(self):
        from .models import ProjectInvitation
        import hashlib
        from datetime import timedelta
        from django.utils import timezone
        token='synthetic-industry-invitation-token'
        invitation=ProjectInvitation.objects.create(token_hash=hashlib.sha256(token.encode()).hexdigest(),email='bound_admin@example.test',role=Profile.Roles.ADMIN,project=self.a,admin_industry=self.telecom,created_by=self.super,expires_at=timezone.now()+timedelta(hours=1))
        self.client.logout()
        response=self.client.post(reverse('governance_accept_invite',args=[token]),{'username':'new_industry_admin','email':invitation.email,'password1':'SyntheticFixture-4830!','password2':'SyntheticFixture-4830!'})
        self.assertEqual(response.status_code,302)
        user=User.objects.get(username='new_industry_admin')
        self.assertEqual(user.profile.admin_industry_id,self.telecom.pk)
        self.assertEqual(list(accessible_projects(user)),[self.a])
        with self.assertRaises(ValidationError):grant_membership(self.super,user,self.b)

    def test_upgrade_binds_unambiguous_and_fails_closed_ambiguous_admin(self):
        import importlib
        from django.apps import apps
        single=User.objects.create_user('single_industry_legacy')
        single.profile.role=Profile.Roles.ADMIN
        single.profile.project=self.a
        single.profile.company=self.company
        single.profile.save()
        migration=importlib.import_module('core.migrations.0030_admin_industry')
        migration.bind_existing_admins(apps,None)
        single.profile.refresh_from_db()
        self.assertEqual(single.profile.admin_industry_id,self.telecom.pk)
        self.assertFalse(single.profile.admin_industry_pending)
        self.admin.profile.refresh_from_db()
        self.assertTrue(self.admin.profile.admin_industry_pending)
        self.assertFalse(accessible_projects(self.admin).exists())
        self.client.force_login(self.super)
        response=self.client.post(reverse('governance_admin_industry',args=[self.admin.pk]),{'admin_industry':self.telecom.pk})
        self.assertEqual(response.status_code,302)
        self.assertEqual(list(accessible_projects(self.admin)),[self.a])

    def test_binding_is_csrf_guarded_audited_and_invite_cannot_change_issuer_industry(self):
        from django.test import Client
        from .models import GovernanceAudit,ProjectInvitation
        strict=Client(enforce_csrf_checks=True)
        strict.force_login(self.super)
        url=reverse('governance_admin_industry',args=[self.admin.pk])
        self.assertEqual(strict.post(url,{'admin_industry':self.telecom.pk}).status_code,403)
        self.client.force_login(self.super)
        self.assertEqual(self.client.post(url,{'admin_industry':self.telecom.pk}).status_code,302)
        event=GovernanceAudit.objects.get(action='admin_industry_bound')
        self.assertEqual(event.actor_id,self.super.pk)
        self.assertEqual(event.details['administrator_id'],self.admin.pk)
        self.client.force_login(self.admin)
        response=self.client.post(reverse('governance_invite'),{'email':'synthetic_engineer@example.test','role':Profile.Roles.ENGINEER,'project':self.a.pk,'admin_industry':self.construction.pk})
        self.assertEqual(response.status_code,200)
        self.admin.profile.refresh_from_db()
        self.assertEqual(self.admin.profile.admin_industry_id,self.telecom.pk)
        self.assertIsNone(ProjectInvitation.objects.get(email='synthetic_engineer@example.test').admin_industry_id)
