"""Create a new definition from explicitly selected authoritative leaf fields."""
from copy import deepcopy
from django.core.exceptions import ValidationError
from .template_service import IDENTIFIER,validate_definition


def subset_definition(source_definition,field_ids,name):
    if not isinstance(name,str) or not name.strip() or len(name.strip())>160:
        raise ValidationError('Provide a checklist name of at most 160 characters.')
    if not isinstance(field_ids,list) or not 1<=len(field_ids)<=3000:
        raise ValidationError('Select at least one checklist item.')
    if any(not isinstance(fid,str) or not IDENTIFIER.fullmatch(fid) for fid in field_ids):
        raise ValidationError('The selection contains a malformed item identifier.')
    if len(set(field_ids))!=len(field_ids):
        raise ValidationError('Each checklist item may be selected once only.')
    validate_definition(source_definition)
    available={field['id'] for section in source_definition['sections'] for field in section['fields']}
    selected=set(field_ids)
    if not selected.issubset(available):
        raise ValidationError('An item is not present in the selected source checklist. Reload the source and try again.')
    result=deepcopy(source_definition)
    result['title']=name.strip()
    # The source description may claim that every original row is included.
    result['description']='Selected checklist items. Review this draft before publishing.'
    sections=[]
    for section in source_definition['sections']:
        fields=[deepcopy(field) for field in section['fields'] if field['id'] in selected]
        if fields:
            chosen=deepcopy(section)
            chosen['fields']=fields
            sections.append(chosen)
    result['sections']=sections
    validate_definition(result)
    return result
