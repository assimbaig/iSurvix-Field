"""Bounded local PDF text/raster conversion using permissively licensed engines.

No service endpoint, credential, download, document action or script is invoked.
Original PDF bytes are read only. Uploaded text is evidence, never instructions.
PDFium calls are serialized because the native library is not thread-safe.
"""
from contextlib import contextmanager
from io import BytesIO
import json
import math
import re
from threading import RLock


MAX_BYTES = 30 * 1024 * 1024
MAX_PAGES = 80
MAX_PAGE_AREA = 100_000_000
MAX_TEXT_CHARS = 240_000
MAX_RASTER_PIXELS = 24_000_000
_PDFIUM_LOCK = RLock()


class PDFError(ValueError):
    """A safe diagnostic without uploaded content, local paths or credentials."""


def renderer_identity():
    import pypdf
    import pypdfium2
    return f'pypdfium2/{pypdfium2.PYPDFIUM_INFO};pdfium/{pypdfium2.PDFIUM_INFO};pypdf/{pypdf.__version__}'


class PDFDocument:
    def __init__(self, raw, *, max_bytes=MAX_BYTES, max_pages=MAX_PAGES):
        self._pdf = None
        if (type(max_bytes) is not int or max_bytes <= 0 or type(max_pages) is not int or max_pages <= 0
                or not isinstance(raw, bytes) or not raw or len(raw) > max_bytes
                or not raw.startswith(b'%PDF-')):
            raise PDFError('The PDF document is corrupt, empty or exceeds the supported byte limit.')
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(raw), strict=True)
            if reader.is_encrypted:
                raise PDFError('Encrypted PDF documents are unsupported.')
            import pypdfium2
            with _PDFIUM_LOCK:
                self._pdf = pypdfium2.PdfDocument(raw)
                self._count = len(self._pdf)
            if not 1 <= self._count <= max_pages:
                raise PDFError(f'Use PDF documents containing 1-{max_pages} pages.')
        except PDFError:
            self.close()
            raise
        except ImportError:
            self.close()
            raise PDFError('The local PDF tools are unavailable. Install the pinned local dependencies.') from None
        except Exception:
            self.close()
            raise PDFError('The PDF document is corrupt or unsupported.') from None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __len__(self):
        if self._pdf is None:
            raise PDFError('The PDF document has been closed.')
        return self._count

    def __getitem__(self, index):
        if self._pdf is None or type(index) is not int or not 0 <= index < self._count:
            raise PDFError('The requested PDF page is unavailable.')
        return PDFPage(self, index)

    def __iter__(self):
        for index in range(len(self)):
            yield self[index]

    def close(self):
        with _PDFIUM_LOCK:
            if self._pdf is not None:
                self._pdf.close()
                self._pdf = None


class PDFPage:
    def __init__(self, document, index):
        self.document, self.index = document, index

    @contextmanager
    def _page(self):
        with _PDFIUM_LOCK:
            if self.document._pdf is None:
                raise PDFError('The PDF document has been closed.')
            page = None
            try:
                page = self.document._pdf.get_page(self.index)
                yield page
            except PDFError:
                raise
            except Exception:
                raise PDFError('The PDF page could not be processed locally.') from None
            finally:
                if page is not None:
                    page.close()

    @staticmethod
    def _size(page):
        width, height = page.get_size()
        if (not math.isfinite(width) or not math.isfinite(height) or width <= 0 or height <= 0
                or width * height > MAX_PAGE_AREA):
            raise PDFError('A PDF page has unsupported page dimensions.')
        return width, height

    @property
    def size(self):
        with self._page() as page:
            return self._size(page)

    def extract_text(self, *, max_chars=MAX_TEXT_CHARS):
        if type(max_chars) is not int or max_chars < 0:
            raise PDFError('The PDF text bound is invalid.')
        with self._page() as page:
            self._size(page)
            text_page = page.get_textpage()
            try:
                count = text_page.count_chars()
                if count > max_chars:
                    raise PDFError('A PDF page exceeds the supported extracted-text limit.')
                text = text_page.get_text_range(0, count) if count else ''
                if len(text) > max_chars:
                    raise PDFError('A PDF page exceeds the supported extracted-text limit.')
                return text.replace('\r\n', '\n').replace('\r', '\n')
            finally:
                text_page.close()

    def render_png(self, *, max_edge=1280, max_scale=2.0):
        if (type(max_edge) is not int or not 1 <= max_edge <= 6000
                or type(max_scale) not in (int, float) or not math.isfinite(max_scale) or not 0 < max_scale <= 4):
            raise PDFError('The PDF raster bound is invalid.')
        with self._page() as page:
            width, height = self._size(page)
            scale = min(float(max_scale), max_edge / max(width, height))
            if math.ceil(width * scale) * math.ceil(height * scale) > MAX_RASTER_PIXELS:
                raise PDFError('The PDF raster exceeds the supported pixel limit.')
            # No forms environment or JavaScript engine is initialized. A PDF's
            # embedded actions/links never become application instructions.
            bitmap = page.render(scale=scale, may_draw_forms=False)
            image = None
            try:
                image = bitmap.to_pil()
                output = BytesIO()
                image.save(output, format='PNG')
                return output.getvalue()
            finally:
                if image is not None:
                    image.close()
                bitmap.close()


