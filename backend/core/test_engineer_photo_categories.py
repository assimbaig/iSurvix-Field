"""General Info is data; legacy unclassified evidence remains recoverable."""
import json
from pathlib import Path
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,override_settings
from django.urls import reverse
from . import test_engineer_bulk_categories as fixture
from .models import GovernanceAudit,PhotoEvidence


@override_settings(SECRET_KEY='isolated-engineer-data-photo-separation',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EngineerPhotoCategoryTests(TestCase):
    setUp=fixture.EngineerBulkCategoryTests.setUp
    person=fixture.EngineerBulkCategoryTests.person
    add_photo=fixture.EngineerBulkCategoryTests.add_photo
    state=fixture.EngineerBulkCategoryTests.state
    groups=fixture.EngineerBulkCategoryTests.groups

    def test_general_info_is_not_a_photo_destination_or_upload_category(self):
        before=self.groups();count=PhotoEvidence.objects.count()
        state=self.state()
        self.assertEqual([c['value'] for c in state['categories']],['Civil','Electrical','Tower'])
        for group in ['General Info','']:
            with self.subTest(group=group):
                response=self.client.post(reverse('photo_capture_category',args=[self.checklist.pk]),
                    json.dumps({'photo_ids':self.ids,'group':group,'expected_digest':state['digest']}),content_type='application/json')
                self.assertEqual(response.status_code,409,response.content)
                self.assertIn('site data',response.json()['error'])
                self.assertEqual(self.groups(),before)
        for group in ['General Info','']:
            with self.subTest(upload_group=group):
                response=self.client.post(reverse('photo_upload',args=[self.checklist.pk]),{'group':group,
                    'files':[SimpleUploadedFile('legacy.png',self.originals[self.photo.pk],content_type='image/png')]})
                self.assertEqual(response.status_code,409,response.content)
                self.assertEqual(PhotoEvidence.objects.count(),count)
                self.assertEqual(self.groups(),before)

    def test_existing_unclassified_sources_stay_readable_and_can_move_without_changing_bytes(self):
        self.photo.group='';self.photo.save(update_fields=['group'])
        audit_count=GovernanceAudit.objects.count()
        state=self.state()
        self.assertEqual(GovernanceAudit.objects.count(),audit_count)
        self.assertEqual(next(p for p in state['photos'] if p['id']==self.photo.pk)['group'],'')
        original=self.client.get(reverse('photo_evidence',args=[self.checklist.pk,self.photo.pk,'original']))
        self.assertEqual(original.status_code,200)
        self.assertEqual(b''.join(original.streaming_content),self.originals[self.photo.pk])
        moved=self.client.post(reverse('photo_capture_category',args=[self.checklist.pk]),
            json.dumps({'photo_ids':[self.photo.pk],'group':'Civil','expected_digest':state['digest']}),content_type='application/json')
        self.assertEqual(moved.status_code,200,moved.content)
        self.photo.refresh_from_db();self.assertEqual(self.photo.group,'Civil')
        self.assertEqual(Path(self.photo.original.path).read_bytes(),self.originals[self.photo.pk])
        self.assertEqual(set(p['id'] for p in moved.json()['photos']),set(self.ids))
