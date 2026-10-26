"""Evidence-bound survey drawing records and deterministic PDF/DXF presentation.

These are survey records, not structural/electrical designs or compliance certificates.
Unverified photo interpretation is never converted to a measured position or connection.
All coordinates in the final geometry.json are A3 paper millimetres, origin bottom-left;
the PDF and DXF renderers consume the same ordered entities, including the title block.
The caller owns permission checks, approved-project branding and human release gates.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import shutil
import textwrap
import unicodedata
import uuid
import zipfile
from datetime import date
from functools import lru_cache
from html import escape
from pathlib import Path

from PIL import Image
from reportlab.pdfbase.pdfmetrics import stringWidth

VERSION = 'survey-drawings-2'
PAGE = (420.0, 297.0)
MAX_SHEETS = 32
MAX_RECORDS = 1000
MAX_ENTITIES = 20000
ROWS_PER_SHEET = 16
LAYERS = {
    'BORDER': (8, 25), 'TITLE': (7, 35), 'TEXT': (7, 18),
    'EQUIPMENT': (7, 35), 'MEASURED': (5, 25), 'DIMENSIONS': (7, 18),
    'WARNINGS': (1, 25), 'LOGOS': (7, 18), 'ROUTES': (3, 25),
    'SKETCH_TRACE': (8, 8), 'SKETCH_REFERENCE': (7, 18),
}
SHEETS = (
    ('site_layout', 'Site layout', '002'),
    ('shelter_layout', 'Shelter, equipment and cable routes', '003'),
    ('tower_elevation', 'Tower elevation, sections and platforms', '004'),
    ('antenna_arrangement', 'Antenna levels and sectors', '005'),
    ('equipment_schedule', 'Equipment schedule and mounting records', '006'),
    ('mounting_connections', 'Enlarged mounting connections', '007'),
    ('power_sld', 'Power single-line records', '008'),
    ('rectifier_mdb', 'Rectifier and MDB distribution', '009'),
    ('roxtec_hatchplate', 'Roxtec and hatchplate arrangements', '010'),
    ('grounding', 'Grounding arrangement', '011'),
)
SHEET_KEYS = {key for key, _, _ in SHEETS}
UNITS = {'mm': 1.0, 'cm': 10.0, 'm': 1000.0}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _text(value, limit=500):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = unicodedata.normalize('NFC', str('' if value is None else value))
    text = re.sub(r'\s+', ' ', text)
    # Keep real scripts (including Arabic joining characters), but not hidden
    # direction overrides, NULs or invalid surrogate code points in CAD/PDF text.
    text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C'
                   or char in ('\u200c', '\u200d'))
    return text.strip()[:limit]


@lru_cache(maxsize=1)
def _unicode_metrics_font():
    import pymupdf
    return pymupdf.Font('helv')


def _text_width(text, height):
    if text.isascii():
        return stringWidth(text, 'Helvetica', height)
    # PyMuPDF's Unicode fallback metrics cover the scripts that Helvetica lacks.
    # The PDF renderer below also uses its bundled fonts, without OS font paths.
    return _unicode_metrics_font().text_length(text, fontsize=height)


def _num(value):
    number = float(value)
    if not math.isfinite(number) or abs(number) > 1e9:
        raise ValueError('Coordinates must be finite and bounded.')
    return number


def _sources(record):
    source = record.get('sources', record.get('source_refs', []))
    if isinstance(source, dict):
        source = [source]
    if not source and record.get('source_id') is not None:
        source = [{'id': record['source_id'], 'source_id': record['source_id'], 'type': record.get('source_type', 'evidence'), 'reference': record.get('reference', ''), 'page': record.get('page'), 'crop': record.get('crop')}]
    return copy.deepcopy(source if isinstance(source, list) else [])


def _source_label(sources):
    labels = []
    for source in sources[:5]:
        if not isinstance(source, dict):
            labels.append(_text(source, 28))
            continue
        label = _text(source.get('label') or source.get('name') or f"{source.get('type', source.get('kind', 'evidence'))} {source.get('id', source.get('source_id', source.get('photo_id', source.get('document_id', '?'))))}", 54)
        if source.get('reference'):
            label += ' | '+_text(source['reference'],70)
        if source.get('page') is not None:
            label += f" p{source['page']}"
        if source.get('crop'):
            label += ' crop'
        labels.append(label)
    if len(sources) > 5:
        labels.append(f'+{len(sources)-5} sources; see geometry.json')
    return '; '.join(labels) or 'No source - needs verification'


def _category(record):
    explicit = record.get('sheet') or record.get('drawing_sheet')
    if explicit in SHEET_KEYS:
        return explicit
    if record.get('category') in ('site','coordinate'):
        return 'site_layout'
    text = ' '.join(_text(record.get(k, ''), 200).lower().replace('_', ' ') for k in ('field', 'field_hint', 'component', 'key', 'label', 'category', 'equipment_type'))
    for keywords, key in (
        (('roxtec', 'hatchplate', 'cable entry'), 'roxtec_hatchplate'),
        (('grounding', 'earthing', 'earth bar'), 'grounding'),
        (('rectifier', 'mdb', 'distribution board'), 'rectifier_mdb'),
        (('single line', 'single-line', 'electrical connection', 'power supply'), 'power_sld'),
        (('mounting connection', 'bolt', 'bracket connection'), 'mounting_connections'),
        (('antenna', 'azimuth', 'sector', 'tilt'), 'antenna_arrangement'),
        (('tower', 'platform', 'installation level'), 'tower_elevation'),
        (('shelter', 'cable route'), 'shelter_layout'),
        (('coordinate', 'site layout', 'site boundary', 'site id', 'site identification'), 'site_layout'),
    ):
        if any(keyword in text for keyword in keywords):
            return key
    return 'equipment_schedule'


def _line(x1, y1, x2, y2, layer='BORDER', sources=None):
    return {'kind': 'line', 'points': [[round(x1, 4), round(y1, 4)], [round(x2, 4), round(y2, 4)]], 'layer': layer, 'sources': sources or []}


def _label(text, x, y, height=2.5, layer='TEXT', sources=None, max_width=390):
    # Physical text size never falls below 2.1 mm; long text wraps rather than shrinks.
    text = _text(text)
    while text and _text_width(text, height) > max_width:
        text = text[:-4].rstrip() + '...'
    return {'kind': 'text', 'text': text, 'x': round(x, 4), 'y': round(y, 4),
            'height': height, 'max_width': max_width, 'layer': layer, 'sources': sources or []}


def _box(x, y, width, height, layer='BORDER', sources=None):
    return {'kind': 'polyline', 'points': [[x,y],[x+width,y],[x+width,y+height],[x,y+height]], 'closed': True, 'layer': layer, 'sources': sources or []}


def _frame(sheet, site_id):
    return [
        _box(8, 8, 404, 281),
        _label('iSurvix | Survey evidence drawings', 14, 281, 3.4, 'TITLE'),
        _label(f"{site_id} / {sheet['title']}", 14, 273, 4, 'TITLE', max_width=384),
        _line(14, 268, 406, 268),
        _label('Evidence record only. No structural capacity, electrical safety or code compliance assessment.', 14, 65, 2.25, 'WARNINGS'),
        _label('Unknown dimensions and concealed connections have not been inferred. Review sources before use.', 14, 59.5, 2.25, 'WARNINGS'),
        _label('NORTH: not established unless recorded in the source.', 14, 48, 2.2),
        _label('Use the stated scale only. Do not scale evidence schedules.', 14, 42, 2.2),
    ]


def _table(rows, *, x=14, y=251, width=392, row_height=10.6, columns=(105, 180, 107)):
    out = [_box(x, y+3, width, 8)]
    starts = [x, x+columns[0], x+columns[0]+columns[1], x+width]
    for col, (title, column) in enumerate(zip(('Recorded item', 'Finding / verification status', 'Source evidence'), starts)):
        out.append(_label(title, column+2, y+5.3, 2.5, 'TITLE', max_width=columns[col]-4))
    for index, row in enumerate(rows):
        top = y+3-index*row_height
        bottom = top-row_height
        out.append(_line(x, bottom, x+width, bottom))
        for edge in starts:
            out.append(_line(edge, top, edge, bottom))
        for col, value in enumerate(row[:3]):
            wrap_chars = max(15, int((columns[col]-5)/1.17))
            lines = textwrap.wrap(_text(value, 400), width=wrap_chars, break_long_words=True)[:3]
            for offset, line in enumerate(lines):
                out.append(_label(line, starts[col]+2, top-3.1-offset*2.6, 2.1, max_width=columns[col]-4))
    return out


def _validated_records(records, warnings):
    good = []
    for index, original in enumerate(records):
        if not isinstance(original, dict):
            warnings.append(f'Drawing record {index+1}: unsupported record type.')
            continue
        rec = copy.deepcopy(original)
        sources = _sources(rec)
        status = str(rec.get('verification_status', rec.get('status', ''))).lower()
        if status not in ('confirmed', 'verified') or not sources or rec.get('measurement_basis') not in ('recorded', 'site_measured', 'manufacturer_verified'):
            warnings.append(f"{_text(rec.get('tag') or f'Drawing record {index+1}', 70)}: measured geometry withheld; needs sourced, confirmed measurements.")
            continue
        if rec.get('kind') == 'connection' and rec.get('observed') is not True:
            warnings.append(f"{_text(rec.get('tag') or 'Connection', 70)}: connection withheld; visible or recorded connectivity not confirmed.")
            continue
        factor = UNITS.get(str(rec.get('unit', '')).lower())
        if factor is None:
            warnings.append(f"Drawing record {index+1}: explicit supported measurement unit required.")
            continue
        try:
            kind = rec.get('kind')
            if kind == 'equipment':
                x, y = _num(rec['x'])*factor, _num(rec['y'])*factor
                width, height = _num(rec['width'])*factor, _num(rec['height'])*factor
                if width <= 0 or height <= 0:
                    raise ValueError('Positive envelope dimensions required.')
                rec['mm_points'] = [[x,y], [x+width,y+height]]
                rec['mm_width'], rec['mm_height'] = width, height
            elif kind in ('line', 'boundary', 'connection', 'dimension'):
                points = rec['points']
                if not isinstance(points, list) or not 2 <= len(points) <= 128:
                    raise ValueError('Two to 128 points required.')
                rec['mm_points'] = [[_num(p[0])*factor, _num(p[1])*factor] for p in points]
                if kind == 'dimension':
                    if len(points) != 2 or not rec.get('value'):
                        raise ValueError('Explicit recorded dimension value required.')
                    length = math.dist(rec['mm_points'][0], rec['mm_points'][1])
                    value = _num(rec['value'])*factor
                    if value <= 0 or abs(length-value) > max(1., value*.01):
                        warnings.append(f"{_text(rec.get('tag') or 'Dimension')}: conflicting coordinate and recorded measurement; geometry withheld.")
                        continue
            else:
                raise ValueError('Unsupported geometry kind.')
            rec['sources'] = sources
            rec['sheet'] = _category(rec)
            good.append(rec)
        except (KeyError, TypeError, ValueError, IndexError, OverflowError):
            warnings.append(f"Drawing record {index+1}: incomplete or invalid measured geometry withheld.")
    return good


def _measured_entities(records, blocks):
    """Place ONLY explicit recorded coordinates; generic envelopes remain labelled typical."""
    points = [p for rec in records for p in rec['mm_points']]
    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    span_x, span_y = max(max_x-min_x, 1), max(max_y-min_y, 1)
    needed = max(span_x/168, span_y/135, 1)
    denominator = next((s for s in (1,2,5,10,20,25,50,100,200,250,500,1000,2000,5000,10000,20000,50000,100000) if s >= needed), math.ceil(needed/100000)*100000)
    def transform(p):
        return [24+(p[0]-min_x)/denominator, 98+(p[1]-min_y)/denominator]
    out = []
    for rec in records:
        converted = [transform(p) for p in rec['mm_points']]
        sources = rec['sources']
        if rec['kind'] == 'equipment':
            x,y = converted[0]
            width,height = rec['mm_width']/denominator,rec['mm_height']/denominator
            key = _text(rec.get('equipment_type')).lower()
            block = blocks.get(key)
            if block and (key!='dish' or abs(width-height)<=.01):
                # Both exporters share the SAME normalized reusable block definition.
                # DXF keeps a native INSERT, allowing practical CAD block editing.
                out.append({'kind':'block','x':x,'y':y,'width':width,'height':height,
                    'layer':'EQUIPMENT','sources':sources,'block_version':blocks['_version'],
                    'block_key':key,'definition':copy.deepcopy(block)})
            else:
                out.append(_box(x,y,width,height,'EQUIPMENT',sources))
            # Tags are leadered into a numbered schedule, avoiding crowded geometry labels.
            tag = _text(rec.get('tag', 'Recorded envelope'), 35)
            out.append(_label(tag, x, max(88,y-4), 2.1, sources=sources, max_width=65))
        elif rec['kind'] == 'dimension':
            a,b=converted
            out.append(_line(*a,*b,'DIMENSIONS',sources))
            for point in (a,b):
                out.append(_line(point[0]-1.2,point[1]-1.2,point[0]+1.2,point[1]+1.2,'DIMENSIONS',sources))
            out.append(_label(f"{rec['value']} {rec['unit']} (recorded)", (a[0]+b[0])/2, (a[1]+b[1])/2+3, 2.1, sources=sources,max_width=85))
        else:
            out.append({'kind':'polyline','points':converted,'closed':rec['kind']=='boundary','layer':'ROUTES' if rec['kind']=='connection' else 'MEASURED','sources':sources})
    out.append(_label(f'Measured record diagram - scale 1:{denominator} at A3', 20, 256, 2.4,'TITLE',max_width=182))
    out.append(_label('Generic envelopes: Typical - verify against site.',20,80,2.1,'WARNINGS',max_width=185))
    # Real scale bar in paper mm (labels are model mm, never guessed site distances).
    distance_label = f'{50*denominator:g} mm'
    out.extend([_line(24,88,74,88,'DIMENSIONS'), _line(24,86,24,90,'DIMENSIONS'), _line(74,86,74,90,'DIMENSIONS'),
        _label('0',24,82.5,2.1,'DIMENSIONS',max_width=20),
        _label(distance_label,74-stringWidth(distance_label,'Helvetica',2.1),82.5,2.1,'DIMENSIONS',max_width=80)])
    return out, f'1:{denominator} at A3'


def build_geometry(snapshot: dict, findings: list) -> dict:
    """Build bounded evidence schedules and, only when verified, measured diagrams.

    ``snapshot['drawing_records']`` is an optional list of human-confirmed coordinates;
    see _validated_records. Freeform AI ``findings`` can support a schedule, not exact
    engineering geometry. Source IDs/pages/crops are retained without interpretation.
    """
    if not isinstance(snapshot, dict) or not isinstance(findings, list):
        raise ValueError('A survey snapshot and structured findings list are required.')
    raw_records = snapshot.get('drawing_records', [])
    if not isinstance(raw_records, list) or len(raw_records) > MAX_RECORDS or len(findings) > 5000:
        raise ValueError('Drawing input exceeds the supported bounded record count.')
    block_data = json.loads(Path(__file__).with_name('drawing_blocks_v1.json').read_text(encoding='utf-8'))
    blocks = block_data['blocks'];blocks['_version'] = block_data['version']
    warnings = []
    records = _validated_records(raw_records, warnings)
    project = snapshot.get('project', {})
    if isinstance(project, dict):
        project_id, project_name = project.get('id', snapshot.get('project_id', '')), project.get('name', '')
    else:
        project_id, project_name = snapshot.get('project_id', ''), _text(project)
    site = snapshot.get('site', {})
    site_id = snapshot.get('site_id') or (site.get('id') if isinstance(site, dict) else site)
    geometry = {'version':VERSION,'blocks_version':block_data['version'],'page_mm':list(PAGE),'project_id':project_id,'project':_text(project_name or snapshot.get('project_name','Project not supplied'),120),'site_id':_text(site_id,80) or 'Site not supplied','survey_id':snapshot.get('survey_id',snapshot.get('id')),'date':_text(snapshot.get('date') or snapshot.get('submitted_at') or date.today().isoformat(),10),'warnings':warnings,'missing_information':[],'sheets':[],'sources':[],'record_type':'Survey evidence drawings; no engineering certification'}
    groups = {key:[] for key in SHEET_KEYS}
    seen = {}
    for finding in findings:
        if not isinstance(finding, dict):
            warnings.append('Unsupported finding omitted from drawing presentation; retained by processing record.')
            continue
        key = _category(finding)
        label = _text(finding.get('label') or finding.get('field') or finding.get('component') or finding.get('field_hint') or finding.get('key') or finding.get('category') or 'Evidence finding',95)
        value = finding.get('value', finding.get('answer', finding.get('description', 'Not recorded')))
        status = _text(finding.get('status') or finding.get('verification_status') or 'Needs review',35)
        sources = _sources(finding)
        unit = _text(finding.get('unit'),15)
        missing_value = value in (None, '', [], {})
        answer = f"{'Not recorded' if missing_value else _text(value,230)}{(' '+unit) if unit and not missing_value else ''} | {status}"
        if finding.get('conflict') or finding.get('conflicts'):
            answer += ' | CONFLICT - resolve before release'
            warnings.append(f'{label}: conflicting evidence; no authoritative value selected.')
        fingerprint = _digest([key,label,answer])
        if fingerprint in seen:
            seen[fingerprint]['sources'].extend(s for s in sources if s not in seen[fingerprint]['sources'])
        else:
            row = {'label':label,'answer':answer,'sources':sources,'confidence':finding.get('confidence'),'verification_status':status}
            groups[key].append(row);seen[fingerprint]=row
        for source in sources:
            if source not in geometry['sources']:
                geometry['sources'].append(source)
    for rec in records:
        for source in rec['sources']:
            if source not in geometry['sources']:
                geometry['sources'].append(source)
        groups[rec['sheet']].append({'label':_text(rec.get('tag') or rec['kind'],95),'answer':f"Confirmed measured record ({rec['unit']}); {_text(rec.get('measurement_basis'))}",'sources':rec['sources']})
    register_rows=[]
    for key,title,number in SHEETS:
        rows=groups[key]
        measured=[rec for rec in records if rec['sheet']==key]
        if not rows:
            missing=f'{title}: no supported records; obtain applicable measurements, equipment details and evidence.'
            geometry['missing_information'].append(missing)
            register_rows.append((f'SV-{number} | {title}','Not generated - supporting information missing','No geometry or connections assumed'))
            continue
        pages=[rows[i:i+ROWS_PER_SHEET] for i in range(0,len(rows),ROWS_PER_SHEET)]
        count=0
        for part,part_rows in enumerate(pages,1):
            if len(geometry['sheets']) >= MAX_SHEETS-3:
                warnings.append(f'{title}: remaining facts exceed drawing page bound; review complete structured processing results.')
                break
            sheet={'key':key,'title':title+(' - '+str(part) if len(pages)>1 else ''),'number':f'SV-{number}'+(f'-{part:02d}' if len(pages)>1 else ''),'scale':'Not to Scale','entities':[],'findings':part_rows,'measured_record_count':len(measured) if part==1 else 0}
            sheet['entities']=_frame(sheet,geometry['site_id'])
            if measured and part==1:
                entities,scale=_measured_entities(measured,blocks)
                sheet['entities'].extend(entities);sheet['scale']=scale
                narrow=[(r['label'],r['answer'],_source_label(r['sources'])) for r in part_rows]
                sheet['entities'].extend(_table(narrow,x=210,width=196,columns=(55,81,60)))
            else:
                sheet['entities'].append(_label('Evidence schedule - no unsupported positions, concealed connections or exact profiles.',14,263,2.5,'WARNINGS'))
                sheet['entities'].extend(_table([(r['label'],r['answer'],_source_label(r['sources'])) for r in part_rows]))
            geometry['sheets'].append(sheet);count+=1
        register_rows.append((f'SV-{number} | {title}',f'{count} sheet(s) | '+('Measured records + verification schedule' if measured else 'Evidence schedule only / Not to Scale'),f'{len(rows)} recorded findings; sources linked in geometry.json'))
    register={'key':'register','title':'Drawing register and verification notes','number':'SV-001','scale':'Not to Scale','entities':[],'findings':[]}
    register['entities']=_frame(register,geometry['site_id'])
    register['entities'].append(_label('Survey documentation. Each drawing is evidence-bound and requires authorised technical review.',14,263,2.5,'WARNINGS'))
    register['entities'].extend(_table(register_rows,row_height=12.8))
    notes=[('Design basis','No structural/electrical design performed. No governing design code or load combinations claimed.','A design basis and separate calculations are needed for engineering design.'),('Survey origin',f"Survey {geometry['survey_id']} | {geometry['date']}",f"{len(geometry['sources'])} linked evidence references"),('Drawing symbols',block_data['version'],'Generic measured envelopes; Typical - verify against site.'),('Verification',f"{len(geometry['missing_information'])} missing sheet categories; {len(warnings)} warnings",'Review missing information and conflicts before release.')]
    register['entities'].extend(_table(notes,y=104,row_height=8,columns=(105,180,107)))
    geometry['sheets'].insert(0,register)
    if warnings:
        warning_sheet={'key':'verification','title':'Conflicts and drawing verification requests','number':'SV-012','scale':'Not to Scale','entities':[],'findings':[]}
        warning_sheet['entities']=_frame(warning_sheet,geometry['site_id'])
        warning_sheet['entities'].extend(_table([(f'Request {i+1}',w,'See source processing findings') for i,w in enumerate(warnings[:ROWS_PER_SHEET])]))
        geometry['sheets'].append(warning_sheet)
    if sum(len(sheet['entities']) for sheet in geometry['sheets']) > MAX_ENTITIES:
        raise ValueError('Drawing entity bound exceeded.')
    geometry['digest']=_digest(geometry)
    validate_geometry(geometry)
    return geometry


def refresh_drawing_register(geometry):
    """Rebuild the register after adding source sheets, before either exporter.

    Actual drawing numbers lead the register; absent standard categories remain
    explicit. Additional register pages are themselves indexed and bounded.
    """
    drawings=[s for s in geometry['sheets'] if s['key']!='register' and not s['key'].startswith('register_continued_')]
    actual=[(f"{s['number']} | {s['title']}",f"Generated | {s['scale']}",
             _source_label([s['source']]) if s.get('source') else f"{len(s.get('findings',[]))} recorded findings; see geometry.json") for s in drawings]
    missing=[(f'SV-{number} | {title}','Not generated - supporting information missing','No geometry or connections assumed')
             for key,title,number in SHEETS if not any(s['key']==key for s in drawings)]
    count=1
    while True:
        continuation=[(f'SV-001-{i:02d} | Drawing register continued','Register index continuation','See corresponding register page') for i in range(2,count+1)]
        rows=actual+continuation+missing
        needed=max(1,math.ceil(len(rows)/12))
        if needed==count:break
        count=needed
    if len(drawings)+count>MAX_SHEETS:
        raise ValueError('Drawing register continuation exceeds the supported sheet limit; split the submission.')
    notes=[('Design basis','No structural/electrical design performed. No governing design code or load combinations claimed.','A design basis and separate calculations are needed for engineering design.'),
        ('Survey origin',f"Survey {geometry['survey_id']} | {geometry['date']}",f"{len(geometry['sources'])} linked evidence references"),
        ('Drawing symbols',geometry['blocks_version'],'Generic measured envelopes; Typical - verify against site.'),
        ('Verification',f"{len(geometry['missing_information'])} missing sheet categories; {len(geometry['warnings'])} warnings",'Review missing information and conflicts before release.')]
    registers=[]
    for part in range(count):
        sheet={'key':'register' if part==0 else f'register_continued_{part+1}',
               'title':'Drawing register and verification notes' if part==0 else 'Drawing register continued',
               'number':'SV-001' if part==0 else f'SV-001-{part+1:02d}',
               'scale':'Not to Scale','findings':[],'entities':[]}
        sheet['entities']=_frame(sheet,geometry['site_id'])
        sheet['entities'].append(_label('Survey documentation. Each drawing is evidence-bound and requires authorised technical review.',14,263,2.5,'WARNINGS'))
        sheet['entities'].extend(_table(rows[part*12:(part+1)*12],row_height=11))
        sheet['entities'].extend(_table(notes,y=104,row_height=8,columns=(105,180,107)))
        registers.append(sheet)
    geometry['sheets']=registers+drawings


def validate_geometry(geometry):
    """Reject nonfinite, out-of-sheet or unsupported plotted entities before exports."""
    if not 1 <= len(geometry['sheets']) <= MAX_SHEETS:
        raise ValueError('Invalid drawing sheet count.')
    for sheet in geometry['sheets']:
        for entity in sheet['entities']:
            kind=entity.get('kind')
            if entity.get('layer') not in LAYERS:
                raise ValueError('Unsupported drawing layer.')
            if kind in ('line','polyline'):
                points=entity['points']
            elif kind=='circle':
                x,y=entity['center'];r=_num(entity['radius'])
                if r<=0:raise ValueError('Invalid circle radius.')
                points=[[x-r,y-r],[x+r,y+r]]
            elif kind in ('text','image','block'):
                x,y=entity['x'],entity['y']
                if kind=='text':
                    height=_num(entity['height'])
                    if height<2.1:raise ValueError('Unreadably small text.')
                    points=[[x,y],[x+_text_width(entity['text'],height),y+height]]
                else:
                    points=[[x,y],[x+entity['width'],y+entity['height']]]
                    if entity['width']<=0 or entity['height']<=0:raise ValueError('Invalid measured envelope.')
                    if kind=='block':
                        for primitive in entity['definition']['entities']:
                            if primitive['kind'] not in ('line','polyline','circle'):
                                raise ValueError('Unsupported block primitive.')
            else:
                raise ValueError('Unsupported drawing entity kind.')
            for p in points:
                x,y=_num(p[0]),_num(p[1])
                if not 8-0.01<=x<=412+.01 or not 8-.01<=y<=289+.01:
                    raise ValueError('Drawing geometry or labels exceed the A3 border.')


def _titleblock(sheet, geometry, revision, prepared, checked, approved, released, logos):
    x,y,w,h=214,8,198,54
    entities=[_box(x,y,w,h,'TITLE')]
    entities.extend(_line(x,y+level,x+w,y+level) for level in (10,22,34,44))
    entities.extend(_line(x+offset,y,x+offset,y+10) for offset in (66,132))
    entities += [
        _label(f"Project: {geometry['project']}",x+3,y+47,2.4,'TITLE',max_width=114),
        _label(f"Site: {geometry['site_id']}",x+3,y+37,2.6,'TITLE',max_width=139),
        _label(sheet['title'],x+3,y+26,2.6,'TITLE',max_width=190),
        _label(f"{sheet['number']} | Rev {revision:03d} | {geometry['date']} | Sheet {sheet['sheet_no']}/{len(geometry['sheets'])}",x+3,y+17,2.2,max_width=190),
        _label(f"Scale: {sheet['scale']}",x+3,y+12.7,2.1,max_width=190),
        _label(f'Prepared: {_text(prepared,45) or "Not assigned"}',x+2,y+4,2.1,max_width=62),
        _label(f'Checked: {_text(checked,45) or "Pending human review"}',x+68,y+4,2.1,max_width=62),
        _label(f'Approved: {_text(approved,45) or "Not released"}',x+134,y+4,2.1,max_width=62),
        _label(f'Revision {revision:03d} | {geometry["date"]} | '+('Authorised release' if released else 'Initial / updated review issue'),14,32,2.2,max_width=190),
        _label('Previous output revisions remain preserved in the survey history.',14,26,2.2,max_width=190),
        _label('RELEASED - Survey record only' if released else 'DRAFT - FOR REVIEW',14,12,3.4,'TITLE' if released else 'WARNINGS',max_width=193),
    ]
    for logo in logos:
        width,height=logo['paper_width'],logo['paper_height']
        logo_x,logo_y={'company':(337,y+45),'client':(373,y+45),'partner':(373,y+35)}[logo['role']]
        entities.append({'kind':'image','x':logo_x,'y':logo_y,'width':width,'height':height,'path':logo['path'],'pixel_width':logo['pixel_width'],'pixel_height':logo['pixel_height'],'layer':'LOGOS','sources':[{'type':'project_branding','project_id':geometry['project_id'],'role':logo['role']}]})
    return entities


def _prepare_logos(branding, geometry, folder):
    if not branding:
        return []
    if str(branding.get('project_id'))!=str(geometry.get('project_id')) or not geometry.get('project_id'):
        raise ValueError('Branding must be explicitly assigned to the drawing project.')
    logos=[]
    for role in ('company','client','partner'):
        value=branding.get(f'{role}_logo') or branding.get(f'{role}_logo_path')
        if not value:continue
        path=Path(value)
        with Image.open(path) as image:
            if image.width*image.height>40_000_000:raise ValueError('Branding image too large.')
            image.thumbnail((1000,400))
            image=image.convert('RGBA')
            asset=folder/'assets'/f'{role}-logo.png';asset.parent.mkdir(exist_ok=True)
            image.save(asset)
            pixel_width,pixel_height=image.size
        ratio=min(34/pixel_width,8/pixel_height)
        logos.append({'role':role,'path':asset.relative_to(folder).as_posix(),'pixel_width':pixel_width,'pixel_height':pixel_height,'paper_width':round(pixel_width*ratio,3),'paper_height':round(pixel_height*ratio,3)})
    return logos


def _pdf(geometry, target, folder):
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    paper=[value*mm for value in PAGE]
    document=canvas.Canvas(str(target),pagesize=paper,pageCompression=1,invariant=1)
    document.setTitle(f"{geometry['site_id']} survey drawings | revision {geometry['revision']:03d}")
    document.setSubject(f"Shared geometry SHA256 {geometry['digest']}; {'Released survey record' if geometry['released'] else 'Draft - For Review'}")
    document.setAuthor('iSurvix Field')
    for sheet in geometry['sheets']:
        for entity in sheet['entities']:
            layer=entity['layer'];weight=LAYERS[layer][1]/100
            document.setLineWidth(weight*mm)
            document.setStrokeColorRGB(.12,.12,.12)
            document.setFillColorRGB(.12,.12,.12)
            if layer=='WARNINGS':document.setFillColorRGB(.55,.12,.08)
            kind=entity['kind']
            if kind=='text':
                if entity['text'].isascii():
                    document.setFont('Helvetica',entity['height']*mm)
                    document.drawString(entity['x']*mm,entity['y']*mm,entity['text'])
            elif kind in ('line','polyline'):
                path=document.beginPath();points=entity['points'];path.moveTo(points[0][0]*mm,points[0][1]*mm)
                for x,y in points[1:]:path.lineTo(x*mm,y*mm)
                if entity.get('closed'):path.close()
                document.drawPath(path)
            elif kind=='circle':
                document.circle(entity['center'][0]*mm,entity['center'][1]*mm,entity['radius']*mm)
            elif kind=='image':
                document.drawImage(str(folder/entity['path']),entity['x']*mm,entity['y']*mm,width=entity['width']*mm,height=entity['height']*mm,mask='auto')
            elif kind=='block':
                for primitive in entity['definition']['entities']:
                    x,y,width,height=entity['x'],entity['y'],entity['width'],entity['height']
                    if primitive['kind']=='circle':
                        center=primitive['center']
                        document.circle((x+center[0]*width)*mm,(y+center[1]*height)*mm,primitive['radius']*width*mm)
                    else:
                        points=[[x+p[0]*width,y+p[1]*height] for p in primitive['points']]
                        path=document.beginPath();path.moveTo(points[0][0]*mm,points[0][1]*mm)
                        for px,py in points[1:]:path.lineTo(px*mm,py*mm)
                        if primitive.get('closed'):path.close()
                        document.drawPath(path)
        document.showPage()
    document.save()
    _pdf_unicode_labels(geometry, target)


def _pdf_unicode_labels(geometry, target):
    """Shape Unicode with bundled fonts and retain source text in ActualText.

    ReportLab's base Helvetica cannot render Arabic. PyMuPDF Story uses HarfBuzz
    and its bundled Noto/Droid fallbacks for glyphs, shaping and bidi ordering.
    ActualText keeps the original logical Unicode even when glyph ligatures have
    several code points or the font's ToUnicode map uses presentation forms.
    Readers may still insert bidi-run breaks or reorder adjacent table labels
    during extraction; the shared geometry and DXF retain the logical labels.
    """
    if not any(entity['kind'] == 'text' and not entity['text'].isascii()
               for sheet in geometry['sheets'] for entity in sheet['entities']):
        return
    import pymupdf
    from reportlab.lib.units import mm

    with pymupdf.open(target) as document:
        for page, sheet in zip(document, geometry['sheets']):
            for entity in sheet['entities']:
                if entity['kind'] != 'text' or entity['text'].isascii():
                    continue
                size = entity['height'] * mm
                x = entity['x'] * mm
                # Story places its first baseline about one font size below the
                # box top. Keep it on the same paper baseline as the CAD entity.
                top = (PAGE[1] - entity['y']) * mm - size
                width = min(entity.get('max_width', 412 - entity['x']), 412 - entity['x']) * mm
                rect = pymupdf.Rect(x, top, x + width, top + size * 1.8)
                color = '#8c1f14' if entity['layer'] == 'WARNINGS' else '#1f1f1f'
                css = ('* { margin: 0; padding: 0; } '
                       f'body {{ font-family: sans-serif; font-size: {size:.8f}pt; '
                       f'line-height: 1; color: {color}; }}')
                spare, scale = page.insert_htmlbox(
                    rect, '<span>' + escape(entity['text']) + '</span>', css=css, scale_low=1,
                )
                if spare < 0 or scale < 1:
                    raise ValueError('Unicode drawing label does not fit its readable text bounds.')
                # insert_htmlbox appends one page-content stream invoking its
                # shaped form. Mark only that stream, leaving neighbouring text
                # and CAD linework outside the replacement-text scope.
                xref = page.get_contents()[-1]
                actual = ('FEFF' + entity['text'].encode('utf-16-be').hex()).encode('ascii')
                marked = b'/Span << /ActualText <' + actual + b'> >> BDC\n'
                document.update_stream(xref, marked + document.xref_stream(xref) + b'\nEMC\n')
        # One font can be reused by many labels. Subset and deduplicate the
        # embedded resources before publishing the still-private revision.
        document.subset_fonts()
        data = document.tobytes(garbage=4, deflate=True, no_new_id=True)
    Path(target).write_bytes(data)


def _dxf(geometry, sheet, target):
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    document=ezdxf.new('R2010');document.units=4
    document.header['$INSUNITS']=4;document.header['$MEASUREMENT']=1
    document.header['$LWDISPLAY']=True
    document.appids.new('ISURVIX')
    document.dimstyles.new('ISURVIX-MM',dxfattribs={'dimtxt':2.5,'dimasz':2.0,'dimdec':0,'dimtad':1})
    document.styles.get('Standard').dxf.font='Arial.ttf'
    for name,(color,weight) in LAYERS.items():document.layers.new(name,dxfattribs={'color':color,'lineweight':weight})
    document.rootdict.add_xrecord('ISURVIX_GEOMETRY').extend([(1,geometry['digest']),(1,sheet['number']),(90,len(sheet['entities']))])
    space=document.modelspace()
    for index,entity in enumerate(sheet['entities']):
        attributes={'layer':entity['layer']}
        kind=entity['kind']
        if kind=='text':
            drawn=space.add_text(entity['text'],dxfattribs={**attributes,'height':entity['height']}).set_placement((entity['x'],entity['y']),align=TextEntityAlignment.LEFT)
        elif kind=='line':drawn=space.add_line(*entity['points'],dxfattribs=attributes)
        elif kind=='polyline':drawn=space.add_lwpolyline(entity['points'],close=entity.get('closed',False),dxfattribs=attributes)
        elif kind=='circle':drawn=space.add_circle(entity['center'],entity['radius'],dxfattribs=attributes)
        elif kind=='image':
            image_def=document.add_image_def(filename=entity['path'],size_in_pixel=(entity['pixel_width'],entity['pixel_height']))
            drawn=space.add_image(image_def,insert=(entity['x'],entity['y']),size_in_units=(entity['width'],entity['height']),dxfattribs=attributes)
        elif kind=='block':
            name='ISURVIX_'+entity['block_key'].upper()+'_'+_digest(entity['definition'])[:8].upper()
            if name not in document.blocks:
                block=document.blocks.new(name)
                for primitive in entity['definition']['entities']:
                    if primitive['kind']=='line':block.add_line(*primitive['points'],dxfattribs={'layer':'0'})
                    elif primitive['kind']=='polyline':block.add_lwpolyline(primitive['points'],close=primitive.get('closed',False),dxfattribs={'layer':'0'})
                    elif primitive['kind']=='circle':block.add_circle(primitive['center'],primitive['radius'],dxfattribs={'layer':'0'})
            drawn=space.add_blockref(name,(entity['x'],entity['y']),dxfattribs={**attributes,'xscale':entity['width'],'yscale':entity['height']})
        drawn.set_xdata('ISURVIX',[(1070,index),(1000,_digest(entity))])
    document.layouts.get('Layout1').page_setup(size=PAGE,margins=(0,0,0,0),units='mm',rotation=0)
    document.set_modelspace_vport(height=310,center=(210,148.5))
    audit=document.audit()
    if audit.has_errors:raise ValueError('Generated DXF failed audit.')
    document.saveas(target)


def _write_outputs(geometry, folder, revision, branding, prepared_by, checked_by, approved_by, released):
    """Author to an unpublished revision directory; only the wrapper publishes it."""
    drawing=copy.deepcopy(geometry);drawing.pop('digest',None)
    sketch_assets=drawing.pop('_sketch_assets', {})
    if not isinstance(sketch_assets, dict) or len(sketch_assets)>160:
        raise ValueError('Invalid sketch asset collection.')
    import base64
    total_asset_bytes=0
    for path, encoded in sketch_assets.items():
        if not isinstance(path,str) or not re.fullmatch(r'assets/sketch-[0-9a-f]{16}-(clean|reference)\.png',path):
            raise ValueError('Invalid sketch asset reference.')
        if not isinstance(encoded,str) or len(encoded)>128*1024*1024:
            raise ValueError('Sketch asset exceeds drawing limits.')
        raw=base64.b64decode(encoded,validate=True)
        total_asset_bytes+=len(raw)
        if total_asset_bytes>96*1024*1024:raise ValueError('Sketch assets exceed drawing limits.')
        target=folder/path;target.parent.mkdir(exist_ok=True)
        target.write_bytes(raw)
    drawing.update({'revision':revision,'released':bool(released),'prepared_by':_text(prepared_by),'checked_by':_text(checked_by),'approved_by':_text(approved_by)})
    logos=_prepare_logos(branding,drawing,folder)
    for index,sheet in enumerate(drawing['sheets'],1):
        sheet['sheet_no']=index
        sheet['entities'].extend(_titleblock(sheet,drawing,revision,prepared_by,checked_by,approved_by,released,logos))
    validate_geometry(drawing)
    drawing['digest']=_digest(drawing)
    (folder/'geometry.json').write_text(json.dumps(drawing,indent=2,ensure_ascii=True,allow_nan=False),encoding='utf-8')
    pdf=folder/'survey-drawings.pdf';_pdf(drawing,pdf,folder)
    import pymupdf
    pages=[]
    with pymupdf.open(pdf) as rendered:
        for index,sheet in enumerate(drawing['sheets']):
            filename=sheet['number'].lower()
            dxf=folder/f'{filename}.dxf';_dxf(drawing,sheet,dxf)
            preview=folder/f'{filename}.png'
            rendered[index].get_pixmap(matrix=pymupdf.Matrix(1.2,1.2),alpha=False).save(preview)
            pages.append({'key':sheet['key'],'number':sheet['number'],'title':sheet['title'],'scale':sheet['scale'],'sheet_no':index+1,'dxf':dxf.name,'preview':preview.name,'entity_count':len(sheet['entities'])})
    manifest={'version':VERSION,'revision':revision,'released':bool(released),'geometry_digest':drawing['digest'],'output_dir':'.','geometry':'geometry.json','pdf':pdf.name,'bundle':'survey-drawings.zip','sheets':pages,'warnings':drawing['warnings'],'missing_information':drawing['missing_information'],'assets':[logo['path'] for logo in logos]+list(sketch_assets)}
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    bundle=folder/manifest['bundle']
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(folder.rglob('*')):
            if file.is_file() and file!=bundle:
                archive.write(file,file.relative_to(folder).as_posix())
    return manifest


def render_outputs(geometry: dict, output_dir: Path, *, revision: int=1, branding: dict|None=None, prepared_by: str='', checked_by: str='', approved_by: str='', released: bool=False) -> dict:
    """Write isolated immutable revision files; caller must authorise release first.

    A repeated revision is rejected, never overwritten. The returned paths are absolute;
    ``geometry.json`` and manifest contain portable paths relative to that revision folder.
    Raster logo assets are included beside DXF files. All other PDF content is vector.
    """
    if type(revision) is not int or revision<1 or revision>999999:
        raise ValueError('Positive bounded drawing revision required.')
    if released and (not _text(checked_by) or not _text(approved_by)):
        raise ValueError('Released outputs require checked and approved human identities.')
    validate_geometry(geometry)
    parent=Path(output_dir).resolve();parent.mkdir(parents=True,exist_ok=True)
    folder=parent/f'revision-{revision:03d}'
    if folder.exists():raise FileExistsError(f'Output revision already exists: {folder.name}')
    staging=parent/f'.building-{revision:03d}-{uuid.uuid4().hex}'
    staging.mkdir()
    try:
        manifest=_write_outputs(geometry,staging,revision,branding,prepared_by,checked_by,approved_by,released)
        # Atomic same-filesystem rename publishes a complete set, never partial outputs.
        # On Windows rename also refuses an existing destination; Linux must recheck.
        if folder.exists():raise FileExistsError(f'Output revision already exists: {folder.name}')
        staging.rename(folder)
    except Exception:
        # Only our newly created unpublished staging directory is removed.
        if staging.is_dir():
            if staging.resolve().parent!=parent or not staging.name.startswith('.building-'):
                raise RuntimeError('Refused cleanup outside the drawing revision parent.')
            shutil.rmtree(staging)
        raise
    manifest=copy.deepcopy(manifest)
    for key in ('geometry','pdf','bundle'):manifest[key]=str(folder/manifest[key])
    manifest['output_dir']=str(folder)
    for sheet in manifest['sheets']:
        for key in ('dxf','preview'):sheet[key]=str(folder/sheet[key])
    manifest['assets']=[str(folder/path) for path in manifest['assets']]
    return manifest
