"""Real Unicode drawing exports from synthetic records; no DB/model/network."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import ezdxf
import pymupdf

from .survey_drawings import _digest, _text, build_geometry, render_outputs


class SurveyUnicodeRegressions(TestCase):
    def geometry(self, *, label='حالة الخزانة', value='تم الفحص | Cabinet 123'):
        return build_geometry(
            {'id': 300, 'project': {'id': 7, 'name': 'مشروع الرياض'},
             'site_id': 'موقع الرياض', 'date': '2026-10-23'},
            [{'sheet': 'equipment_schedule', 'label': label, 'value': value,
              'sources': [{'id': 1, 'type': 'synthetic', 'label': 'صورة الاختبار'}]}],
        )

    def test_normalization_preserves_letters_and_removes_unsafe_controls(self):
        self.assertEqual(_text('موقع الرياض'), 'موقع الرياض')
        self.assertEqual(_text('Cafe\u0301\nالرياض\x00\u202e'), 'Café الرياض')
        self.assertEqual(_text('ر\u200cی\u200dاض'), 'ر\u200cی\u200dاض')
        self.assertEqual(_text(None), '')
        self.assertEqual(len(_text('أ' * 600)), 500)

    def test_structured_values_and_geometry_keep_logical_unicode(self):
        self.assertEqual(json.loads(_text({'الموقع': 'الرياض'})), {'الموقع': 'الرياض'})
        geometry = self.geometry()
        self.assertEqual(geometry['site_id'], 'موقع الرياض')
        self.assertEqual(geometry['project'], 'مشروع الرياض')
        sheet = next(s for s in geometry['sheets'] if s['key'] == 'equipment_schedule')
        self.assertEqual(sheet['findings'][0]['label'], 'حالة الخزانة')
        self.assertIn('تم الفحص', sheet['findings'][0]['answer'])

    def test_real_pdf_and_dxf_preserve_arabic_and_mixed_labels(self):
        with TemporaryDirectory(prefix='ifield-unicode-') as directory:
            result = render_outputs(self.geometry(), Path(directory), prepared_by='مهندس الاختبار')
            final = json.loads(Path(result['geometry']).read_text(encoding='utf-8'))
            geometry_digest = final.pop('digest')
            self.assertEqual(geometry_digest, _digest(final))
            self.assertEqual(final['site_id'], 'موقع الرياض')
            with pymupdf.open(result['pdf']) as document:
                # A PDF extractor can separate visual bidi/font runs by line
                # breaks. Whitespace is presentation, not a changed field value.
                pdf_text = ' '.join(' '.join(page.get_text() for page in document).split())
                for expected in ('موقع الرياض', 'مشروع الرياض', 'حالة الخزانة',
                                 'تم الفحص | Cabinet 123', 'مهندس الاختبار'):
                    self.assertIn(expected, pdf_text)
                self.assertIn(geometry_digest, document.metadata['subject'])
                self.assertTrue(any('NotoNaskhArabic' in font[3].replace(' ', '')
                                    for page in document for font in page.get_fonts()))
                for page in document:
                    # Labels remain text/vector content, not a screenshot substitute.
                    self.assertEqual(page.get_images(), [])
                    page.get_pixmap(alpha=False)
                streams = b'\n'.join(document.xref_stream(xref)
                                     for page in document for xref in page.get_contents())
                for sheet in final['sheets']:
                    for entity in sheet['entities']:
                        if entity['kind'] == 'text' and not entity['text'].isascii():
                            logical = ('FEFF' + entity['text'].encode('utf-16-be').hex()).encode('ascii')
                            self.assertIn(b'/ActualText <' + logical + b'>', streams)
            for sheet, paths in zip(final['sheets'], result['sheets']):
                drawing = ezdxf.readfile(paths['dxf'])
                self.assertFalse(drawing.audit().has_errors)
                entities = list(drawing.modelspace())
                self.assertEqual(len(entities), len(sheet['entities']))
                for source, drawn in zip(sheet['entities'], entities):
                    self.assertEqual(drawn.get_xdata('ISURVIX')[1].value, _digest(source))
                    if source['kind'] == 'text':
                        self.assertEqual(drawn.dxf.text, source['text'])
                self.assertTrue(any('موقع الرياض' in e.dxf.text
                                    for e in drawing.modelspace().query('TEXT')))

    def test_unicode_markup_is_literal_text_without_links_or_actions(self):
        label = 'موقع <a href="https://example.invalid">اختبار</a> & 123'
        with TemporaryDirectory(prefix='ifield-unicode-') as directory:
            result = render_outputs(self.geometry(label=label), Path(directory))
            final = json.loads(Path(result['geometry']).read_text(encoding='utf-8'))
            self.assertTrue(any(e.get('text') == label
                                for s in final['sheets'] for e in s['entities']))
            with pymupdf.open(result['pdf']) as document:
                text = '\n'.join(page.get_text() for page in document)
                self.assertIn('href="https://example.invalid">', text)
                streams = b'\n'.join(document.xref_stream(xref)
                                     for page in document for xref in page.get_contents())
                logical = ('FEFF' + label.encode('utf-16-be').hex()).encode('ascii')
                self.assertIn(b'/ActualText <' + logical + b'>', streams)
                self.assertTrue(all(not page.get_links() for page in document))

    def test_non_arabic_unicode_also_survives_real_exports(self):
        with TemporaryDirectory(prefix='ifield-unicode-') as directory:
            result = render_outputs(self.geometry(label='識別 東京', value='Café — Δοκιμή'),
                                    Path(directory))
            with pymupdf.open(result['pdf']) as document:
                text = ' '.join(' '.join(page.get_text() for page in document).split())
                self.assertIn('識別 東京', text)
                self.assertIn('Café — Δοκιμή', text)
            drawing = ezdxf.readfile(result['sheets'][1]['dxf'])
            labels = [e.dxf.text for e in drawing.modelspace().query('TEXT')]
            self.assertIn('識別 東京', labels)
            self.assertTrue(any('Café — Δοκιμή' in label for label in labels))

    def test_long_unicode_text_stays_bounded_and_renderable(self):
        geometry = self.geometry(label='الرياض ' * 40, value='تجربة ' * 65)
        with TemporaryDirectory(prefix='ifield-unicode-') as directory:
            result = render_outputs(geometry, Path(directory))
            with pymupdf.open(result['pdf']) as document:
                self.assertTrue(all('?' not in page.get_text() for page in document))
                for page in document:
                    for block in page.get_text('dict')['blocks']:
                        if block.get('type') != 0:
                            continue
                        for line in block['lines']:
                            for span in line['spans']:
                                self.assertGreaterEqual(span['size'], 2.1 * 72 / 25.4 - .01)
                                self.assertGreaterEqual(span['bbox'][0], 7 * 72 / 25.4)
                                self.assertLessEqual(span['bbox'][2], 413 * 72 / 25.4)

    def test_unsupported_unicode_fit_fails_without_publishing_partial_revision(self):
        with TemporaryDirectory(prefix='ifield-unicode-') as directory:
            with patch.object(pymupdf.Page, 'insert_htmlbox', return_value=(-1, 0)):
                with self.assertRaisesRegex(ValueError, 'Unicode drawing label'):
                    render_outputs(self.geometry(), Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])
