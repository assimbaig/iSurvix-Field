from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory, override_settings
from .models import Profile
from .release_notice import release_notice_context


@override_settings(ROOT_URLCONF='checklist.urls_local', ISURVIX_RELEASE_ID='a'*40)
class ReleaseDisplayTests(TestCase):
    def test_public_notice_uses_defined_version_instead_of_source_hash(self):
        user=User.objects.create_user('release-owner',is_superuser=True)
        user.profile.role=Profile.Roles.SUPER_ADMIN;user.profile.save()
        request=RequestFactory().get('/governance/');request.user=user;request.session={}
        notice=release_notice_context(request)['release_notice']
        self.assertEqual(notice['version'],'V1.3.1 Beta')
        self.assertEqual(notice['release_id'],'a'*40)
        self.assertTrue(notice['changes'])

    def test_version_contract_supports_minor_and_patch_numbers_only(self):
        from .release_history import validate_version
        self.assertEqual(validate_version('1.3'),'1.3')
        self.assertEqual(validate_version('1.3.1'),'1.3.1')
        for bad in ['1','1.3.1.2','a'*40,'PR#44','01.3','1.03','1.3<script>']:
            with self.subTest(bad=bad),self.assertRaises(ValueError):validate_version(bad)
