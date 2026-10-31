"""Protected PDF raster previews use actual local parsing and preserve originals."""
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import hashlib

from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from reportlab.pdfgen import canvas

from . import test_engineer_documents as fixtures
from .survey_processing_models import SurveyDocument


@override_settings(SECRET_KEY='isolated-qa-pdf-preview',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QADocumentPreviewTests(TestCase):
    setUp=fixtures.EngineerDocumentTests.setUp
    person=fixtures.EngineerDocumentTests.person
    add_photo=fixtures.EngineerDocumentTests.add_photo
    post=fixtures.EngineerDocumentTests.post
    raw=fixtures.EngineerDocumentTests.raw
    state=fixtures.EngineerDocumentTests.state
    upload=fixtures.EngineerDocumentTests.upload
    submit=fixtures.EngineerDocumentTests.submit
    qa_state=fixtures.EngineerDocumentTests.qa_state
    doc_upload=fixtures.EngineerDocumentTests.doc_upload
    uploaded=fixtures.EngineerDocumentTests.uploaded

    def source(self):
        stream=BytesIO();pdf=canvas.Canvas(stream,pagesize=(500,700))
        for number in (1,2):
            pdf.setFont('Helvetica',22);pdf.drawString(35,640,f'SYNTHETIC report page {number}')
            pdf.rect(35,440,220,140,fill=number==2);pdf.showPage()
        pdf.save();data=stream.getvalue()
        row=self.uploaded(kind='report',name='synthetic-two-page.pdf',raw=data)
        self.upload('Civil');response,_=self.submit()
        self.assertEqual(response.status_code,201,response.content)
        state=self.qa_state();document=next(doc for doc in state['documents'] if doc['id']==row['id'])
        return document,data,state

    def test_real_pdf_page_is_a_readable_bounded_png_and_reuses_its_cache(self):
        document,data,_=self.source()
        response=self.client.get(document['raster_preview_url'])
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'],'image/png')
        self.assertEqual(response['X-Document-Preview-Page'],'1')
        self.assertEqual(response['X-Document-Preview-Pages'],'2')
        self.assertIn('private',response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        image_data=b''.join(response.streaming_content)
        image=Image.open(BytesIO(image_data));self.assertLessEqual(max(image.size),1600)
        self.assertGreater(min(image.size),500)
        self.assertLess(min(low for low,high in image.getextrema()),200)
        with patch('core.pdf_tools.PDFPage.render_png',side_effect=AssertionError('Do not render an unchanged page twice')):
            repeated=self.client.get(document['raster_preview_url'])
            self.assertEqual(repeated.status_code,200)
            self.assertEqual(b''.join(repeated.streaming_content),image_data)
        original=SurveyDocument.objects.get(pk=document['id'])
        self.assertEqual(Path(original.original.path).read_bytes(),data)
        self.assertEqual(original.sha256,hashlib.sha256(data).hexdigest())

    def test_authorised_preview_is_local_without_a_legacy_pdf_engine_or_service(self):
        with patch.dict('sys.modules', {'pymupdf': None, 'fitz': None}):
            document,data,_=self.source()
            response=self.client.get(document['raster_preview_url'])
            self.assertEqual(response.status_code,200)
            self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG'))
        original=SurveyDocument.objects.get(pk=document['id'])
        self.assertEqual(Path(original.original.path).read_bytes(),data)

    def test_page_navigation_invalid_pages_and_original_download_are_distinct(self):
        document,data,_=self.source()
        second=self.client.get(document['raster_preview_url'].replace('page=1','page=2'))
        self.assertEqual(second.status_code,200)
        self.assertEqual(second['X-Document-Preview-Page'],'2')
        self.assertTrue(b''.join(second.streaming_content).startswith(b'\x89PNG\r\n\x1a\n'))
        for page in ('0','3','-1','abc','9'*100,'²'):
            response=self.client.get(document['raster_preview_url'].replace('page=1','page='+page))
            self.assertEqual(response.status_code,404,page)
        original=self.client.get(document['original_url'])
        self.assertEqual(original['Content-Type'],'application/pdf')
        self.assertEqual(b''.join(original.streaming_content),data)

    def test_raster_preview_keeps_source_and_project_access_checks(self):
        document,_,state=self.source()
        self.client.force_login(self.engineer)
        current=self.client.get(document['raster_preview_url'])
        self.assertEqual(current.status_code,200)
        self.assertTrue(b''.join(current.streaming_content).startswith(b'\x89PNG'))
        current.close()
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(document['raster_preview_url']).status_code,404)
        self.client.logout()
        self.assertEqual(self.client.get(document['raster_preview_url']).status_code,302)
        self.client.force_login(self.quality)
        foreign=reverse('photo_capture_document',args=[self.checklist.pk+100,document['id']])
        self.assertEqual(self.client.get(foreign,{'preview':1,'raster':1,'revision_id':state['revision_id']}).status_code,404)

    def test_changed_original_does_not_return_an_old_cached_success(self):
        document,_,_=self.source()
        rendered=self.client.get(document['raster_preview_url'])
        self.assertEqual(rendered.status_code,200)
        b''.join(rendered.streaming_content)
        original=SurveyDocument.objects.get(pk=document['id'])
        Path(original.original.path).write_bytes(b'not the recorded original')
        response=self.client.get(document['raster_preview_url'])
        self.assertEqual(response.status_code,409)
        self.assertIn('source',response.json()['error'].lower())
