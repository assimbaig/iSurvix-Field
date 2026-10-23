"""Selected presentation contracts never confer application permissions."""
from django.contrib.auth.models import User,AnonymousUser
from django.test import TestCase,RequestFactory,override_settings
from django.urls import reverse
from .models import Profile,Project,Checklist,IndustryCatalog
from .local_ai import local_context

@override_settings(SECRET_KEY='synthetic-role-design-tests',ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,LOCAL_AI_ENABLED=True)
class RoleDesignTests(TestCase):
    def setUp(self):
        self.project=Project.objects.create(name='Synthetic design project')
        self.users={}
        for role in [Profile.Roles.SUPER_ADMIN,Profile.Roles.ADMIN,Profile.Roles.ENGINEER,Profile.Roles.QUALITY_ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.CLIENT]:
            user=User.objects.create_user('design_'+role.lower(),is_superuser=role==Profile.Roles.SUPER_ADMIN)
            user.profile.role=role;user.profile.project=self.project
            if role==Profile.Roles.ADMIN:user.profile.admin_industry=IndustryCatalog.objects.get(code='telecom')
            user.profile.save();self.users[role]=user
        self.survey=Checklist.objects.create(user=self.users[Profile.Roles.ENGINEER],project=self.project,quality_reviewer=self.users[Profile.Roles.QUALITY_ENGINEER],site_id='DESIGN-SYNTHETIC',schema_snapshot={'sections':[{'id':'general','title':'General','fields':[{'id':'observation','label':'Observation','type':'text'}]}]})
    def context(self,user):
        request=RequestFactory().get('/');request.user=user
        return local_context(request)['role_design']
    def test_exact_selected_role_designs(self):
        codes={role:'enterprise-1' for role in self.users}
        for role,user in self.users.items():
            descriptor=self.context(user)
            self.assertEqual(descriptor['role'],role);self.assertEqual(descriptor['code'],codes[role])
            self.assertEqual(descriptor['layout'],'enterprise')
            self.assertEqual(descriptor['palette'],'navy')
        self.assertEqual(self.context(self.users[Profile.Roles.QUALITY_ENGINEER])['label'],'QA Engineer')
    def test_presentation_requires_actual_active_role_not_profile_or_session_claim(self):
        self.assertIsNone(self.context(AnonymousUser()))
        fake=User.objects.create_user('design_forged_super');fake.profile.role=Profile.Roles.SUPER_ADMIN;fake.profile.save()
        self.assertIsNone(self.context(fake))
        self.client.force_login(fake)
        session=self.client.session;session['is_dev_admin']=True;session.save()
        self.assertEqual(self.client.get(reverse('governance_home')).status_code,403)
        user=self.users[Profile.Roles.SUPER_ADMIN];user.profile.is_locked=True;user.profile.save()
        self.assertIsNone(self.context(user))
        user=self.users[Profile.Roles.ENGINEER];user.is_active=False;user.save()
        self.assertIsNone(self.context(user))
    def test_role_workspace_renders_selected_design_and_preserves_action_scope(self):
        for role,user in self.users.items():
            self.client.force_login(user)
            response=self.client.get(reverse('governance_home'))
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.context['role_design'],self.context(user))
            self.assertContains(response,'data-role="'+role+'"')
            self.assertContains(response,'data-layout="'+self.context(user)['layout']+'"')
            self.assertContains(response,'data-palette="'+self.context(user)['palette']+'"')
            self.assertEqual(bool(response.context['can_assign']),role in {Profile.Roles.ADMIN,Profile.Roles.TEAM_LEAD})
        self.client.force_login(self.users[Profile.Roles.SUPER_ADMIN])
        self.assertEqual(self.client.get(reverse('custom_checklist',args=[self.survey.pk])).status_code,403)
    def test_shared_capture_review_and_photo_pages_keep_role_design_without_role_escalation(self):
        for role in [Profile.Roles.ENGINEER,Profile.Roles.QUALITY_ENGINEER,Profile.Roles.TEAM_LEAD]:
            self.client.force_login(self.users[role])
            for route in ['custom_checklist','photo_workspace','roadmap_activity']:
                response=self.client.get(reverse(route,args=[self.survey.pk]),follow=True)
                self.assertEqual(response.status_code,200)
                self.assertContains(response,'data-role="'+role+'"')
            response=self.client.get(reverse('custom_checklist',args=[self.survey.pk]))
            if role==Profile.Roles.ENGINEER:
                self.assertRedirects(response,reverse('photo_workspace',args=[self.survey.pk]),fetch_redirect_response=False)
            else:self.assertFalse(response.context['can_submit'])
            if role==Profile.Roles.QUALITY_ENGINEER:
                self.assertFalse(response.context['can_edit']);self.assertFalse(response.context['can_review'])
        self.survey.status=Checklist.Status.FINAL;self.survey.save()
        self.client.force_login(self.users[Profile.Roles.CLIENT])
        response=self.client.get(reverse('custom_checklist',args=[self.survey.pk]),follow=True)
        self.assertEqual(response.status_code,200);self.assertContains(response,'data-role="CLIENT"')
        self.assertFalse(response.context['can_edit']);self.assertFalse(response.context['can_submit']);self.assertFalse(response.context['can_review'])

    def test_shell_module_choices_follow_permitted_industry_and_super_is_administrative(self):
        request=RequestFactory().get('/')
        request.user=self.users[Profile.Roles.ENGINEER]
        context=local_context(request)
        self.assertEqual({module['code'] for module in context['shell_modules']},{'telecom_survey','telecom_inspection'})
        construction=Project.objects.create(name='Other company construction',industry='construction')
        self.assertNotIn(construction,context['shell_projects'])
        request.user=self.users[Profile.Roles.SUPER_ADMIN]
        self.assertEqual(local_context(request)['shell_modules'],[])
        self.client.force_login(request.user)
        response=self.client.get(reverse('governance_home'))
        self.assertNotContains(response,'id="enterprise-module"')
        self.assertNotContains(response,'>Task explorer</a>')

    def test_operational_shell_exposes_working_explorer_and_project_controls(self):
        self.client.force_login(self.users[Profile.Roles.ENGINEER])
        response=self.client.get(reverse('custom_checklist',args=[self.survey.pk]),follow=True)
        self.assertContains(response,reverse('task_explorer'))
        self.assertContains(response,'id="enterprise-project"')
        self.assertContains(response,'class="platform-nav workspace-nav-tiles"')
        self.assertNotContains(response,'class="role-primary-shell"')
        html=response.content.decode()
        self.assertLess(html.index('class="platform-nav workspace-nav-tiles"'),html.index('</header>'))
        self.assertNotContains(response,'>Administration</a>')
