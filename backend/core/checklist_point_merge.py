"""Append reviewed workbook points to an unused draft without replacing its structure."""
from copy import deepcopy
from django.core.exceptions import ValidationError
from .checklist_wizard_service import digest
from .template_service import validate_definition


def merged_definition(target, records, marker):
    from .editor_hierarchy import merge_group_names
    definition=merge_group_names(deepcopy(target.definition),[record['definition'] for record in records])
    sections={s['title'].strip().casefold():s for s in definition['sections']}
    existing_ids={field['id'] for section in definition['sections'] for field in section['fields']}
    for record in records:
        for section in record['definition']['sections']:
            key=section['title'].strip().casefold()
            destination=sections.get(key)
            if destination is None:
                destination={**deepcopy(section),'id':'import_section_'+digest([marker,key])[:16],'fields':[]}
                definition['sections'].append(destination);sections[key]=destination
            labels={field['label'].strip().casefold() for field in destination['fields']}
            for field in section['fields']:
                if field['label'].strip().casefold() in labels:
                    raise ValidationError('Duplicate checkpoint in '+section['title']+': '+field['label']+'. Remove it from the import sample.')
                item=deepcopy(field);item['id']='import_'+digest([marker,record['key'],section['id'],field['id']])[:24]
                if item['id'] in existing_ids:raise ValidationError('These points were already added to this draft.')
                existing_ids.add(item['id']);labels.add(item['label'].strip().casefold());destination['fields'].append(item)
    validate_definition(definition)
    return definition
