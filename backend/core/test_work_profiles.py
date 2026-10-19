"""Professional publication cannot bypass project grants or account boundaries."""
from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from django.utils import timezone
from .models import Profile,Project,Company,ProjectMembership,WorkProfile,ProfessionalExperience,GovernanceAudit

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class WorkProfileTests(TestCase):
    def setUp(self):
        self.company=Company.objects.create(name='Synthetic professional employer')
        self.project=Project.objects.create(name='Synthetic shared project',company=self.company)
        self.engineer=self.person('professional_engineer',Profile.Roles.ENGINEER)
        self.quality=self.person('professional_quality',Profile.Roles.QUALITY_ENGINEER)
        self.client_user=self.person('professional_client',Profile.Roles.CLIENT)
        self.record=WorkProfile.objects.create(user=self.engineer,display_name='Published Engineering Professional',headline='Field Engineer',bio='Synthetic professional biography',published=True)
    def person(self,name,role,project=None,superuser=False):
        project=project or self.project
        user=User.objects.create_user(name,email=name+'@example.test',password='Synthetic-professional-241!',is_superuser=superuser)
        user.profile.role=role;user.profile.project=project;user.profile.company=project.company;user.profile.save()
        ProjectMembership.objects.create(user=user,project=project,is_active=True,is_primary=True)
        return user
    def view(self,user):
        self.client.force_login(user)
        return self.client.get(reverse('work_profile_detail',args=[self.engineer.pk]))
    def experience_data(self,**changes):
        return {'organization':'Synthetic engineering organization','job_title':'Field Engineer','start_date':'2022-01-01','is_current':'on','summary':'Synthetic self-reported experience','qualifications':'Synthetic qualification reference',**changes}
    def test_client_reads_only_published_staff_without_authentication_metadata(self):
        response=self.view(self.client_user)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,self.record.display_name)
        self.assertNotContains(response,self.engineer.email)
        self.assertNotContains(response,self.engineer.password)
        self.assertContains(self.client.get(reverse('work_profile_directory')),self.record.display_name)
        self.record.published=False;self.record.save()
        self.assertEqual(self.view(self.client_user).status_code,404)
        self.assertNotContains(self.client.get(reverse('work_profile_directory')),self.record.display_name)
    def test_client_scope_revocation_expiry_lock_and_tenant_boundaries(self):
        grant=ProjectMembership.objects.get(user=self.engineer,project=self.project)
        grant.expires_at=timezone.now()-timedelta(seconds=1);grant.save()
        self.assertEqual(self.view(self.client_user).status_code,404)
        grant.expires_at=None;grant.is_active=False;grant.save()
        self.assertEqual(self.view(self.client_user).status_code,404)
        grant.is_active=True;grant.save()
        self.engineer.profile.is_locked=True;self.engineer.profile.save()
        self.assertEqual(self.view(self.client_user).status_code,404)
        self.engineer.profile.is_locked=False;self.engineer.profile.save()
        ProjectMembership.objects.filter(user=self.client_user).update(is_active=False)
        self.assertEqual(self.view(self.client_user).status_code,404)
        foreign_company=Company.objects.create(name='Synthetic foreign employer')
        foreign_project=Project.objects.create(name='Synthetic foreign project',company=foreign_company)
        foreign=self.person('professional_foreign_client',Profile.Roles.CLIENT,foreign_project)
        self.assertEqual(self.view(foreign).status_code,404)
    def test_client_cannot_discover_other_clients_or_super(self):
        other=self.person('professional_other_client',Profile.Roles.CLIENT)
        superuser=self.person('professional_super',Profile.Roles.SUPER_ADMIN,superuser=True)
        for user in [other,superuser]:WorkProfile.objects.create(user=user,display_name='Restricted '+user.username,published=True)
        self.client.force_login(self.client_user)
        for user in [other,superuser]:
            self.assertEqual(self.client.get(reverse('work_profile_detail',args=[user.pk])).status_code,404)
            self.assertNotContains(self.client.get(reverse('work_profile_directory')),'Restricted '+user.username)
        self.client.force_login(superuser)
        self.assertEqual(self.client.get(reverse('work_profile_directory')).status_code,403)
    def test_self_edit_is_all_roles_only_own_allowlisted_fields(self):
        roles=[Profile.Roles.ENGINEER,Profile.Roles.QUALITY_ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.ADMIN,Profile.Roles.CLIENT,Profile.Roles.PROJECT_MANAGER,Profile.Roles.SUPER_ADMIN]
        for number,role in enumerate(roles):
            actor=self.person('professional_role_'+str(number),role,superuser=role==Profile.Roles.SUPER_ADMIN)
            self.client.force_login(actor)
            self.assertEqual(self.client.get(reverse('work_profile')).status_code,200)
            self.assertFalse(WorkProfile.objects.get(user=actor).published)
            response=self.client.post(reverse('work_profile'),{'display_name':'Updated own name','headline':'Professional role','bio':'<script>unsafe()</script>','published':'on','user':self.engineer.pk,'role':'SUPER_ADMIN','admin_industry':'999'})
            self.assertEqual(response.status_code,302)
            self.assertEqual(WorkProfile.objects.get(user=actor).display_name,'Updated own name')
            self.assertEqual(self.client.get(reverse('work_profile_detail',args=[actor.pk])).status_code,200)
            self.assertNotContains(self.client.get(reverse('work_profile_detail',args=[actor.pk])),'<script>unsafe()</script>')
        self.record.refresh_from_db();self.assertEqual(self.record.display_name,'Published Engineering Professional')
    def test_engineer_and_quality_experience_crud_is_owned_and_csrf_guarded(self):
        for actor in [self.engineer,self.quality]:
            self.client.force_login(actor)
            response=self.client.post(reverse('work_profile_experience_add'),self.experience_data(work_profile=self.record.pk))
            self.assertEqual(response.status_code,302)
            entry=ProfessionalExperience.objects.get(work_profile__user=actor)
            self.assertEqual(self.client.post(reverse('work_profile_experience_edit',args=[entry.pk]),self.experience_data(job_title='Updated title')).status_code,302)
            self.assertEqual(self.client.get(reverse('work_profile_experience_delete',args=[entry.pk])).status_code,405)
            strict=Client(enforce_csrf_checks=True);strict.force_login(actor)
            self.assertEqual(strict.post(reverse('work_profile_experience_delete',args=[entry.pk])).status_code,403)
        engineer_entry=ProfessionalExperience.objects.get(work_profile__user=self.engineer)
        self.client.force_login(self.quality)
        self.assertEqual(self.client.post(reverse('work_profile_experience_edit',args=[engineer_entry.pk]),self.experience_data()).status_code,404)
        self.assertEqual(self.client.post(reverse('work_profile_experience_delete',args=[engineer_entry.pk])).status_code,404)
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.post(reverse('work_profile_experience_delete',args=[engineer_entry.pk])).status_code,302)
        self.assertFalse(ProfessionalExperience.objects.filter(pk=engineer_entry.pk).exists())
        self.assertTrue(GovernanceAudit.objects.filter(action='professional_experience_deleted').exists())
    def test_role_forgery_and_invalid_dates_do_not_create_experience(self):
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.post(reverse('work_profile_experience_add'),self.experience_data(role=Profile.Roles.ENGINEER)).status_code,403)
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.post(reverse('work_profile_experience_add'),self.experience_data(start_date='2023-01-01',end_date='2022-01-01',is_current='')).status_code,400)
        self.assertEqual(self.client.post(reverse('work_profile_experience_add'),self.experience_data(end_date='2024-01-01')).status_code,400)
        self.assertFalse(ProfessionalExperience.objects.exists())
        self.engineer.profile.is_locked=True;self.engineer.profile.save()
        self.assertEqual(self.client.post(reverse('work_profile'),{'published':'on'}).status_code,403)
    def test_unpublish_immediately_removes_client_access_and_no_private_bio_in_audit(self):
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.post(reverse('work_profile'),{'display_name':'Engineer','bio':'Private professional introduction'}).status_code,302)
        self.assertEqual(self.view(self.client_user).status_code,404)
        audit=GovernanceAudit.objects.get(action='professional_profile_saved')
        self.assertEqual(audit.details,{'published':False})

    def test_public_fallback_never_exposes_owner_login_identifier(self):
        self.record.display_name='';self.record.save()
        response=self.view(self.client_user)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Project team member')
        self.assertNotContains(response,self.engineer.username)
        self.assertNotContains(response,self.engineer.email)
        directory=self.client.get(reverse('work_profile_directory'))
        self.assertNotContains(directory,self.engineer.username)
        self.assertNotContains(directory,self.engineer.email)
