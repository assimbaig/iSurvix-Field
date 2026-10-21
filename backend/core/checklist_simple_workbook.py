"""One-sheet, plain-language checklist import using the existing safe XLSX intake."""
import hashlib
import math
from .checklist_workbook import _error, _bool, _text, WORKFLOWS
from .template_service import FIELD_TYPES, validate_definition
from django.core.exceptions import ValidationError

HEADERS=['Section','Checkpoint','Input type','Required','Photo','Choices','Unit','Help']


def parse_simple(workbook, raw):
    sheet=workbook['Checklist']
    sheet.reset_dimensions();sheet.calculate_dimension(force=True)
    if sheet.max_row>3007 or sheet.max_column>8:
        _error('Checklist',0,'size','Use up to 3,000 checkpoints and the eight sample columns.')
    rows=list(sheet.iter_rows())
    for row in rows:
        for cell in row:
            value=cell.value
            if cell.data_type in {'f','e'}:
                _error('Checklist',cell.row,cell.column_letter,'Formulas and Excel errors are not supported.')
            if value is not None and (not isinstance(value,(str,bool,int,float)) or isinstance(value,float) and not math.isfinite(value)):
                _error('Checklist',cell.row,cell.column_letter,'Use plain text, booleans or finite numbers.')
            if isinstance(value,str) and len(value)>10000:
                _error('Checklist',cell.row,cell.column_letter,'Cell text exceeds its limit.')
    if [sheet.cell(7,col).value for col in range(1,9)]!=HEADERS:
        _error('Checklist',7,'headers','Keep the sample column headings unchanged.')
    name=_text(sheet['B2'].value,'Checklist',2,'Checklist name',160,True)
    industry=_text(sheet['E2'].value,'Checklist',2,'Industry',30,True).strip().lower()
    workflow=_text(sheet['H2'].value,'Checklist',2,'Workflow',40,True).strip().lower()
    if WORKFLOWS.get(workflow)!=industry:
        _error('Checklist',2,'Workflow','Choose a supported workflow matching the industry.')
    sections={}
    for rowno,cells in enumerate(rows[7:],8):
        values=[cell.value for cell in cells]
        if not any(value not in (None,'') for value in values):continue
        section,label,kind,required,photo,choices,unit,help_text=values
        title=_text(section,'Checklist',rowno,'Section',160,True).strip()
        label=_text(label,'Checklist',rowno,'Checkpoint',3000,True).strip()
        kind=_text(kind,'Checklist',rowno,'Input type',30,True).strip().lower()
        if kind not in FIELD_TYPES-{'table'}:
            _error('Checklist',rowno,'Input type','Choose text, textarea, number, date, select, inspection or photo.')
        photo=_text(photo,'Checklist',rowno,'Photo',20).strip().lower() or 'none'
        if photo not in {'none','optional','required'}:
            _error('Checklist',rowno,'Photo','Choose None, Optional or Required.')
        sid='section_'+hashlib.sha256(title.casefold().encode()).hexdigest()[:16]
        section=sections.setdefault(sid,{'id':sid,'title':title,'fields':[]})
        if any(field['label'].casefold()==label.casefold() for field in section['fields']):
            _error('Checklist',rowno,'Checkpoint','Duplicate checkpoint in this section.')
        if isinstance(required,str) and required.strip().lower() in {'yes','no'}:
            required=required.strip().lower()=='yes'
        field={'id':'point_'+str(rowno-7),'label':label,'type':kind,'required':_bool(required,'Checklist',rowno,'Required'),
               'photo_required':photo=='required'}
        if kind=='photo':
            field['photo_required']=field['required'] or photo=='required'
        if kind=='select':
            field['options']=[x.strip() for x in _text(choices,'Checklist',rowno,'Choices').split('|') if x.strip()]
        elif choices not in (None,''):
            _error('Checklist',rowno,'Choices','Choices belong to select inputs only.')
        if unit not in (None,''):field['unit']=_text(unit,'Checklist',rowno,'Unit',80)
        if help_text not in (None,''):field['description']=_text(help_text,'Checklist',rowno,'Help',1000)
        section['fields'].append(field)
    definition={'title':name,'sections':list(sections.values())}
    try:validate_definition(definition)
    except ValidationError as error:_error('Checklist',0,'definition','; '.join(error.messages))
    return {'sha256':hashlib.sha256(raw).hexdigest(),'checklists':[{'key':'one_page','name':name,'industry':industry,
        'workflow_type':workflow,'definition':definition}],'warnings':[]}
