"""Synthetic sketch preservation and drawing export checks; no native inference."""
import hashlib
import io
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import ezdxf
import pymupdf
from PIL import Image, ImageDraw

from .survey_drawings import build_geometry, render_outputs
from .test_survey_drawings import working_directory


def sketch_record():
    image = Image.new('RGB', (1600, 1000), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((150, 200, 1300, 800), outline='black', width=5)
    draw.line((150, 200, 1300, 800), fill='black', width=3)
    draw.ellipse((650, 400, 850, 600), outline='blue', width=4)
    draw.text((600, 120), '3500 mm', fill='black', stroke_width=1)
    draw.text((1350, 500), '??', fill='red', stroke_width=1)
    stream = io.BytesIO(); image.save(stream, 'PNG'); raw = stream.getvalue()
    return {'id': 31, 'kind': 'hand_sketch', 'filename': 'synthetic-sketch.png',
            'raw': raw, 'sha256': hashlib.sha256(raw).hexdigest()}


class SurveySketchTests(TestCase):
    def geometry(self, records=None, analyses=None):
        from .survey_sketches import add_hand_sketches
        return add_hand_sketches(build_geometry({'id': 999, 'site_id': 'SYNTHETIC'}, []),
                                 records or [sketch_record()], analyses or {})

    def test_missing_analysis_retains_full_source_and_flags_unknown_dimensions(self):
        result = self.geometry()
        sheet = next(s for s in result['sheets'] if s['key'].startswith('hand_sketch'))
        self.assertEqual(sheet['scale'], 'Not to Scale')
        self.assertTrue(any('DIMENSIONS NEED REVIEW' in e.get('text', '') and e['layer'] == 'WARNINGS'
                            for e in sheet['entities']))
        self.assertTrue(any(e['kind'] == 'polyline' and e['layer'] == 'SKETCH_TRACE' for e in sheet['entities']))
        self.assertIn(sketch_record()['sha256'], str(sheet['source']))

    def test_pdf_dxf_bundle_preserve_original_and_red_dimension_flags(self):
        raw = sketch_record()
        analysis = {'source_id': 'document:31', 'sha256': raw['sha256'], 'findings': [
            {'category': 'measurement', 'component': 'Overall width', 'value': 3500, 'unit': 'mm',
             'basis': 'recorded', 'evidence_quote': '3500 mm', 'recorded_measurement': True}],
            'missing': ['Right side dimension is unreadable'], 'conflicts': []}
        result = self.geometry([raw], {'document:31': analysis})
        with working_directory() as temp:
            manifest = render_outputs(result, Path(temp))
            sheet = next(s for s in manifest['sheets'] if s['key'].startswith('hand_sketch'))
            with pymupdf.open(manifest['pdf']) as document:
                page = document[sheet['sheet_no'] - 1]
                text = page.get_text()
                self.assertIn('3500 mm', text)
                self.assertIn('Right side dimension is unreadable', text)
                self.assertIn('Not to Scale', text)
                spans = [s for b in page.get_text('dict')['blocks'] if 'lines' in b
                         for line in b['lines'] for s in line['spans']]
                self.assertTrue(any('Right side' in s['text'] and s['color'] != 0x1e1e1e for s in spans))
                self.assertGreaterEqual(len(page.get_images()), 2)
            cad = ezdxf.readfile(sheet['dxf'])
            self.assertTrue(list(cad.modelspace().query('LWPOLYLINE[layer=="SKETCH_TRACE"]')))
            drawing = json.loads(Path(manifest['geometry']).read_text())
            reference = next(e for s in drawing['sheets'] for e in s['entities']
                             if e.get('sketch_role') == 'reference')
            with Image.open(Path(manifest['output_dir']) / reference['path']) as retained:
                self.assertEqual(retained.size, (1600, 1000))
                self.assertEqual(retained.convert('RGB').tobytes(), Image.open(io.BytesIO(raw['raw'])).tobytes())

    def test_changed_original_and_wrong_analysis_hash_are_rejected(self):
        bad = sketch_record(); bad['sha256'] = '0' * 64
        with self.assertRaises(ValueError): self.geometry([bad])
        with self.assertRaises(ValueError): self.geometry(analyses={'document:31': {'sha256': '0' * 64}})

    def test_unsupported_or_unquoted_dimension_never_becomes_recorded(self):
        raw = sketch_record()
        analysis = {'sha256': raw['sha256'], 'findings': [
            {'category': 'measurement', 'value': 900, 'unit': 'mm', 'basis': 'visible',
             'component': 'Guessed height', 'evidence_quote': ''}], 'missing': [], 'conflicts': []}
        result = self.geometry([raw], {'document:31': analysis})
        texts = ' '.join(e.get('text', '') for s in result['sheets'] for e in s['entities'])
        self.assertNotIn('900 mm', texts)
        self.assertIn('DIMENSIONS NEED REVIEW', texts)

    def test_pdf_multipart_analysis_and_every_page_are_preserved(self):
        document = pymupdf.open()
        for index in range(2):
            page = document.new_page(width=500, height=300)
            page.draw_rect((50, 60, 400, 220))
            page.insert_text((80, 40), f'Synthetic sketch page {index+1}')
        raw = document.tobytes(); document.close()
        record = {'id': 22, 'kind': 'hand_sketch', 'filename': 'synthetic.pdf', 'raw': raw,
                  'sha256': hashlib.sha256(raw).hexdigest()}
        analyses = {'document:22:page:1:part:1': {'sha256': record['sha256'], 'missing': ['Left span unreadable']},
                    'document:22:page:1:part:2': {'sha256': record['sha256'], 'missing': ['Rear span absent']}}
        result = self.geometry([record], analyses)
        sheets = [s for s in result['sheets'] if s['key'].startswith('hand_sketch')]
        self.assertEqual(len(sheets), 2)
        self.assertIn('Rear span absent', str(sheets[0]))
        self.assertIn('Left span unreadable', str(sheets[0]))
        self.assertEqual(sheets[1]['source']['reference'], 'page 2')

    def test_note_overflow_creates_review_continuation_without_silent_omission(self):
        raw = sketch_record()
        analysis = {'sha256': raw['sha256'], 'findings': [],
                    'missing': [f'Span {i}: unreadable' for i in range(20)]}
        result = self.geometry([raw], {'document:31': analysis})
        sheets = [s for s in result['sheets'] if s['key'].startswith('hand_sketch')]
        self.assertGreater(len(sheets), 1)
        self.assertIn('Span 19: unreadable', str(sheets))

    def test_hand_sketch_kind_reaches_existing_vision_prompt(self):
        from . import survey_evidence as evidence
        raw = sketch_record()
        source = next(evidence.extract_sources([], [raw]))
        self.assertEqual(source['metadata']['kind'], 'hand_sketch')
        response = {'message': {'content': json.dumps({'findings': [], 'missing': [], 'conflicts': [], 'suggested_items': []})}}
        with patch.object(evidence, '_vision_check'), patch.object(evidence.local_ai, 'ollama', return_value=response) as native:
            evidence.analyse_source(source, 'synthetic-local-model')
        prompt = native.call_args.args[1]['messages'][0]['content']
        self.assertIn('unreadable dimensions', prompt)
        self.assertIn('Not to Scale', prompt)
        self.assertEqual(len(native.call_args.args[1]['messages'][1]['images']), 1)

    def test_trace_overflow_is_explicit_and_keeps_complete_images(self):
        with patch('core.survey_sketches.MAX_TRACE_POINTS', 1):
            result = self.geometry()
        sheet = next(s for s in result['sheets'] if s['key'].startswith('hand_sketch'))
        self.assertIn('Trace limit reached', str(sheet))
        self.assertEqual(len([e for e in sheet['entities'] if e['kind'] == 'image']), 2)

    def workbook_record(self, embedded=True):
        from openpyxl import Workbook
        from openpyxl.drawing.image import Image as WorkbookImage
        book = Workbook(); sheet = book.active; sheet.title = 'Sketch'
        sheet['B2'] = 'Overall width 3500 mm'
        if embedded:
            sheet.add_image(WorkbookImage(io.BytesIO(sketch_record()['raw'])), 'D5')
        stream = io.BytesIO(); book.save(stream); book.close(); raw = stream.getvalue()
        return {'id': 41, 'kind': 'hand_sketch', 'filename': 'synthetic-sketch.xlsx',
                'raw': raw, 'sha256': hashlib.sha256(raw).hexdigest()}

    def test_workbook_embedded_sketch_retains_full_image_sheet_reference_and_dimensions(self):
        record = self.workbook_record()
        analysis = {'sha256': record['sha256'], 'findings': [
            {'category': 'measurement', 'component': 'Overall width', 'value': 3500, 'unit': 'mm',
             'basis': 'recorded', 'evidence_quote': 'Overall width 3500 mm', 'recorded_measurement': True}]}
        result = self.geometry([record], {'document:41:sheet:Sketch:part:1': analysis})
        sheet = next(s for s in result['sheets'] if s['key'].startswith('hand_sketch'))
        self.assertEqual(sheet['source']['source_id'], 'document:41:sheet:Sketch:image:1')
        self.assertIn('worksheet Sketch', sheet['source']['reference'])
        self.assertIn('row 5', sheet['source']['reference'])
        self.assertIn('3500 mm', str(sheet))
        reference = next(e for e in sheet['entities'] if e.get('sketch_role') == 'reference')
        self.assertEqual((reference['pixel_width'], reference['pixel_height']), (1600, 1000))
        with working_directory() as temp:
            manifest = render_outputs(result, Path(temp))
            self.assertTrue(Path(manifest['pdf']).is_file())

    def test_workbook_without_raster_image_yields_warning_sheet_and_keeps_processing(self):
        record = self.workbook_record(embedded=False)
        result = self.geometry([record])
        sheet = next(s for s in result['sheets'] if s['key'].startswith('hand_sketch'))
        self.assertIn('No supported embedded image', str(sheet))
        self.assertFalse(any(e['layer'] == 'SKETCH_TRACE' for e in sheet['entities']))
        self.assertEqual(sheet['source']['source_id'], 'document:41:sheet:Sketch')
        self.assertEqual(result['sheets'][0]['key'], 'register')
        with working_directory() as temp:
            manifest = render_outputs(result, Path(temp))
            with pymupdf.open(manifest['pdf']) as document:
                self.assertIn('No supported embedded image', document[-1].get_text())

    def test_register_lists_appended_sketch_and_current_warning_counts_in_both_exports(self):
        result = self.geometry()
        register = next(s for s in result['sheets'] if s['key'] == 'register')
        sketch = next(s for s in result['sheets'] if s['key'].startswith('hand_sketch'))
        text = ' '.join(e.get('text', '') for e in register['entities'])
        self.assertIn(sketch['number'], text)
        expected = f"{len(result['missing_information'])} missing sheet categories; {len(result['warnings'])} warnings"
        self.assertIn(expected, text)
        with working_directory() as temp:
            manifest = render_outputs(result, Path(temp))
            with pymupdf.open(manifest['pdf']) as document:
                self.assertIn(sketch['number'], document[0].get_text())
                self.assertIn(expected, document[0].get_text())
            register_file = next(s['dxf'] for s in manifest['sheets'] if s['key'] == 'register')
            labels = ' '.join(e.dxf.text for e in ezdxf.readfile(register_file).modelspace().query('TEXT'))
            self.assertIn(sketch['number'], labels)
            self.assertIn(expected, labels)

    def test_register_continues_all_rows_and_respects_total_sheet_bound(self):
        from .survey_drawings import refresh_drawing_register
        result = build_geometry({'id': 999, 'site_id': 'SYNTHETIC'}, [])
        result['sheets'].extend({'key': f'hand_sketch_{i}', 'number': f'SK-{i+2:03d}',
            'title': f'Synthetic source {i}', 'scale': 'Not to Scale', 'findings': [], 'entities': []}
            for i in range(20))
        refresh_drawing_register(result)
        registers = [s for s in result['sheets'] if s['key'].startswith('register')]
        self.assertGreater(len(registers), 1)
        indexed = ' '.join(e.get('text', '') for s in registers for e in s['entities'])
        for sheet in result['sheets'][1:]:
            self.assertIn(sheet['number'], indexed)
        result['sheets'].extend({'key': f'hand_sketch_extra_{i}', 'number': f'EX-{i}',
            'title': 'Bound fixture', 'scale': 'Not to Scale', 'findings': [], 'entities': []}
            for i in range(10))
        with self.assertRaisesRegex(ValueError, 'sheet limit'):
            refresh_drawing_register(result)
