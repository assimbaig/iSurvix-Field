"""Expose real standard/scoped-library additions to an existing editor draft."""
from copy import deepcopy
from .checklist_recommendations import recommend, normal
from .checklist_wizard_service import source_identity


def additions(actor, template):
    context=source_identity(template,actor)
    catalog=recommend(actor,context['industry'],context['workflow_type'])
    existing={normal(section['title']):section for section in template.definition['sections']}
    result=[]
    for section in catalog['sections']:
        target=existing.get(normal(section['title']))
        labels={normal(field['label']) for field in target['fields']} if target else set()
        for item in section['fields']:
            if normal(item['field']['label']) in labels:continue
            result.append({'id':item['id'],'field':deepcopy(item['field']),
                'section_id':target['id'] if target else None,'section_title':target['title'] if target else section['title'],
                'group':target.get('group','') if target else '', 'source':item.get('source',''),
                'reason':'Available in the selected workflow standard or a permitted published checklist; absent from this section.',
                'uses':item['uses']})
    return {'template_id':template.pk,'version':template.version,'catalog_digest':catalog['digest'],'recommendations':result}
