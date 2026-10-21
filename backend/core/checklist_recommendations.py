"""Review-first suggestions from standards and permitted published definitions.

Learning changes the available suggestions/ranking only; no operational answers,
photos, approvals or model weights are used or changed.
"""
from copy import deepcopy
import json
import re
from django.core.exceptions import ValidationError
from .checklist_wizard_service import identity, digest, valid_name, source_identity
from .standard_checklists import CATALOG, build_standard
from .template_service import validate_definition


def normal(value):
    return re.sub(r'\s+', ' ', str(value).strip().casefold())


def recommend(actor, industry, workflow):
    identity(actor, industry, workflow)
    from .template_views import template_scope
    sections = {}
    def add(definition, source, learned=False):
        for original in definition.get('sections', []):
            sid = 's_' + digest(normal(original['title']))[:16]
            section = sections.setdefault(sid, {'id':sid,'title':original['title'],'fields':{},'uses':0,'sources':[]})
            if source not in section['sources']: section['sources'].append(source)
            if learned: section['uses'] += 1
            for field in original.get('fields', []):
                # Preserve every condition/choice when distinguishing suggestions.
                content = {key:value for key,value in field.items() if key != 'id'}
                fid = 'p_' + digest([sid, content])[:20]
                item = section['fields'].setdefault(fid, {'id':fid,'field':deepcopy(field),'uses':0,'source':source})
                if learned: item['uses'] += 1
    for key, name, kind, module in CATALOG:
        if kind == industry and module == workflow:
            add(build_standard(key), 'Standard: ' + name)
    for template in template_scope(actor).filter(published=True,disabled=False).order_by('-created_at','-pk')[:100]:
        try: context = source_identity(template, actor)
        except ValidationError: continue
        if context == {'industry':industry,'workflow_type':workflow}:
            add(template.definition, 'Published: ' + template.name, True)
    result=[]
    for section in sections.values():
        section['fields'] = sorted(section['fields'].values(), key=lambda item:-item['uses'])
        result.append(section)
    result.sort(key=lambda item:-item['uses'])
    if len(result)>100 or sum(len(s['fields']) for s in result)>3000:
        raise ValidationError('The recommendation library exceeds the checklist limit. Use a specific standard or import a focused checklist.')
    return {'sections':result,'digest':digest(result)}


def selected_sections(catalog, selected, custom):
    known = {s['id']:s for s in catalog['sections']}
    if not isinstance(custom, str) or len(custom)>16000:
        raise ValidationError('Custom section names are too long.')
    names = [name.strip() for name in custom.splitlines() if name.strip()]
    if len(selected)!=len(set(selected)) or any(key not in known for key in selected):
        raise ValidationError('Choose valid recommended sections.')
    result = [deepcopy(known[key]) for key in selected]
    for name in names:
        if len(name)>160: raise ValidationError('Section names must be at most 160 characters.')
        sid='s_'+digest(normal(name))[:16]
        if any(section['id']==sid for section in result): raise ValidationError('Section names must be distinct.')
        result.append({'id':sid,'title':name,'fields':[],'uses':0,'sources':['Your new section']})
    if not 1<=len(result)<=100: raise ValidationError('Select or add between 1 and 100 sections.')
    return result


def create_recommended(actor, name, industry, workflow, expected, selected, custom, points, additions):
    from django.db import transaction
    from .governance_views import lock_governance, audit
    from .models import ChecklistTemplate
    with transaction.atomic():
        lock_governance(actor)
        catalog=recommend(actor, industry, workflow)
        if catalog['digest'] != expected:
            raise ValidationError('Recommendations changed. Review the suggested sections again before creating a draft.')
        sections=selected_sections(catalog, selected, custom)
        fields={item['id']:item for section in sections for item in section['fields']}
        if len(points)!=len(set(points)) or any(key not in fields for key in points):
            raise ValidationError('Choose checkpoints belonging to your accepted sections.')
        try: extra=json.loads(additions or '[]')
        except (TypeError,ValueError): raise ValidationError('Invalid custom checkpoints.')
        if not isinstance(extra,list) or len(extra)>3000: raise ValidationError('Too many custom checkpoints.')
        by_section={s['id']:[] for s in sections}
        for section in sections:
            for item in section['fields']:
                if item['id'] in points:
                    field=deepcopy(item['field']);field['id']=item['id']
                    by_section[section['id']].append(field)
        for index,item in enumerate(extra):
            if not isinstance(item,dict) or item.get('section') not in by_section:
                raise ValidationError('A custom checkpoint needs an accepted section.')
            field={key:item[key] for key in ['label','type','required','photo_required'] if key in item}
            if field.get('type')=='select':
                field['options']=[x.strip() for x in str(item.get('choices','')).split('|') if x.strip()]
            field['id']='custom_'+digest([index,field])[:20]
            by_section[item['section']].append(field)
        definition={'title':valid_name(name),'wizard_context':identity(actor,industry,workflow),'sections':[]}
        for section in sections:
            if not by_section[section['id']]: raise ValidationError('Add at least one checkpoint to '+section['title']+'.')
            definition['sections'].append({'id':section['id'],'title':section['title'],'fields':by_section[section['id']]})
        validate_definition(definition)
        template=ChecklistTemplate.objects.create(name=valid_name(name),definition=definition,created_by=actor,
            client_left_name='',client_right_name='')
        audit(actor,'checklist_recommendations_accepted',template_id=template.pk,sections=len(sections),points=sum(len(s['fields']) for s in definition['sections']),catalog_digest=expected)
        return template