def open_pdf(raw, *, max_bytes=MAX_BYTES, max_pages=MAX_PAGES):
    return PDFDocument(raw, max_bytes=max_bytes, max_pages=max_pages)


def canonical_ocr_report(raw):
    """Retain bounded local transcriptions as unverified evidence, never decisions."""
    allowed = {'status', 'provenance', 'ocr_lines', 'errors', 'prompt_text_truncated'}
    if not isinstance(raw, dict) or set(raw) - allowed:
        raise PDFError('The local OCR evidence report is malformed.')
    if raw.get('status') not in {'complete', 'unavailable', 'failed'}:
        raise PDFError('The local OCR status is invalid.')
    provenance = raw.get('provenance')
    if (not isinstance(provenance, dict) or set(provenance) != {'engine', 'version', 'verification_status'}
            or provenance['engine'] not in {'rapidocr-onnxruntime', 'provided_adapter'}
            or provenance['verification_status'] != 'unverified_source_text'
            or provenance['version'] is not None and (not isinstance(provenance['version'], str)
                or not re.fullmatch(r'[A-Za-z0-9_.+-]{1,80}', provenance['version']))):
        raise PDFError('The local OCR provenance is invalid.')
    lines, errors = raw.get('ocr_lines'), raw.get('errors')
    if not isinstance(lines, list) or len(lines) > 64 or not isinstance(errors, list) or len(errors) > 8:
        raise PDFError('The local OCR evidence exceeds its supported bounds.')
    retained = []
    for line in lines:
        if (not isinstance(line, dict) or set(line) != {'text', 'confidence', 'box'}
                or not isinstance(line['text'], str) or not line['text'].strip() or len(line['text']) > 200
                or type(line['confidence']) not in (int, float) or not math.isfinite(line['confidence'])
                or not 0 <= line['confidence'] <= 1 or not isinstance(line['box'], list) or len(line['box']) > 4):
            raise PDFError('The local OCR reading is invalid.')
        for point in line['box']:
            if (not isinstance(point, list) or len(point) != 2
                    or any(type(n) not in (int, float) or not math.isfinite(n) or abs(n) > 1_000_000 for n in point)):
                raise PDFError('The local OCR reading location is invalid.')
        retained.append({'text': line['text'], 'confidence': line['confidence'], 'box': line['box']})
    for error in errors:
        if (not isinstance(error, dict) or set(error) != {'tool', 'code'} or error['tool'] != 'ocr'
                or error['code'] not in {'unavailable', 'processing_failed'}):
            raise PDFError('The local OCR failure report is invalid.')
    if (raw['status'] == 'complete' and errors
            or raw['status'] != 'complete' and (retained or not errors)
            or raw['status'] == 'unavailable' and any(item['code'] != 'unavailable' for item in errors)
            or raw['status'] == 'failed' and any(item['code'] != 'processing_failed' for item in errors)):
        raise PDFError('The local OCR status conflicts with its evidence or failures.')
    truncated = raw.get('prompt_text_truncated', False)
    if type(truncated) is not bool:
        raise PDFError('The local OCR truncation status is invalid.')
    result = {'status': raw['status'], 'provenance': dict(provenance), 'ocr_lines': retained,
              'errors': [dict(item) for item in errors], 'prompt_text_truncated': truncated}
    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
    if len(encoded) > 32_000 or len(encoded.encode('utf-8')) > 96 * 1024:
        raise PDFError('The local OCR evidence exceeds its supported bounds.')
    return result
