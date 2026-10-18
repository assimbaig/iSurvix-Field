"""Independent tests: Client onboarding belongs exclusively to scoped Project Admin."""
import hashlib
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from django.utils import timezone
from .models import Company,IndustryCatalog,Project,Profile,ClientOrganization,ProjectInvitation,ProjectMembership
from .governance_views import issue_guard

@override_settings(SECRET_KEY='synthetic-client-boundary-only',ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SuperClientBoundaryTests(TestCase):
    def setUp(self):
        self.telecom=IndustryCatalog.objects.get(code='telecom')
        self.construction=IndustryCatalog.objects.get(code='construction')
        self.company=Company.objects.create(name='Synthetic owner company')
        self.foreign_company=Company.objects.create(name='Synthetic foreign company')
        self.project=Project.objects.create(name='Synthetic client project',company=self.company,industry='telecom')
        self.second=Project.objects.create(name='Synthetic additional project',company=self.company,industry='telecom')
        self.foreign=Project.objects.create(name='Synthetic foreign project',company=self.foreign_company,industry='telecom')
        self.admin=self.person('client_scope_admin',Profile.Roles.ADMIN,self.project)
        self.super=self.person('client_scope_super',Profile.Roles.SUPER_ADMIN,superuser=True)
        self.reviewer=self.person('client_scope_reviewer',Profile.Roles.CLIENT,self.project)
        self.engineer=self.person('client_scope_engineer',Profile.Roles.ENGINEER,self.project)
    def person(self,name,role,project=None,superuser=False):
        user=User.objects.create_user(name,email=name+'@example.test',is_superuser=superuser)
        user.profile.role=role;user.profile.project=project;user.profile.company=project.company if project else None
        if role==Profile.Roles.ADMIN:user.profile.admin_industry=self.telecom
        user.profile.save();return user
    def test_super_cannot_create_client_organization_or_invite_client(self):
        self.client.force_login(self.super)
        self.assertEqual(self.client.post(reverse('governance_company'),{'name':'Forbidden client','company':self.company.pk,'industry':self.telecom.pk,'created_by':self.admin.pk}).status_code,403)
        self.assertFalse(ClientOrganization.objects.exists())
        response=self.client.post(reverse('governance_invite'),{'email':'forged-client@example.test','role':Profile.Roles.CLIENT,'project':self.project.pk})
        self.assertIn(response.status_code,(400,403));self.assertFalse(ProjectInvitation.objects.exists())
        with self.assertRaises(PermissionDenied):issue_guard(self.super,self.project,Profile.Roles.CLIENT)
    def test_legacy_super_client_bearer_link_is_unusable_and_cannot_create_account(self):
        token='synthetic-super-client-token-0001'
        invitation=ProjectInvitation.objects.create(token_hash=hashlib.sha256(token.encode()).hexdigest(),email='legacy-client@example.test',role=Profile.Roles.CLIENT,project=self.project,created_by=self.super,expires_at=timezone.now()+timedelta(days=1))
        url=reverse('governance_accept_invite',args=[token])
        public=Client()
        self.assertEqual(public.get(url).status_code,404)
        self.assertEqual(public.post(url,{'username':'forbidden_legacy_client','email':invitation.email,'password1':'Synthetic-only-test-password-821!','password2':'Synthetic-only-test-password-821!'}).status_code,404)
        invitation.refresh_from_db();self.assertIsNone(invitation.accepted_at)
        self.assertFalse(User.objects.filter(username='forbidden_legacy_client').exists())
    def test_super_cannot_add_client_membership_or_convert_engineer_role(self):
        self.client.force_login(self.super)
        self.assertEqual(self.client.post(reverse('governance_membership',args=[self.reviewer.pk]),{'project':self.second.pk,'action':'grant'}).status_code,403)
        self.assertFalse(ProjectMembership.objects.filter(user=self.reviewer,project=self.second,is_active=True).exists())
        self.assertEqual(self.client.post(reverse('governance_member',args=[self.engineer.pk]),{'action':'role','role':Profile.Roles.CLIENT}).status_code,403)
        self.engineer.profile.refresh_from_db();self.assertEqual(self.engineer.profile.role,Profile.Roles.ENGINEER)
    def test_admin_creation_binds_server_scope_and_cannot_assign_foreign_client(self):
        self.client.force_login(self.admin)
        response=self.client.post(reverse('governance_company'),{'name':'Authorized Client','description':'Synthetic scoped client','company':self.foreign_company.pk,'industry':self.construction.pk,'created_by':self.super.pk})
        self.assertEqual(response.status_code,302)
        org=ClientOrganization.objects.get(name='Authorized Client')
        self.assertEqual((org.company_id,org.industry_id,org.created_by_id),(self.company.pk,self.telecom.pk,self.admin.pk))
        self.assertEqual(self.client.post(reverse('governance_project_client',args=[self.project.pk]),{'client_organization':org.pk}).status_code,302)
        self.project.refresh_from_db();self.assertEqual(self.project.client_organization_id,org.pk)
        foreign=ClientOrganization.objects.create(name='Foreign Client',company=self.foreign_company,industry=self.telecom,created_by=self.admin)
        self.assertEqual(self.client.post(reverse('governance_project_client',args=[self.project.pk]),{'client_organization':foreign.pk}).status_code,400)
        self.assertIn(self.client.post(reverse('governance_project_client',args=[self.foreign.pk]),{'client_organization':org.pk}).status_code,(403,404))
        self.project.refresh_from_db();self.assertEqual(self.project.client_organization_id,org.pk)
    def test_admin_can_invite_client_but_foreign_scope_and_csrf_are_denied(self):
        self.client.force_login(self.admin)
        payload={'email':'new-scoped-client@example.test','role':Profile.Roles.CLIENT,'project':self.project.pk}
        self.assertEqual(self.client.post(reverse('governance_invite'),payload).status_code,200)
        invitation=ProjectInvitation.objects.get(email=payload['email']);self.assertEqual(invitation.created_by_id,self.admin.pk)
        self.assertIn(self.client.post(reverse('governance_invite'),{**payload,'email':'foreign-client@example.test','project':self.foreign.pk}).status_code,(400,403,404))
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.admin)
        self.assertEqual(strict.post(reverse('governance_company'),{'name':'CSRF client'}).status_code,403)
        self.assertFalse(ClientOrganization.objects.filter(name='CSRF client').exists())
    def test_super_project_client_assignment_and_nonadmin_client_creation_denied(self):
        org=ClientOrganization.objects.create(name='Existing Client',company=self.company,industry=self.telecom,created_by=self.admin)
        self.client.force_login(self.super)
        self.assertEqual(self.client.post(reverse('governance_project_client',args=[self.project.pk]),{'client_organization':org.pk}).status_code,403)
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.post(reverse('governance_company'),{'name':'Engineer client'}).status_code,403)
        self.project.refresh_from_db();self.assertIsNone(self.project.client_organization_id)
