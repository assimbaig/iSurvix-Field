"""SA02 administrative desk does not grant operational authority or leak its audit."""
from django.contrib.auth.models import User
from django.test import TestCase,override_settings
from django.urls import reverse
from .models import Profile,Company,Project,IndustryCatalog,Checklist,GovernanceAudit

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SuperTabbedDeskTests(TestCase):
    def setUp(self):
        self.industry=IndustryCatalog.objects.get_or_create(code='telecom',defaults={'name':'Telecom'})[0]
        self.company=Company.objects.create(name='Synthetic SA02 employer')
        self.project=Project.objects.create(name='Synthetic SA02 project',company=self.company)
        self.super=self.person('sa02_super',Profile.Roles.SUPER_ADMIN,True)
        self.admin=self.person('sa02_admin',Profile.Roles.ADMIN)
        self.engineer=self.person('sa02_engineer',Profile.Roles.ENGINEER)
        self.survey=Checklist.objects.create(user=self.engineer,project=self.project,site_id='SYNTHETIC-SA02',schema_snapshot={'sections':[]})
        for number in range(20):GovernanceAudit.objects.create(actor=self.super,action='sa02_event_'+str(number))
    def person(self,name,role,superuser=False):
        user=User.objects.create_user(name,is_superuser=superuser)
        user.profile.role=role;user.profile.company=self.company;user.profile.project=self.project
        if role==Profile.Roles.ADMIN:user.profile.admin_industry=self.industry
        user.profile.save()
        return user
    def test_recent_audit_is_bounded_newest_first_and_super_only(self):
        self.client.force_login(self.super)
        response=self.client.get(reverse('governance_home'))
        self.assertEqual(response.status_code,200)
        self.assertTemplateUsed(response,'dashboards/super_admin_workspace.html')
        self.assertContains(response,'data-super-design="SA-02"')
        self.assertContains(response,'id="sa-desk-content"')
        recent=list(response.context['recent_audit'])
        self.assertGreater(len(recent),0)
        self.assertEqual(len(recent),12)
        self.assertEqual(recent[0].action,'sa02_event_19')
        self.assertEqual([event.pk for event in recent],sorted([event.pk for event in recent],reverse=True))
        for actor in [self.admin,self.engineer]:
            self.client.force_login(actor)
            response=self.client.get(reverse('governance_home'))
            self.assertEqual(response.status_code,200)
            self.assertTemplateUsed(response,'dashboards/governance_workspace.html')
            self.assertIsNone(response.context.get('recent_audit'))
            self.assertNotContains(response,'sa02_event_19')
    def test_five_super_views_remain_administrative_and_operational_urls_denied(self):
        self.client.force_login(self.super)
        for view in ['dashboard','industries','clients','projects','sites']:
            with self.subTest(view=view):
                response=self.client.get(reverse('governance_home'),{'view':view})
                self.assertEqual(response.status_code,200)
                self.assertFalse(response.context['can_assign'])
                self.assertFalse(response.context['can_client_approve'])
                self.assertFalse(response.context['surveys'].exists())
                self.assertFalse(response.context['assignments'].exists())
        for route in ['custom_checklist','photo_workspace','checklist_ai_review']:
            self.assertEqual(self.client.get(reverse(route,args=[self.survey.pk])).status_code,403)
        self.assertEqual(self.client.post(reverse('governance_assign'),{}).status_code,403)
        self.survey.refresh_from_db();self.assertEqual(self.survey.status,Checklist.Status.DRAFT)
    def test_invalid_invitation_returns_dashboard_with_actionable_error(self):
        self.client.force_login(self.super)
        response=self.client.post(reverse('governance_invite'),{'email':'not-an-email','role':Profile.Roles.ADMIN,'project':self.project.pk,'admin_industry':self.industry.pk})
        self.assertEqual(response.status_code,400)
        self.assertEqual(response.context['active_view'],'dashboard')
        self.assertIn('email',response.context['invite_form'].errors)
        self.assertContains(response,'Enter a valid email address.',status_code=400)
        self.assertContains(response,'data-desk-panel="invite"',status_code=400)
        roles=[value for value,label in response.context['invite_form'].fields['role'].choices]
        self.assertNotIn(Profile.Roles.CLIENT,roles)
