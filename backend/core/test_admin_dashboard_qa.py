"""Independent saved-record acceptance for the company Admin overview."""
import hashlib
import re
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import (Checklist, ChecklistTemplate, ClientOrganization, Company,
    IndustryCatalog, PhotoEvidence, PhotoPlacement, Profile, Project,
    ProjectInvitation, ProjectMembership, ReviewRoute, WorkAssignment)


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False, NOTIFICATION_EMAIL_ENABLED=False,
    WORKFLOW_NOTIFICATION_EMAIL_ENABLED=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentAdminDashboardTests(TestCase):
    def setUp(self):
        self.industry = IndustryCatalog.objects.get(code='telecom')
        self.company = Company.objects.create(name='Independent dashboard QA company A')
        self.foreign_company = Company.objects.create(name='Independent dashboard QA company B')
        self.admin = self.person('independent_admin', Profile.Roles.ADMIN)
        self.foreign_admin = self.person('independent_foreign', Profile.Roles.ADMIN, company=self.foreign_company)
        self.template = ChecklistTemplate.objects.create(name='Independent QA approved template', published=True,
            created_by=self.admin, client_left_name='', client_right_name='',
            definition={'title':'Synthetic QA survey', 'sections':[{'id':'general','title':'General Info','fields':[
                {'id':'site_id','label':'Site ID','type':'text','system':'site_id'},
                {'id':'site_name','label':'Site name','type':'text'}]}]})
        self.p1 = self.project('Independent primary project', self.admin)
        self.p2 = self.project('QA <script>window.qaXss=1</script> long project', self.admin)
        self.foreign = self.project('Foreign project must stay private', self.foreign_admin, self.foreign_company)
        self.engineer = self.person('independent_engineer', Profile.Roles.ENGINEER, self.p1)
        ProjectMembership.objects.create(user=self.engineer, project=self.p2, is_active=True)
        self.qa = self.person('independent_quality', Profile.Roles.QUALITY_ENGINEER, self.p1)
        self.lead = self.person('independent_lead', Profile.Roles.TEAM_LEAD, self.p1)
        self.customer = self.person('independent_client', Profile.Roles.CLIENT, self.p1)
        self.organization = ClientOrganization.objects.create(name='Independent QA client', company=self.company,
            industry=self.industry, created_by=self.admin)
        self.p1.client_organization = self.organization; self.p1.save()
        self.c1 = Checklist.objects.create(user=self.engineer, project=self.p1, site_id='SAME-SITE', status='SUBMITTED')
        self.c2 = Checklist.objects.create(user=self.engineer, project=self.p1, site_id='SAME-SITE', status='REVIEW')
        self.c3 = Checklist.objects.create(user=self.engineer, project=self.p2, site_id='SAME-SITE', status='DRAFT')
        ReviewRoute.objects.create(checklist=self.c1, layer_count=3, stage='quality_engineer')
        ReviewRoute.objects.create(checklist=self.c2, layer_count=3, stage='team_lead')
        WorkAssignment.objects.create(project=self.p1, site_id='SAME-SITE', latitude=24, longitude=46,
            assigned_to=self.engineer, assigned_by=self.admin, description='Fixture linked work', checklist=self.c1)
        WorkAssignment.objects.create(project=self.p1, site_id='UNSTARTED-SITE', latitude=25, longitude=47,
            assigned_to=self.engineer, assigned_by=self.admin, description='Fixture pending work')
        for index, checklist in enumerate((self.c1, self.c2)):
            photo = PhotoEvidence.objects.create(checklist=checklist, uploaded_by=self.engineer,
                filename=f'independent-{index}.jpg', sha256=hashlib.sha256(str(index).encode()).hexdigest(),
                original=f'synthetic/{index}.jpg', preview=f'synthetic/{index}-preview.jpg')
            for point in ('one','two','three'):
                PhotoPlacement.objects.create(photo=photo, field_id=point, section_id='civil',
                    schema_digest='f'*64, status='confirmed')
        self.client.force_login(self.admin)

    def person(self, name, role, project=None, company=None):
        user = User.objects.create_user(name, email=name+'@example.test', password='Synthetic-QA-only!')
        user.profile.role=role;user.profile.company=company or self.company;user.profile.project=project
        if role == Profile.Roles.ADMIN:user.profile.admin_industry=self.industry
        user.profile.save()
        if project:ProjectMembership.objects.create(user=user,project=project,is_active=True,is_primary=True)
        return user

    def project(self, name, admin, company=None):
        project=Project.objects.create(name=name,company=company or self.company,industry='telecom',
            administrator=admin,review_layers=3,checklist_template=self.template if admin==self.admin else None)
        ProjectMembership.objects.create(user=admin,project=project,is_active=True)
        return project

    def test_distinct_saved_ids_and_project_scoped_site_identity(self):
        response=self.client.get(reverse('governance_home'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['active_view'],'dashboard')
        self.assertEqual(response.context['admin_dashboard']['summary'],
            {'sites':3,'photos':2,'activities':4,'projects':2,'clients':1,'people':5})
        self.assertEqual(response.context['admin_dashboard']['review_counts'],
            {'quality_engineer':1,'team_lead':1,'client':0,'unknown':0})
        self.assertNotContains(response,self.foreign.name)

    def test_project_scope_persists_after_reload_and_escapes_saved_names(self):
        for _ in range(2):
            response=self.client.get(reverse('governance_home'),{'view':'dashboard','project':self.p2.pk})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.context['selected_project_id'],str(self.p2.pk))
            self.assertEqual(response.context['admin_dashboard']['summary'],
                {'sites':1,'photos':0,'activities':1,'projects':1,'clients':0,'people':2})
            self.assertContains(response,'&lt;script&gt;window.qaXss=1&lt;/script&gt;')
            self.assertNotContains(response,'<script>window.qaXss=1</script>')

    def test_real_dialog_forms_have_unique_ids_and_invalid_invitation_preserves_values(self):
        response=self.client.get(reverse('governance_home'))
        ids=re.findall(r'\bid="([^"]+)"',response.content.decode())
        self.assertEqual(len(ids),len(set(ids)))
        result=self.client.post(reverse('governance_invite'),{'return_view':'dashboard',
            'dashboard_project':self.p1.pk,'project':self.p1.pk,'email':'preserved-invalid',
            'role':Profile.Roles.ENGINEER})
        self.assertEqual(result.status_code,400)
        self.assertEqual(result.context['active_view'],'dashboard')
        self.assertEqual(result.context['admin_dashboard_open_dialog'],'invite')
        self.assertEqual(result.context['invite_form']['email'].value(),'preserved-invalid')
        self.assertFalse(ProjectInvitation.objects.exists())

    def test_new_client_and_invitation_are_real_records_with_honest_disabled_mail(self):
        response=self.client.post(reverse('governance_company'),{'name':'New saved independent client',
            'return_view':'dashboard','dashboard_project':self.p1.pk})
        self.assertEqual(response.status_code,302)
        self.assertEqual(parse_qs(urlsplit(response.url).query)['project'],[str(self.p1.pk)])
        saved=ClientOrganization.objects.get(name='New saved independent client')
        self.assertEqual((saved.company_id,saved.industry_id),(self.company.pk,self.industry.pk))
        response=self.client.post(reverse('governance_invite'),{'return_view':'dashboard',
            'project':self.p1.pk,'email':'new-independent@example.test','role':Profile.Roles.ENGINEER})
        self.assertEqual(response.status_code,200)
        invitation=ProjectInvitation.objects.get(email='new-independent@example.test')
        self.assertEqual((invitation.company_id,invitation.project_id),(self.company.pk,self.p1.pk))
        self.assertContains(response,'Email sending is not configured for this invitation. Share the private link manually.')
        self.assertNotContains(response,'Email sent')

    def test_foreign_scope_and_role_cannot_reuse_dashboard_or_create_admin_invitation(self):
        self.assertEqual(self.client.get(reverse('governance_home'),{'view':'dashboard','project':self.foreign.pk}).status_code,404)
        for user in (self.engineer,self.qa,self.lead,self.customer):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('governance_home'),{'view':'dashboard'}).status_code,404)
        self.client.force_login(self.admin)
        response=self.client.post(reverse('governance_invite'),{'return_view':'dashboard',
            'project':self.p1.pk,'email':'elevated@example.test','role':Profile.Roles.ADMIN})
        self.assertEqual(response.status_code,400)
        self.assertFalse(ProjectInvitation.objects.filter(email='elevated@example.test').exists())
