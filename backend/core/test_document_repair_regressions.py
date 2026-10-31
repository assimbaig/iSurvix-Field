"""Approved W1/S2/S3 repairs against real isolated document HTTP routes."""
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from . import test_engineer_documents as fixtures
from .survey_processing_models import SurveyDocument


@override_settings(SECRET_KEY='isolated-document-repair-tests',
    ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False, DEBUG=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DocumentRepairTests(TestCase):
    setUp=fixtures.EngineerDocumentTests.setUp
    person=fixtures.EngineerDocumentTests.person
    add_photo=fixtures.EngineerDocumentTests.add_photo
    post=fixtures.EngineerDocumentTests.post
    raw=fixtures.EngineerDocumentTests.raw
    state=fixtures.EngineerDocumentTests.state
    upload=fixtures.EngineerDocumentTests.upload
    submit=fixtures.EngineerDocumentTests.submit
    doc_upload=fixtures.EngineerDocumentTests.doc_upload
    uploaded=fixtures.EngineerDocumentTests.uploaded

    def read(self, response):
        self.assertEqual(response.status_code,200)
        try:
            return b''.join(response.streaming_content)
        finally:
            response.close()

    def test_cached_pdf_corruption_never_replaces_source_evidence(self):
        import pymupdf
        with pymupdf.open() as pdf:
            page=pdf.new_page();page.insert_text((72,72),'SYNTHETIC authorised measured source 2 m')
            original=pdf.tobytes()
        row=self.uploaded(kind='report',name='source.pdf',raw=original)
        url=reverse('photo_capture_document',args=[self.checklist.pk,row['id']])+'?preview=1&raster=1&page=1'
        first=self.read(self.client.get(url))
        cached=list((Path(settings.MEDIA_ROOT)/'survey_processing/document_previews'/str(row['id'])).rglob('*.png'))
        self.assertTrue(cached)
        replacement=self.raw('CORRUPTED_DERIVATIVE')
        for path in cached:path.write_bytes(replacement)
        recovered=self.read(self.client.get(url))
        self.assertNotEqual(recovered,replacement,'W1: private cache corruption must not be served')
        self.assertEqual(recovered,first)
        self.assertEqual(Path(SurveyDocument.objects.get(pk=row['id']).original.path).read_bytes(),original)

    def test_unchanged_preview_cache_is_reused_and_forged_metadata_is_regenerated(self):
        import pymupdf
        from unittest.mock import patch
        with pymupdf.open() as pdf:
            page=pdf.new_page();page.insert_text((72,72),'SYNTHETIC cache identity source')
            original=pdf.tobytes()
        row=self.uploaded(kind='report',name='cache-source.pdf',raw=original)
        url=reverse('photo_capture_document',args=[self.checklist.pk,row['id']])+'?preview=1&raster=1&page=1'
        first=self.read(self.client.get(url))
        with patch('core.pdf_tools.PDFPage.render_png',side_effect=AssertionError('Unchanged cache must not render again')):
            self.assertEqual(self.read(self.client.get(url)),first)
        folder=Path(settings.MEDIA_ROOT)/'survey_processing/document_previews'/str(row['id'])
        for manifest in folder.glob('*.json'):
            manifest.write_bytes(b'{"sha256":"forged","identity":{}}')
        self.assertEqual(self.read(self.client.get(url)),first)
        doc=SurveyDocument.objects.get(pk=row['id'])
        Path(doc.original.path).write_bytes(b'out-of-band original corruption')
        self.assertEqual(self.client.get(url).status_code,409)

    def test_owning_admin_cannot_bypass_current_document_membership_using_old_route(self):
        row=self.uploaded()
        removed=self.post('photo_capture_document_remove',{'document_id':row['id'],'expected_digest':self.state()['digest']})
        self.assertEqual(removed.status_code,200,removed.content)
        self.client.force_login(self.admin)
        for name in ['photo_capture_document','survey_processing_document']:
            with self.subTest(route=name):
                response=self.client.get(reverse(name,args=[self.checklist.pk,row['id']]))
                self.assertEqual(response.status_code,404)
                response.close()
        self.assertTrue(Path(SurveyDocument.objects.get(pk=row['id']).original.path).exists())

    def test_malformed_historical_revision_is_controlled_not_found_on_both_routes(self):
        row=self.uploaded();self.client.force_login(self.admin)
        for name in ['photo_capture_document','survey_processing_document']:
            url=reverse(name,args=[self.checklist.pk,row['id']])
            for value in ['', 'not-a-revision', '-1', '²', '9'*5000]:
                with self.subTest(route=name,revision=value[:20]):
                    self.assertEqual(self.client.get(url,{'revision_id':value}).status_code,404)

    def test_missing_task_removal_returns_not_found_without_changing_document(self):
        row=self.uploaded()
        before=Path(SurveyDocument.objects.get(pk=row['id']).original.path).read_bytes()
        response=self.client.post(reverse('photo_capture_document_remove',args=[999999999]),
            {'document_id':row['id'],'expected_digest':'invalid'},content_type='application/json')
        self.assertEqual(response.status_code,404)
        self.assertEqual(SurveyDocument.objects.count(),1)
        self.assertEqual(Path(SurveyDocument.objects.get(pk=row['id']).original.path).read_bytes(),before)

    def test_retained_document_requires_exact_authorised_historical_revision_on_both_routes(self):
        row=self.uploaded();self.upload('Civil');submitted,_=self.submit()
        self.assertEqual(submitted.status_code,201,submitted.content)
        revision=self.checklist.processing_revisions.get()
        # Return the real frozen submission so an Engineer may correct its draft.
        self.client.force_login(self.quality)
        from .review_route_service import route_context
        self.checklist.refresh_from_db()
        returned=self.client.post(reverse('review_route_action',args=[self.checklist.pk]),
            {'action':'reject','reason':'Synthetic return for document correction',
             'expected_token':route_context(self.quality,self.checklist)['token'],
             'return_to':reverse('photo_workspace',args=[self.checklist.pk])+'?qa_step=decision'},HTTP_ACCEPT='application/json')
        self.assertEqual(returned.status_code,200,returned.content)
        self.client.force_login(self.engineer)
        removed=self.post('photo_capture_document_remove',{'document_id':row['id'],'expected_digest':self.state()['digest']})
        self.assertEqual(removed.status_code,200,removed.content)
        for actor in [self.engineer,self.admin]:
            self.client.force_login(actor)
            for name in ['photo_capture_document','survey_processing_document']:
                url=reverse(name,args=[self.checklist.pk,row['id']])
                with self.subTest(role=actor.profile.role,route=name):
                    self.assertEqual(self.client.get(url).status_code,404)
                    self.assertEqual(self.read(self.client.get(url,{'revision_id':revision.pk})),self.raw('sketch'))
                    self.assertEqual(self.client.get(url,{'revision_id':999999999}).status_code,404)
