"""Conservative source tracing inside the existing survey drawing workflow.

Pixel contours are editable source traces, never reconstructed engineering geometry.
The complete source image remains beside the cleaned preview, with immutable source
references. Transcriptions are proposals and never establish scale or approval.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import textwrap
from pathlib import Path

from PIL import Image, ImageOps

from .survey_evidence import (_record_bytes, _image, _open_pdf, _check_workbook_zip,
                              _check_workbook_bounds, EvidenceError)
from .survey_drawings import (_digest, _frame, _label, _text, validate_geometry,
                              refresh_drawing_register, MAX_SHEETS, MAX_ENTITIES)

MAX_TRACE_POINTS = 18000
MAX_TRACE_ENTITIES = 3000
MAX_ASSET_BYTES = 96 * 1024 * 1024


def _pages(record, raw):
    """Read complete images, not the 1280px inference thumbnail; retain all pages."""
    if Path(record.get('filename', '')).suffix.lower() == '.pdf':
        with _open_pdf(raw) as document:
            for index, page in enumerate(document, 1):
                try:
                    image = Image.open(io.BytesIO(page.render_png(max_edge=3000,max_scale=2))).convert('RGB')
                except ValueError as exc:
                    raise EvidenceError(str(exc)) from exc
                yield f"document:{record['id']}:page:{index}", f'page {index}', image
    elif Path(record.get('filename', '')).suffix.lower() == '.xlsx':
        from openpyxl import load_workbook
        _check_workbook_zip(raw)
        book = load_workbook(io.BytesIO(raw), data_only=False, keep_links=False)
        try:
            _check_workbook_bounds(book)
            for sheet in book.worksheets:
                prefix = f"document:{record['id']}:sheet:{sheet.title}"
                if not sheet._images:
                    yield prefix, f'worksheet {sheet.title}', None
                for index, embedded in enumerate(sheet._images, 1):
                    image_raw = embedded._data()
                    _image(image_raw)
                    anchor = getattr(embedded.anchor, '_from', None)
                    reference = f'worksheet {sheet.title}, embedded image {index}'
                    if anchor is not None:
                        reference += f', row {anchor.row+1}, column {anchor.col+1}'
                    with Image.open(io.BytesIO(image_raw)) as original:
                        yield f'{prefix}:image:{index}', reference, ImageOps.exif_transpose(original).convert('RGB')
        finally:
            book.close()
    else:
        _image(raw)  # Existing decoding/pixel bounds before full-resolution decoding.
        with Image.open(io.BytesIO(raw)) as original:
            yield f"document:{record['id']}", 'original', ImageOps.exif_transpose(original).convert('RGB')


def _asset(geometry, image, token, role):
    output = io.BytesIO(); image.save(output, 'PNG')
    raw = output.getvalue()
    assets = geometry.setdefault('_sketch_assets', {})
    if sum(len(value) for value in assets.values()) * 3 // 4 + len(raw) > MAX_ASSET_BYTES:
        raise EvidenceError('Sketch drawing assets exceed the supported size; split the drawing submission.')
    path = f'assets/sketch-{token}-{role}.png'
    assets[path] = base64.b64encode(raw).decode('ascii')
    return path


def _placed_image(path, image, area, source, role):
    x, y, width, height = area
    ratio = min(width / image.width, height / image.height)
    w, h = image.width * ratio, image.height * ratio
    return {'kind': 'image', 'x': x + (width-w)/2, 'y': y + (height-h)/2,
            'width': w, 'height': h, 'path': path, 'pixel_width': image.width,
            'pixel_height': image.height, 'layer': 'SKETCH_REFERENCE',
            'sources': [source], 'sketch_role': role}


def _trace(image, area, source):
    """Bounded pixel-outline tracing. No straightening, snapping, scaling or fill-in."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return [], 'Editable tracing unavailable; full source and cleaned raster retained.'
    reduced = ImageOps.grayscale(image)
    reduced.thumbnail((1800, 1800))
    # Threshold affects the editable outline only. It never replaces the complete
    # grayscale cleaned preview or colour reference (faint strokes may be missed).
    pixels = np.asarray(reduced)
    _, mask = cv2.threshold(pixels, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    x, y, width, height = area
    ratio = min(width/image.width, height/image.height)
    w, h = image.width*ratio, image.height*ratio
    x += (width-w)/2; y += (height-h)/2
    output = []; points_used = 0; overflow = False
    for contour in contours:
        points = contour.reshape(-1, 2)
        if len(points) < 2:
            continue
        if len(output) >= MAX_TRACE_ENTITIES or points_used + len(points) > MAX_TRACE_POINTS:
            overflow = True; continue
        points_used += len(points)
        output.append({'kind': 'polyline', 'closed': True, 'layer': 'SKETCH_TRACE',
            'points': [[round(x + float(px)/reduced.width*w, 4),
                        round(y + h - float(py)/reduced.height*h, 4)] for px, py in points],
            'sources': [source]})
    return output, ('Trace limit reached: some editable contours omitted; full source raster retained.' if overflow else
                    'Pixel-outline trace only; faint strokes/colours may be absent. Compare full reference.')


def _ledger(analysis):
    notes = []; dimensions = []
    for finding in analysis.get('findings', []):
        if not isinstance(finding, dict) or finding.get('category') != 'measurement':
            continue
        label = _text(finding.get('component') or finding.get('field_hint') or 'Dimension', 160)
        quote = _text(finding.get('evidence_quote'), 800)
        if (finding.get('value') is not None and finding.get('basis') == 'recorded'
                and finding.get('unit') and quote and finding.get('recorded_measurement') is True):
            origin = (' | ' + _text(finding['source_id'], 200)) if finding.get('source_id') else ''
            dimensions.append(f"{label}: {_text(finding['value'], 160)} {_text(finding['unit'], 32)} | source says: {quote}{origin} | unverified")
        else:
            notes.append(f'{label}: missing/unreadable/unsupported dimension; obtain site measurement.')
    notes.extend(_text(note, 1000) for note in analysis.get('missing', []) if isinstance(note, str))
    notes.extend('CONFLICT: ' + _text(note, 1000) for note in analysis.get('conflicts', []) if isinstance(note, str))
    if not dimensions:
        notes.insert(0, 'No source-backed readable dimensions available. All required site measurements need review.')
    notes.append('Check every required dimension against the source; absent labels cannot establish a measured span.')
    return dimensions, notes


def add_hand_sketches(geometry, records, analyses):
    """Append source-tracing sheets using trusted original records and saved analyses.

    Caller supplies authenticated immutable snapshot paths and current revision
    analyses, never browser paths. No inference, answer writes or approval occurs.
    Bounds fail explicitly rather than silently omitting original pages or notes.
    """
    result = copy.deepcopy(geometry)
    initial_sheet_count = len(result['sheets'])
    if len(records) > 80:
        raise EvidenceError('Too many hand sketches; split the drawing submission.')
    for record in records:
        if record.get('kind') != 'hand_sketch':
            continue
        raw = _record_bytes(record)
        for source_id, reference, image in _pages(record, raw):
            sheet_prefix = source_id.rsplit(':image:', 1)[0] if ':image:' in source_id else source_id
            matching = [(key, value) for key, value in analyses.items()
                        if key == source_id or key.startswith(source_id + ':part:')
                        or (':sheet:' in source_id and key.startswith(sheet_prefix + ':part:'))]
            analysis = {'findings': [], 'missing': [], 'conflicts': []}
            for key, saved in matching:
                if not isinstance(saved, dict) or saved.get('sha256') != record['sha256']:
                    raise EvidenceError('A sketch analysis does not match its original evidence hash.')
                for field in analysis:
                    entries = saved.get(field, [])
                    analysis[field].extend(({**entry, 'source_id': key} if isinstance(entry, dict) else entry)
                                          for entry in entries)
            source = {'source_id': source_id, 'type': 'hand_sketch', 'id': record['id'],
                      'reference': reference, 'filename': record.get('filename', ''),
                      'sha256': record['sha256']}
            source['analysis_source_ids'] = [key for key, _ in matching]
            dimensions, notes = _ledger(analysis)
            token = hashlib.sha256(source_id.encode()).hexdigest()[:16]
            clean = ImageOps.autocontrast(ImageOps.grayscale(image)).convert('RGB') if image is not None else None
            sheet = {'key': f'hand_sketch_{token}', 'number': f'SK-{len(result["sheets"])+1:03d}',
                     'title': 'Hand sketch - clean source tracing', 'scale': 'Not to Scale',
                     'source': source, 'findings': [], 'entities': []}
            entities = _frame(sheet, result['site_id'])
            entities.append(_label('Draft For Review | Not to Scale | source tracing, not measured engineering reconstruction', 14, 262, 2.5, 'WARNINGS'))
            if image is not None:
                entities.extend([_label('Cleaned source preview (complete image)', 14, 253, 2.5, 'TITLE'),
                    _label('Complete colour source reference', 216, 253, 2.5, 'TITLE')])
                for role, view, area in [('clean', clean, (14, 139, 188, 107)), ('reference', image, (216, 139, 188, 107))]:
                    path = _asset(result, view, token, role)
                    entities.append(_placed_image(path, view, area, source, role))
                traces, trace_note = _trace(image, (14, 139, 188, 107), source)
            else:
                traces = []
                trace_note = 'No supported embedded image: worksheet cells retained; inspect the original workbook for drawing shapes.'
                source['renderability'] = 'no_supported_embedded_image'
                notes.insert(0, trace_note)
                entities.append(_label(trace_note, 14, 243, 2.5, 'WARNINGS'))
                result['warnings'].append(f'{source_id}: {trace_note}')
            # Both exporters consume the same editable contours. The complete
            # cleaned raster beneath them retains strokes missed by thresholding.
            entities.extend(traces)
            entities.extend([_label(trace_note, 14, 133, 2.1, 'WARNINGS'),
                _label(f"Source: {source_id} | {reference} | {_text(record.get('filename'), 170)}", 14, 128, 2.1),
                _label(f"Original SHA256: {record['sha256']}", 14, 123, 2.1)])
            rows = [(line, 'DIMENSIONS') for item in dimensions for line in textwrap.wrap(item, 150)]
            rows += [(line, 'WARNINGS') for item in notes for line in textwrap.wrap('DIMENSIONS NEED REVIEW: ' + item, 150)]
            # Eight lines on the image sheet; overflow receives additional sheets.
            chunks = [rows[:8]] + [rows[i:i+28] for i in range(8, len(rows), 28)]
            for index, chunk in enumerate(chunks):
                if index:
                    sheet = {**sheet, 'key': f'hand_sketch_{token}_notes_{index}',
                             'number': f'SK-{len(result["sheets"])+1:03d}',
                             'title': 'Hand sketch - dimension review continued', 'entities': []}
                    entities = _frame(sheet, result['site_id'])
                    entities.append(_label(f'Draft For Review | Not to Scale | Source {source_id}', 14, 261, 2.5, 'WARNINGS'))
                top = 116 if not index else 251
                entities.extend(_label(text, 14, top-i*5, 2.5, layer, [source]) for i, (text, layer) in enumerate(chunk))
                sheet['entities'] = entities
                result['sheets'].append(sheet)
            result['sources'].append(source)
            result['warnings'].append(f'{source_id}: Not to Scale; source tracing requires human dimension and detail review.')
            if len(result['sheets']) > MAX_SHEETS or sum(len(s['entities']) for s in result['sheets']) > MAX_ENTITIES:
                raise EvidenceError('Sketch sheets or contours exceed drawing limits; split the submission. No source pages were silently omitted.')
    if len(result['sheets']) != initial_sheet_count:
        refresh_drawing_register(result)
        if sum(len(s['entities']) for s in result['sheets']) > MAX_ENTITIES:
            raise EvidenceError('Drawing register exceeds the supported entity limit; split the submission.')
    result.pop('digest', None)
    result['digest'] = _digest(result)
    validate_geometry(result)
    return result
