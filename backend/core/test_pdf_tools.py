"""Real local PDF conversion preserves evidence and never needs a PDF service."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image
from reportlab.lib.pdfencrypt import StandardEncryption
from reportlab.pdfgen import canvas


def pdf_bytes(*, pages=1, size=(500, 700), text='SYNTHETIC SITE Z12345 recorded length 2500 mm', encrypted=False):
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=size,
        encrypt=StandardEncryption('synthetic-user', ownerPassword='synthetic-owner') if encrypted else None)
    for index in range(pages):
        if text:
            pdf.setFont('Helvetica', 16)
            pdf.drawString(25, size[1] - 40, text)
            pdf.rect(25, 35, 100, 60, fill=1)
        pdf.showPage()
    pdf.save()
    return output.getvalue()


class LocalPDFToolsTests(SimpleTestCase):
    def test_existing_evidence_pipeline_converts_without_legacy_pdf_engine(self):
        from .survey_evidence import extract_sources, validate_document
        raw = pdf_bytes()
        with patch.dict('sys.modules', {'pymupdf': None, 'fitz': None}):
            uploaded = validate_document(SimpleUploadedFile('synthetic.pdf', raw))
            sources = list(extract_sources([], [{'id': 42, 'filename': 'synthetic.pdf',
                'raw': raw, 'sha256': uploaded['sha256']}]))
        self.assertEqual(uploaded['raw'], raw)
        self.assertEqual(sources[0]['source_id'], 'document:42:page:1')
        self.assertIn('2500 mm', sources[0]['text'])
        self.assertTrue(sources[0]['image_b64'])
        self.assertEqual(sources[0]['metadata']['pdf_engine'], 'pypdfium2')

    def test_digital_text_and_actual_png_have_readable_bounded_dimensions(self):
        from .pdf_tools import open_pdf
        raw = pdf_bytes()
        with open_pdf(raw) as pdf:
            self.assertEqual(len(pdf), 1)
            page = pdf[0]
            self.assertEqual(page.size, (500.0, 700.0))
            self.assertIn('Z12345', page.extract_text())
            image_bytes = page.render_png(max_edge=1598, max_scale=2)
        with Image.open(BytesIO(image_bytes)) as image:
            self.assertEqual(image.format, 'PNG')
            self.assertLessEqual(max(image.size), 1598)
            self.assertGreater(min(image.size), 500)
            self.assertLess(min(channel[0] for channel in image.getextrema()), 200)

    def test_corrupt_encrypted_and_oversized_bytes_are_rejected(self):
        from .pdf_tools import PDFError, open_pdf
        for raw in (b'not a PDF', b'%PDF-1.4\ncorrupt', pdf_bytes(encrypted=True)):
            with self.subTest(length=len(raw)), self.assertRaises(PDFError):
                open_pdf(raw)
        with self.assertRaises(PDFError):
            open_pdf(pdf_bytes(), max_bytes=10)

    def test_missing_local_converter_is_a_configuration_error_not_a_paid_fallback(self):
        from .pdf_tools import PDFError, open_pdf
        with patch.dict('sys.modules', {'pypdfium2': None}):
            with self.assertRaisesMessage(PDFError, 'local PDF tools are unavailable'):
                open_pdf(pdf_bytes())

    def test_page_count_is_checked_before_page_rendering(self):
        from .pdf_tools import PDFError, open_pdf
        with patch('pypdfium2.PdfPage.render', side_effect=AssertionError('Must not render')):
            with self.assertRaises(PDFError):
                open_pdf(pdf_bytes(pages=2), max_pages=1)

    def test_huge_page_geometry_is_rejected_before_bitmap_allocation(self):
        from .pdf_tools import PDFError, open_pdf
        with open_pdf(pdf_bytes(size=(20000, 20000), text='')) as pdf:
            with patch('pypdfium2.PdfPage.render', side_effect=AssertionError('Must not render')):
                with self.assertRaises(PDFError):
                    pdf[0].render_png()

    def test_text_character_count_is_bounded_before_extracting_text(self):
        from .pdf_tools import PDFError, open_pdf
        with open_pdf(pdf_bytes(text='X' * 200)) as pdf:
            with patch('pypdfium2.PdfTextPage.get_text_range', side_effect=AssertionError('Must not materialise')):
                with self.assertRaises(PDFError):
                    pdf[0].extract_text(max_chars=20)

    def test_invalid_page_numbers_and_closed_document_fail_clearly(self):
        from .pdf_tools import PDFError, open_pdf
        pdf = open_pdf(pdf_bytes())
        for number in (-1, 1, True, '0'):
            with self.subTest(number=number), self.assertRaises(PDFError):
                pdf[number]
        pdf.close()
        with self.assertRaises(PDFError):
            pdf[0]

    def test_engine_identity_is_stable_for_preview_cache_keys(self):
        from .pdf_tools import renderer_identity
        identity = renderer_identity()
        self.assertEqual(identity, renderer_identity())
        self.assertIn('pypdfium2', identity)
        self.assertIn('5.14.0', identity)

    def test_hand_sketch_pdf_pages_use_free_local_rendering_without_changing_ids(self):
        from .survey_sketches import _pages
        raw = pdf_bytes()
        with patch.dict('sys.modules', {'pymupdf': None, 'fitz': None}):
            pages = list(_pages({'id': 18, 'filename': 'synthetic-sketch.pdf'}, raw))
        self.assertEqual(pages[0][:2], ('document:18:page:1', 'page 1'))
        self.assertEqual(pages[0][2].mode, 'RGB')
        self.assertLessEqual(max(pages[0][2].size), 3000)


class LocalPDFOCRWorkerTests(SimpleTestCase):
    def source(self, text=''):
        from .survey_evidence import extract_sources
        raw = pdf_bytes(text=text)
        return next(extract_sources([], [{'id': 42, 'filename': 'synthetic.pdf',
            'raw': raw, 'sha256': hashlib.sha256(raw).hexdigest()}]))

    def run_worker(self, source, report):
        from .survey_evidence import analyse_source
        captured = []
        def transport(path, payload=None, **_):
            captured.append(payload)
            return {'message': {'content': json.dumps({'findings': [], 'missing': [],
                'conflicts': [], 'suggested_items': []})}, 'done_reason': 'stop'}
        with patch('core.local_evidence_tools.local_ocr', return_value=report) as engine:
            result = analyse_source(source, 'synthetic-model', transport=transport,
                                    verify=lambda *_: None)
        content = captured[0]['messages'][1]['content']
        wire = json.loads(content.split('\n', 1)[1].rsplit('\n', 1)[0])
        return result, wire, captured, engine

    def test_image_only_pdf_ocr_is_worker_only_and_retains_unverified_provenance(self):
        with patch('core.local_evidence_tools.local_ocr', side_effect=AssertionError('Extraction must remain pure')):
            source = self.source()
        report = {'status': 'complete', 'provenance': {'engine': 'rapidocr-onnxruntime',
            'version': '1.4.4', 'verification_status': 'unverified_source_text'},
            'ocr_lines': [{'text': 'RECORDED 2500 mm', 'confidence': .97, 'box': [[1, 1], [50, 1], [50, 10], [1, 10]]}],
            'errors': []}
        result, wire, requests, engine = self.run_worker(source, report)
        engine.assert_called_once()
        self.assertIn('2500 mm', wire['evidence_text'])
        self.assertEqual(result['local_ocr']['provenance']['verification_status'], 'unverified_source_text')
        self.assertEqual(result['local_ocr']['status'], 'complete')
        self.assertEqual(result['local_ocr']['ocr_lines'][0]['confidence'], .97)
        self.assertEqual(result['verification_status'], 'needs_review')
        self.assertEqual(result['findings'], [])
        self.assertTrue(requests[0]['messages'][1]['images'])

    def test_ocr_unavailable_is_explicit_without_losing_actual_image(self):
        report = {'status': 'unavailable', 'provenance': {'engine': 'rapidocr-onnxruntime',
            'version': '1.4.4', 'verification_status': 'unverified_source_text'},
            'ocr_lines': [], 'errors': [{'tool': 'ocr', 'code': 'unavailable'}]}
        result, wire, requests, _ = self.run_worker(self.source(), report)
        self.assertEqual(result['local_ocr']['status'], 'unavailable')
        self.assertTrue(any('OCR' in note for note in result['missing']))
        self.assertTrue(requests[0]['messages'][1]['images'])
        self.assertEqual(wire['evidence_text'], '')

    def test_digital_pdf_does_not_repeat_text_extraction_through_ocr(self):
        result, wire, _, engine = self.run_worker(self.source('NATIVE PDF TEXT 2500 mm'), {})
        engine.assert_not_called()
        self.assertIn('2500 mm', wire['evidence_text'])
        self.assertNotIn('local_ocr', result)

    def test_long_ocr_retains_lines_but_bounds_prompt_text_and_reports_truncation(self):
        source = self.source()
        source['metadata']['recorded_note'] = 'x' * 5000
        report = {'status': 'complete', 'provenance': {'engine': 'rapidocr-onnxruntime',
            'version': '1.4.4', 'verification_status': 'unverified_source_text'},
            'ocr_lines': [{'text': 'Z' * 200, 'confidence': .91, 'box': []} for _ in range(64)],
            'errors': []}
        result, wire, _, _ = self.run_worker(source, report)
        self.assertLessEqual(len(wire['evidence_text']), 12000)
        self.assertTrue(result['local_ocr']['prompt_text_truncated'])
        self.assertEqual(len(result['local_ocr']['ocr_lines']), 64)
        self.assertEqual(wire['recorded_metadata']['recorded_note'], 'x' * 5000)


class LocalPDFRemoteOCRTests(SimpleTestCase):
    def report(self):
        return {'status': 'complete', 'provenance': {'engine': 'rapidocr-onnxruntime',
            'version': '1.4.4', 'verification_status': 'unverified_source_text'},
            'ocr_lines': [{'text': 'RECORDED 2500 mm', 'confidence': .97, 'box': []}],
            'errors': [], 'prompt_text_truncated': False}

    def task_and_result(self):
        task = SimpleNamespace(key='document:42:page:1', image=SimpleNamespace(name='previews/synthetic.jpg'),
            payload={'sha256': 'a' * 64, 'source_type': 'pdf_page', 'reference': 'page 1',
                     'field_catalog': [], 'text': ''})
        raw = {'source_id': task.key, 'sha256': task.payload['sha256'], 'model': 'synthetic-model',
            'findings': [], 'missing': [], 'conflicts': [], 'suggested_items': [], 'local_ocr': self.report()}
        return task, raw

    def test_remote_source_retains_local_ocr_as_unverified_evidence(self):
        from .remote_worker_service import _validate_source
        task, raw = self.task_and_result()
        result = _validate_source(task, raw, 'synthetic-model')
        self.assertEqual(result['local_ocr'], raw['local_ocr'])
        self.assertEqual(result['verification_status'], 'needs_review')
        self.assertEqual(result['findings'], [])

    def test_remote_source_rejects_malformed_or_approval_shaped_ocr(self):
        from django.core.exceptions import ValidationError
        from .remote_worker_service import _validate_source
        for changes in ({'status': 'approved'}, {'approved': True},
                        {'errors': [{'tool': 'ocr', 'code': 'unavailable'}]},
                        {'ocr_lines': [{'text': 'x', 'confidence': float('nan'), 'box': []}]},
                        {'ocr_lines': [{'text': 'x' * 201, 'confidence': .9, 'box': []}]}):
            task, raw = self.task_and_result()
            raw['local_ocr'].update(changes)
            with self.subTest(fields=list(changes)), self.assertRaises(ValidationError):
                _validate_source(task, raw, 'synthetic-model')

    def test_remote_implementation_pin_covers_local_converter_and_ocr_helpers(self):
        from .remote_worker_service import versions, _compatible
        from django.core.exceptions import ValidationError
        before = versions()
        read = Path.read_bytes
        for changed in ('pdf_tools.py', 'local_evidence_tools.py'):
            def altered(path):
                value = read(path)
                return value + b'\n# isolated helper-version change\n' if path.name == changed else value
            with self.subTest(module=changed), patch.object(Path, 'read_bytes', altered):
                self.assertNotEqual(before['implementation'], versions()['implementation'])
                with self.assertRaises(ValidationError):
                    _compatible({'versions': before})
