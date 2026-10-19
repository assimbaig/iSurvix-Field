"""Catalog authorization and standard-template applicability, without live schema edits."""
import json
from django.core.exceptions import PermissionDenied, ValidationError

STANDARD_TYPES={
    'telecom_survey_default':('telecom','telecom_survey'),
    'telecom_inspection_bts':('telecom','telecom_inspection'),
    'telecom_inspection_colocation':('telecom','telecom_inspection'),
    'construction_inspection_all':('construction','construction_inspection'),
}

def standard_metadata(definition):
    metadata=definition.get('standard_catalog')
    if metadata is None:return None
    if not isinstance(metadata,dict) or not isinstance(metadata.get('key'),str) or metadata['key'] not in STANDARD_TYPES:
        raise ValidationError('Unknown standard checklist identity.')
    if type(metadata.get('version')) is not int or metadata['version']!=1:
        raise ValidationError('Unsupported standard checklist version.')
    if (metadata.get('industry'),metadata.get('workflow_type'))!=STANDARD_TYPES[metadata['key']]:
        raise ValidationError('The standard industry and workflow must match its catalog identity.')
    if set(metadata)-{'key','version','industry','workflow_type','stages','rooms'}:
        raise ValidationError('Unknown standard checklist configuration.')
    stages=metadata.get('stages',[]);rooms=metadata.get('rooms',[])
    if metadata['industry']=='construction':
        from .standard_checklists import STAGES,_rooms
        if not isinstance(stages,list) or not stages or any(not isinstance(s,str) or s not in STAGES for s in stages) or len(set(stages))!=len(stages):
            raise ValidationError('Select valid, distinct construction stages.')
        try:_rooms(rooms)
        except ValueError as error:raise ValidationError(str(error)) from error
    elif stages!=[] or rooms!=[]:
        raise ValidationError('Rooms and construction stages belong to Construction Inspection.')
    return metadata

def wizard_metadata(definition):
    metadata=definition.get('wizard_context')
    if metadata is None:return None
    workflows={'telecom_survey':'telecom','telecom_inspection':'telecom','construction_inspection':'construction'}
    if (not isinstance(metadata,dict) or set(metadata)!={'version','industry','workflow_type'} or
        type(metadata.get('version')) is not int or metadata['version']!=1 or
        not isinstance(metadata.get('workflow_type'),str) or
        workflows.get(metadata['workflow_type'])!=metadata.get('industry')):
        raise ValidationError('Choose a supported industry and checklist workflow.')
    standard=standard_metadata(definition)
    if standard and any(standard[key]!=metadata[key] for key in ('industry','workflow_type')):
        raise ValidationError('Wizard and standard industry/workflow must agree.')
    return metadata

def validate_standard_project(template,project,workflow_type=None):
    if template is None:return
    metadata=wizard_metadata(template.definition) or standard_metadata(template.definition)
    if not metadata:return
    from .industry_service import industry_family
    if metadata['industry']!=industry_family(project):
        raise ValidationError('This standard checklist belongs to a different project industry.')
    if workflow_type and metadata['workflow_type']!=workflow_type:
        raise ValidationError('Choose the standard checklist for this activity workflow before assigning the task.')

def permitted_industries(actor):
    from .access import is_super_admin,role_for,accessible_projects
    from .models import Profile
    if is_super_admin(actor):return {'telecom','construction'}
    if role_for(actor)!=Profile.Roles.ADMIN:
        raise PermissionDenied('Standard checklist management requires a Project Admin or Super Admin.')
    projects=accessible_projects(actor)
    if not projects.exists():raise PermissionDenied('An active project administration grant is required.')
    assigned=actor.profile.admin_industry
    from .industry_service import industry_family
    return {industry_family(assigned)} if assigned else {industry_family(code) for code in projects.values_list('industry',flat=True)}

def catalog_for(actor):
    from .standard_checklists import catalog_entries
    allowed=permitted_industries(actor)
    result=[]
    for raw in catalog_entries():
        if raw['industry'] not in allowed:continue
        entry={**raw,'section_count':raw['sections_count'],'field_count':raw['fields_count'],
               'stages':[{'id':stage['value'],'label':stage['label']} for stage in raw['stage_choices']],
               'room_types':[{'id':kind,'label':kind.replace('_',' ').title()} for kind in raw['room_types']]}
        result.append(entry)
    return result

def entry_for(actor,key):
    if not isinstance(key,str) or len(key)>80:raise ValidationError('Choose a standard checklist.')
    entry=next((item for item in catalog_for(actor) if item['key']==key),None)
    if not entry:raise PermissionDenied('This standard checklist is outside your assigned industry.')
    return entry

def selection_payload(data):
    stages=data.getlist('stages') if hasattr(data,'getlist') and 'stages' in data else data.get('stages')
    if isinstance(stages,str):raise ValidationError('Construction stages must be a list.')
    raw=data.get('rooms','[]')
    if isinstance(raw,str):
        if len(raw)>16000:raise ValidationError('Room selection is too large.')
        try:rooms=json.loads(raw)
        except (ValueError,TypeError):raise ValidationError('Room selection must be a valid JSON list.')
    else:rooms=raw
    if not isinstance(rooms,list):raise ValidationError('Room selection must be a list.')
    return stages,rooms
