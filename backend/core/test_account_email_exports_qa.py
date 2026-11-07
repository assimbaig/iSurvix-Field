"""Independent real-record acceptance for account recovery, releases and exports.

Run only through scripts/run_backend_tests.py: disposable DB/media, no live mail.
"""
from io import BytesIO
import re
import uuid

from django.apps import apps
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from .models import Company, IndustryCatalog, Profile, Project, ProjectMembership


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False, NOTIFICATION_EMAIL_ENABLED=True,
                   NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',
                   NOTIFICATION_EMAIL_CREDENTIALS_FILE='',
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentAccountEmailExportsQA(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(name='Synthetic QA company A')
        self.foreign_company = Company.objects.create(name='Synthetic PRIVATE company B')
        self.industry = IndustryCatalog.objects.get(code='telecom')
        self.engineer = self.person('qa_recovery_engineer', Profile.Roles.ENGINEER)
        self.admin = self.person('qa_export_admin', Profile.Roles.ADMIN)
        self.foreign = self.person('PRIVATE_foreign_person_B', Profile.Roles.ADMIN, self.foreign_company)
        self.owner = self.person('qa_platform_owner', Profile.Roles.SUPER_ADMIN)
        User.objects.filter(pk=self.owner.pk).update(is_staff=True, is_superuser=True)
        self.owner.refresh_from_db()
        self.project = Project.objects.create(name='Synthetic QA project A', company=self.company,
                                              administrator=self.admin, industry='telecom')
        for user in [self.admin, self.engineer]:
            user.profile.project = self.project
            user.profile.save()
            ProjectMembership.objects.create(user=user, project=self.project)

    def person(self, name, role, company=None):
        user = User.objects.create_user(name, email=name+'@example.test', password='Synthetic-QA-old-779!')
        user.profile.role = role
        user.profile.company = company or self.company
        user.profile.admin_industry = self.industry if role == Profile.Roles.ADMIN else None
        user.profile.save()
        return user

    def recovery_model(self):
        return apps.get_model('core', 'AccountRecoveryRequest')

    def queue_reset(self, user=None):
        user = user or self.engineer
        response = self.client.post(reverse('account_password_reset'), {'email':user.email})
        self.assertEqual(response.status_code, 302)
        return self.recovery_model().objects.get(user_id=user.pk)

    def reset_url(self, row):
        from .account_recovery import _reset_token
        return reverse('account_password_reset_confirm', args=[row.pk, _reset_token(row)])

    def test_forgot_password_is_discoverable_and_never_enumerates_unknown_accounts(self):
        url = reverse('account_password_reset')
        self.assertContains(self.client.get('/login/'), url)
        known = self.client.post(url, {'email':self.engineer.email})
        unknown = self.client.post(url, {'email':'unregistered-synthetic@example.test'})
        self.assertEqual(known.status_code, 302)
        self.assertEqual(unknown.status_code, known.status_code)
        self.assertEqual(unknown['Location'], known['Location'])
        self.assertEqual(self.recovery_model().objects.count(), 1)
        self.assertNotIn(self.engineer.email, known.content.decode())

    def test_reset_changes_password_once_without_authenticating_anonymous_caller(self):
        row = self.queue_reset()
        url = self.reset_url(row)
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {'new_password1':'Synthetic-QA-new-882!', 'new_password2':'Synthetic-QA-new-882!'})
        self.assertEqual(response.status_code, 302)
        self.engineer.refresh_from_db()
        self.assertTrue(self.engineer.check_password('Synthetic-QA-new-882!'))
        self.assertNotIn('_auth_user_id', self.client.session)
        row.refresh_from_db()
        self.assertIsNotNone(row.used_at)
        self.client.post(url, {'new_password1':'Synthetic-QA-replay-993!', 'new_password2':'Synthetic-QA-replay-993!'})
        self.engineer.refresh_from_db()
        self.assertTrue(self.engineer.check_password('Synthetic-QA-new-882!'))

    def test_reset_denies_csrf_and_cannot_unlock_an_administrator_locked_account(self):
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(reverse('account_password_reset'), {'email':self.engineer.email}).status_code, 403)
        row = self.queue_reset()
        url = self.reset_url(row)
        Profile.objects.filter(user=self.engineer).update(is_locked=True)
        self.client.post(url, {'new_password1':'Synthetic-QA-unlock-994!', 'new_password2':'Synthetic-QA-unlock-994!'})
        self.engineer.refresh_from_db()
        self.engineer.profile.refresh_from_db()
        self.assertTrue(self.engineer.check_password('Synthetic-QA-old-779!'))
        self.assertTrue(self.engineer.profile.is_locked)

    def test_new_reset_supersedes_old_link_and_email_change_invalidates_new_link(self):
        first = self.queue_reset()
        old_url = self.reset_url(first)
        self.client.post(reverse('account_password_reset'), {'email':self.engineer.email})
        self.client.post(old_url, {'new_password1':'Synthetic-QA-oldtoken-994!', 'new_password2':'Synthetic-QA-oldtoken-994!'})
        self.engineer.refresh_from_db()
        self.assertTrue(self.engineer.check_password('Synthetic-QA-old-779!'))
        newest = self.recovery_model().objects.filter(user=self.engineer).exclude(pk=first.pk).latest('created_at')
        new_url = self.reset_url(newest)
        self.engineer.email = 'changed-synthetic@example.test'
        self.engineer.save(update_fields=['email'])
        self.client.post(new_url, {'new_password1':'Synthetic-QA-staleemail-994!', 'new_password2':'Synthetic-QA-staleemail-994!'})
        self.engineer.refresh_from_db()
        self.assertTrue(self.engineer.check_password('Synthetic-QA-old-779!'))

    def test_release_popup_displays_human_version_and_bullets_not_technical_commit(self):
        self.client.force_login(self.engineer)
        with override_settings(ISURVIX_RELEASE_ID='c'*40):
            response = self.client.get(reverse('governance_home'), follow=True)
        self.assertEqual(response.status_code, 200)
        notice = response.context['release_notice']
        self.assertTrue(notice['changes'])
        visible_text = re.sub(r'<[^>]*>', ' ', response.content.decode())
        self.assertIn('V1.3.1 Beta', visible_text)
        self.assertNotIn('c'*40, visible_text)
        self.assertNotIn('ccccccc', visible_text)

    def test_release_history_is_owner_only_and_get_does_not_create_history(self):
        model = apps.get_model('core', 'InstalledRelease')
        for actor in [self.admin, self.engineer, self.foreign]:
            self.client.force_login(actor)
            before = model.objects.count()
            self.assertEqual(self.client.get(reverse('release_history')).status_code, 403)
            self.assertEqual(model.objects.count(), before)
        self.client.force_login(self.owner)
        before = model.objects.count()
        self.assertEqual(self.client.get(reverse('release_history')).status_code, 200)
        self.assertEqual(model.objects.count(), before)

    def test_real_login_registers_each_installed_release_once_across_accounts(self):
        model = apps.get_model('core', 'InstalledRelease')
        for release in ['e'*40, 'f'*40]:
            with override_settings(ISURVIX_RELEASE_ID=release):
                for actor in [self.admin, self.engineer, self.owner]:
                    self.client.force_login(actor)
                    self.assertEqual(model.objects.filter(release_key=release).count(), 1)
        self.assertEqual(set(model.objects.filter(release_key__in=['e'*40, 'f'*40])
                             .values_list('release_key', flat=True)), {'e'*40, 'f'*40})

    def export_model(self):
        return apps.get_model('core', 'DataExportJob')

    def queue_people_export(self):
        self.client.force_login(self.admin)
        key = str(uuid.uuid4())
        for _ in range(2):
            response = self.client.post(reverse('data_exports'), {'section':'people', 'request_key':key})
            self.assertIn(response.status_code, [200, 302])
        self.assertEqual(self.export_model().objects.filter(owner=self.admin).count(), 1)
        return self.export_model().objects.get(owner=self.admin)

    def test_people_export_is_persisted_deduplicated_and_foreign_company_data_absent(self):
        from .export_service import process_next
        self.engineer.username = '=2+2'
        self.engineer.save(update_fields=['username'])
        job = self.queue_people_export()
        self.assertTrue(process_next())
        job.refresh_from_db()
        self.assertEqual(job.status, 'ready')
        response = self.client.get(reverse('data_export_download', args=[job.pk]))
        self.assertEqual(response.status_code, 200)
        raw = b''.join(response.streaming_content) if response.streaming else response.content
        workbook = load_workbook(BytesIO(raw), read_only=True, data_only=False)
        self.assertEqual(set(workbook.sheetnames), {'Data', 'Columns', 'Export'})
        values = [str(cell.value) for sheet in workbook for row in sheet for cell in row if cell.value is not None]
        self.assertIn(self.engineer.username, '\n'.join(values))
        self.assertNotIn(self.foreign.username, '\n'.join(values))
        self.assertFalse([cell.coordinate for sheet in workbook for row in sheet for cell in row
                          if cell.data_type == 'f'], 'Untrusted source strings must not become spreadsheet formulas')
        workbook.close()

    def test_export_download_rechecks_actor_and_locked_owner_cannot_retrieve_ready_file(self):
        from .export_service import process_next
        job = self.queue_people_export()
        self.assertTrue(process_next())
        url = reverse('data_export_download', args=[job.pk])
        self.client.force_login(self.foreign)
        self.assertIn(self.client.get(url).status_code, [403, 404])
        self.client.force_login(self.admin)
        Profile.objects.filter(user=self.admin).update(is_locked=True)
        self.assertIn(self.client.get(url).status_code, [403, 404])

    def test_engineer_cannot_request_people_directory_export(self):
        self.client.force_login(self.engineer)
        response = self.client.post(reverse('data_exports'), {'section':'people', 'request_key':str(uuid.uuid4())})
        self.assertIn(response.status_code, [400, 403])
        self.assertFalse(self.export_model().objects.filter(owner=self.engineer).exists())
