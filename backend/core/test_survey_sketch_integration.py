"""Real upload/submission/drawing integration with isolated synthetic sketches."""
import hashlib
from pathlib import Path

import pymupdf
from django.test import TestCase, override_settings
from django.urls import reverse

from . import survey_processing as pipeline
from . import test_engineer_documents as documents
from .test_survey_sketches import sketch_record
from .survey_processing_models import SurveyDocument, SurveySourceAnalysis, SurveyProcessingResult


@override_settings(SECRET_KEY='isolated-sketch-render-integration', ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SketchDrawingIntegrationTests(TestCase):
    setUp = documents.EngineerDocumentTests.setUp
    person = documents.EngineerDocumentTests.person
    add_photo = documents.EngineerDocumentTests.add_photo
    post = documents.EngineerDocumentTests.post
    raw = documents.EngineerDocumentTests.raw
    state = documents.EngineerDocumentTests.state
    upload = documents.EngineerDocumentTests.upload
    submit = documents.EngineerDocumentTests.submit
    doc_upload = documents.EngineerDocumentTests.doc_upload
    uploaded = documents.EngineerDocumentTests.uploaded

    def prepared(self, kind='hand_sketch'):
        source = sketch_record()
        row = self.uploaded(kind=kind, raw=source['raw'])
        self.upload('Civil')
        response, _ = self.submit()
        self.assertEqual(response.status_code, 201, response.content)
        revision = self.checklist.processing_revisions.get()
        finding = {'source_id': 'document:' + str(row['id']), 'category': 'measurement',
            'component': 'Recorded width', 'value': 3500, 'unit': 'mm', 'basis': 'recorded',
            'evidence_quote': '3500 mm', 'recorded_measurement': True, 'confidence': 'high'}
        analysis = {'sha256': hashlib.sha256(source['raw']).hexdigest(), 'findings': [finding],
            'missing': ['Right side dimension unreadable'], 'conflicts': []}
        SurveySourceAnalysis.objects.create(revision=revision, source_id=finding['source_id'],
            payload=analysis, digest=pipeline.digest(analysis))
        payload = pipeline.prepare_checklist(revision.snapshot,
            {'findings': [finding], 'missing': [], 'conflicts': []})
        SurveyProcessingResult.objects.create(revision=revision, payload=payload, digest=pipeline.digest(payload))
        return revision, payload, row, source

    def test_uploaded_sketch_produces_protected_pdf_with_missing_measurement_highlight(self):
        revision, payload, row, source = self.prepared()
        drawing = pipeline.render_drawing_set(revision, payload)
        sketch_sheets = [sheet for sheet in drawing.geometry['sheets'] if sheet['key'].startswith('hand_sketch_')]
        self.assertTrue(sketch_sheets, 'The actual survey renderer must include the uploaded hand sketch.')
        with pymupdf.open(drawing.manifest['pdf']) as pdf:
            text = ''.join(page.get_text() for page in pdf)
            self.assertIn('3500 mm', text)
            self.assertIn('Right side dimension unreadable', text)
            self.assertIn('Not to Scale', text)
        document = SurveyDocument.objects.get(pk=row['id'])
        self.assertEqual(Path(document.original.path).read_bytes(), source['raw'])
        url = reverse('survey_processing_output', args=[self.checklist.pk, drawing.pk, 0, 'pdf'])
        self.client.force_login(self.quality)
        drawing_workspace = reverse('survey_processing_workspace', args=[self.checklist.pk])
        self.assertContains(self.client.get(reverse('photo_workspace', args=[self.checklist.pk])),
                            drawing_workspace + '#drawings')
        self.assertEqual(self.client.get(drawing_workspace).status_code, 200)
        download = self.client.get(url)
        try:
            self.assertEqual(download.status_code, 200)
            self.assertTrue(b''.join(download.streaming_content).startswith(b'%PDF-'))
        finally:
            download.close()
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertFalse(drawing.released)
        self.assertEqual(pipeline.render_drawing_set(revision, payload).pk, drawing.pk)

    def test_report_is_not_automatically_treated_as_a_hand_sketch(self):
        revision, payload, _, _ = self.prepared(kind='report')
        drawing = pipeline.render_drawing_set(revision, payload)
        self.assertFalse(any(sheet['key'].startswith('hand_sketch_') for sheet in drawing.geometry['sheets']))
