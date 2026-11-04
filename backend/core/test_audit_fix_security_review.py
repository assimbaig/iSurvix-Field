"""Independent adversarial review of the approved audit repair result.

Fixtures and actual filesystem redirects are disposable; no operational records,
worker/model services or original evidence are used.
"""
from datetime import timedelta
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Company, IndustryCatalog, Profile, Project, ProjectMembership, WorkProfile
from . import test_worker_runtime_tools as runtime_fixture


class DiagnosticRedirectSecurityReviewTests(SimpleTestCase):
    setUp = runtime_fixture.WorkerRuntimeToolTests.setUp

    def check_redirect(self, component):
        local = self.directory / '.local'
        if component == 'diagnostics':
            local.mkdir()
        outside_temp = tempfile.TemporaryDirectory(prefix='outside-diagnostic-boundary-', dir=self.directory.parent)
        self.addCleanup(outside_temp.cleanup)
        outside = Path(outside_temp.name)
        self.assertEqual(outside.parent.resolve(), self.directory.parent.resolve())
        self.assertNotEqual(outside, self.directory)
        link = local / 'diagnostics' if component == 'diagnostics' else local
        if os.name == 'nt':
            powershell = shutil.which('powershell.exe') or shutil.which('pwsh')
            self.assertIsNotNone(powershell, 'This Windows redirect regression requires PowerShell')
            quoted_link = "'" + str(link).replace("'", "''") + "'"
            quoted_target = "'" + str(outside).replace("'", "''") + "'"
            subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-Command',
                '$ErrorActionPreference = \'Stop\'; New-Item -ItemType Junction -Path ' +
                quoted_link + ' -Target ' + quoted_target + ' | Out-Null'], check=True,
                capture_output=True, timeout=20)
            self.assertTrue(link.is_junction(), 'The fixture must be a real Windows junction')
        else:
            link.symlink_to(outside, target_is_directory=True)
            self.assertTrue(link.is_symlink())
        try:
            with self.assertRaises(ValueError):
                produced = self.tools.collect_diagnostics(project_root=self.directory,
                    model=runtime_fixture.MODEL, photo_url=self.url, text_url=self.url)
                produced = Path(produced)
                self.assertTrue(produced.is_file())
                self.assertTrue(produced.resolve().is_relative_to(outside.resolve()))
            self.assertEqual(list(outside.iterdir()), [], 'Redirected private output must never be written')
        finally:
            # Remove only the fixture redirect itself. Never recursively follow it.
            if os.name == 'nt':
                os.rmdir(link)
            else:
                link.unlink()

    def test_real_directory_redirect_cannot_receive_private_diagnostic_output(self):
        self.check_redirect('diagnostics')

    def test_real_local_ancestor_redirect_cannot_receive_private_diagnostic_output(self):
        self.check_redirect('local')


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DirectoryAndRosterSecurityReviewTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Independent repair employer A')
        self.foreign_company = Company.objects.create(name='Independent repair employer B')
        self.project = Project.objects.create(name='Independent repair shared project', company=self.company)
        self.other_project = Project.objects.create(name='Independent repair unshared project', company=self.company)
        self.foreign_project = Project.objects.create(name='Independent repair foreign project', company=self.foreign_company)
        self.actor = self.person('review_client', Profile.Roles.CLIENT)
        self.admin = self.person('review_admin', Profile.Roles.ADMIN)
        self.project.administrator = self.admin
        self.project.save(update_fields=['administrator'])
        profile = self.admin.profile
        profile.admin_industry = IndustryCatalog.objects.get(code=self.project.industry)
        profile.save(update_fields=['admin_industry'])

    def person(self, name, role, *, project=None, published=True):
        project = project or self.project
        user = User.objects.create_user(name)
        profile = user.profile
        profile.role, profile.company, profile.project = role, project.company, project
        profile.save()
        ProjectMembership.objects.create(user=user, project=project, is_active=True, is_primary=True)
        WorkProfile.objects.create(user=user, display_name='Synthetic ' + name, published=published)
        return user

    def client_for(self, user):
        browser = Client()
        browser.force_login(user)
        return browser

    def listed_ids(self, browser):
        result = set()
        page = 1
        while True:
            response = browser.get(reverse('work_profile_directory'), {'page': page})
            self.assertEqual(response.status_code, 200)
            result.update(row['profile'].user_id for row in response.context['page_obj'])
            if not response.context['page_obj'].has_next():
                return result
            page += 1

    def test_all_directory_pages_exclude_revoked_expired_locked_foreign_and_unpublished_targets(self):
        visible = [self.person(f'review_visible_{i:02}', Profile.Roles.ENGINEER) for i in range(30)]
        revoked = self.person('review_revoked', Profile.Roles.ENGINEER)
        expired = self.person('review_expired', Profile.Roles.ENGINEER)
        locked = self.person('review_locked', Profile.Roles.ENGINEER)
        disabled = self.person('review_disabled', Profile.Roles.ENGINEER)
        private = self.person('review_private', Profile.Roles.ENGINEER, published=False)
        foreign = self.person('review_foreign', Profile.Roles.ENGINEER, project=self.foreign_project)
        unshared = self.person('review_unshared', Profile.Roles.ENGINEER, project=self.other_project)
        other_client = self.person('review_other_client', Profile.Roles.CLIENT)
        ProjectMembership.objects.filter(user=revoked, project=self.project).update(is_active=False)
        ProjectMembership.objects.filter(user=expired, project=self.project).update(expires_at=timezone.now()-timedelta(seconds=1))
        Profile.objects.filter(user=locked).update(is_locked=True)
        User.objects.filter(pk=disabled.pk).update(is_active=False)
        browser = self.client_for(self.actor)
        listed = self.listed_ids(browser)
        self.assertEqual(listed, {self.admin.pk, *(user.pk for user in visible)})
        for target in [revoked, expired, locked, disabled, private, foreign, unshared, other_client]:
            self.assertEqual(browser.get(reverse('work_profile_detail', args=[target.pk])).status_code, 404)
        ProjectMembership.objects.filter(user=visible[-1], project=self.project).update(is_active=False)
        self.assertNotIn(visible[-1].pk, self.listed_ids(browser), 'The same session must recheck revocation')
        ProjectMembership.objects.filter(user=self.actor, project=self.project).update(is_active=False)
        self.assertEqual(self.listed_ids(browser), set(), 'Revoking the viewer must remove every shared profile')

    def test_admin_cannot_manage_an_offpage_or_foreign_scope_account_via_forged_form(self):
        for i in range(26):
            self.person(f'review_roster_{i:02}', Profile.Roles.ENGINEER)
        shared = self.person('review_z_cross_scope', Profile.Roles.ENGINEER)
        ProjectMembership.objects.create(user=shared, project=self.other_project, is_active=True)
        foreign = self.person('review_z_foreign_scope', Profile.Roles.ENGINEER, project=self.foreign_project)
        browser = self.client_for(self.admin)
        for page in (1, 2):
            response = browser.get(reverse('governance_home'), {'view': 'administration', 'people_page': page})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(foreign.pk, {member.pk for member in response.context['members']})
        for target in [shared, foreign]:
            response = browser.post(reverse('governance_member', args=[target.pk]), {'action': 'deactivate'})
            self.assertEqual(response.status_code, 403)
            target.refresh_from_db()
            self.assertTrue(target.is_active)
        response = browser.post(reverse('governance_member', args=[shared.pk]),
            {'action': 'role', 'role': Profile.Roles.SUPER_ADMIN, 'is_superuser': '1'})
        self.assertEqual(response.status_code, 400)
        shared.refresh_from_db()
        self.assertFalse(shared.is_superuser)
