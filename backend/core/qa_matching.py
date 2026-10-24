"""QA evidence links and personal checklist ordering, separate from acceptance."""
from copy import deepcopy

from django.core.exceptions import ValidationError

from .survey_processing_models import SurveyProcessingEvent


LINK_ACTIONS={'confirm_link','unlink','reassign_link'}
CATEGORY_LABELS={'':'General Info','Civil':'Civil','Electrical':'Electrical','Tower':'Tower'}
GROUP_CATEGORIES={'power supply':'Electrical','tower equipment':'Tower',
    'dc power system details':'Electrical','other-operator electrical readings':'Electrical',
    'electromechanical & grounding':'Electrical'}
STANDARD_SECTIONS={('civil','Civil & site inspection'):'Civil',
    ('grounding','Electromechanical & grounding'):'Electrical',
    ('dc','DC power system details'):'Electrical',
    ('operator_readings','Other-operator electrical readings'):'Electrical'}


def category_for(section,field):
    for label,source in [(field.get('category'),'approved field category'),
                         (section.get('category'),'approved section category'),
                         (section.get('group'),'approved group')]:
        if not isinstance(label,str) or not label.strip():continue
        normalized=label.strip().casefold()
        known={label.casefold():key for key,label in CATEGORY_LABELS.items()}
        known.update(GROUP_CATEGORIES)
        return known.get(normalized,''),normalized in known,source
    standard=STANDARD_SECTIONS.get((section['id'],section['title']))
    return (standard,True,'standard section') if standard else ('',False,'unclassified')


def catalog(revision):
    result={}
    for section in revision.snapshot['schema'].get('sections',[]):
        for field in section.get('fields',[]):
            category,known,source=category_for(section,field)
            result[field['id']]={'category':category,'category_label':CATEGORY_LABELS[category],
                'category_known':known,'category_source':source,'group':section.get('group',''),
                'section_id':section['id'],'section_title':section['title'],
                'instruction':str(field.get('instruction') or field.get('instructions') or field.get('help') or
                    field.get('description') or field.get('help_text') or field.get('question') or ''),
                'required':field.get('required',False),'photo_required':field.get('photo_required',False),
                'evidence_rules':deepcopy(field.get('evidence_rules',{}))}
    return result


def photo_id(source):
    ident=str(source.get('source_id',''))
    return int(ident.split(':')[1]) if ident.startswith('photo:') and ident.split(':')[1].isdigit() else None


def valid_ai_sources(item,findings):
    """Raw observations remain in findings; unsupported candidates are not links."""
    if item.get('conflict') or item.get('confidence')!='high' or item.get('status') in {'Missing','Not applicable'} or item.get('value') in (None,'',[],{}):return []
    result=[]
    for source in item.get('sources',[]):
        matching=[f for f in findings if f.get('source_id')==source.get('source_id') and f.get('field_hint')==item['id'] and
            f.get('value') not in (None,'',[],{}) and f.get('confidence')=='high' and not f.get('mapping_unassigned')]
        if matching:result.append(deepcopy(source))
    return result


def replay(revision,payload):
    items={item['id']:item for item in payload['checklist_items']}
    for item in items.values():
        item['sources']=valid_ai_sources(item,payload.get('findings',[]))
    for event in revision.processing_events.filter(action__in=['qa_answer','qa_mapping','qa_link']).order_by('pk'):
        if event.action in {'qa_answer','qa_mapping'}:
            for ident,updates in event.payload.get('items',{}).items():
                if ident in items:items[ident].update(deepcopy(updates))
            continue
        ident=event.payload['field_id'];item=items.get(ident)
        if item is None:continue
        pid=event.payload['photo_id']
        sources=[source for source in item.get('sources',[]) if photo_id(source)!=pid]
        if event.payload['state']=='qa_confirmed':
            source=next((p for p in revision.snapshot['photos'] if p['id']==pid),None)
            if source:sources.append({'source_id':'photo:'+str(pid),'reference':source['filename'],
                'mapping_status':'qa_confirmed','mapping_reason':event.reason,'reviewed_by':event.actor_id})
        item['sources']=sources
    return payload


def link_state(revision,payload):
    allowed={photo['id'] for photo in revision.snapshot['photos']}
    result=[];seen=set()
    for item in payload['checklist_items']:
        manual=bool(item.get('qa_by'))
        ai=valid_ai_sources(item,payload.get('findings',[]))
        ai_ids={photo_id(source) for source in ai}
        for source in item.get('sources',[]):
            pid=photo_id(source)
            if pid not in allowed:continue
            if (pid,item['id']) in seen:continue
            confirmed=source.get('mapping_status')=='qa_confirmed' or manual
            if not confirmed and pid not in ai_ids:continue
            seen.add((pid,item['id']))
            explanations=[finding.get('mapping_reason','') for finding in payload.get('findings',[])
                if photo_id(finding)==pid and finding.get('field_hint')==item['id'] and finding.get('mapping_reason')]
            result.append({'photo_id':pid,'field_id':item['id'],
                'state':'qa_confirmed' if confirmed else 'ai_suggested',
                'reason':source.get('mapping_reason',item.get('reason','')) if confirmed else ' · '.join(dict.fromkeys(explanations))[:4000],
                'confidence':None if confirmed else item.get('confidence'),
                'source':'QA review' if confirmed else 'Local AI Analysis'})
    return result


def order_state(revision,actor_id):
    from .survey_processing import digest
    defaults={key:[] for key in CATEGORY_LABELS}
    fields=catalog(revision)
    for ident,field in fields.items():defaults[field['category']].append(ident)
    for event in revision.processing_events.filter(action='qa_display_order',actor_id=actor_id).order_by('pk'):
        category=event.payload.get('category');ids=event.payload.get('field_ids')
        if category in defaults and isinstance(ids,list) and len(ids)==len(defaults[category]) and set(ids)==set(defaults[category]):
            defaults[category]=ids
    return defaults,digest({'revision_id':revision.pk,'actor_id':actor_id,'order':defaults})


def state(revision,payload,actor,private=True):
    links=link_state(revision,payload)
    if not private:links=[link for link in links if link['state']=='qa_confirmed']
    assigned={link['photo_id'] for link in links}
    ids=[p['id'] for p in revision.snapshot['photos']]
    order,signature=order_state(revision,actor.pk)
    observations={pid:[] for pid in ids}
    for record in revision.source_analyses.all() if private else []:
        from .survey_processing import digest
        if digest(record.payload)!=record.digest:raise ValidationError('Saved source analysis integrity verification failed.')
        pid=photo_id({'source_id':record.source_id})
        if pid not in observations:continue
        for finding in record.payload.get('findings',[]):
            observations[pid].append({**deepcopy(finding),'source_id':record.source_id,
                'reference':record.payload.get('reference','')})
    history=[{'id':event.pk,'action':event.action,'by':event.actor.get_username(),
        'time':event.created_at.isoformat(),'reason':event.reason,'details':event.payload}
        for event in revision.processing_events.filter(action__in=['qa_link','qa_display_order','qa_mapping','qa_answer']).select_related('actor').order_by('-pk')[:100]] if private else []
    counts={'total':len(ids),'assigned':len(assigned),'unassigned':len(set(ids)-assigned),
        'suggested':sum(link['state']=='ai_suggested' for link in links),
        'confirmed':sum(link['state']=='qa_confirmed' for link in links)}
    return {'links':links,'unassigned_photo_ids':[pid for pid in ids if pid not in assigned],
        'counts':counts,'display_order':order,'order_digest':signature,
        'observations':observations,'matching_history':history}


def require_revision(revision,data):
    if type(data.get('revision_id')) is not int or data['revision_id']!=revision.pk or data.get('source_digest')!=revision.digest:
        raise ValidationError('The submitted evidence revision changed. Refresh this QA workspace before saving.')


def action(revision,c,actor,data,payload):
    from .template_views import require_field_editable
    from .survey_processing import review_digest
    name=data.get('action');fields=catalog(revision)
    require_revision(revision,data)
    if name=='reorder':
        category=data.get('category');ids=data.get('field_ids')
        order,signature=order_state(revision,actor.pk)
        if data.get('expected_order_digest')!=signature:raise ValidationError('Your checklist display order changed. Refresh before reordering.')
        if not isinstance(category,str) or category not in order or not isinstance(ids,list) or any(not isinstance(i,str) for i in ids) or len(ids)!=len(order[category]) or len(set(ids))!=len(ids) or set(ids)!=set(order[category]):
            raise ValidationError('Reorder the exact checklist points within one category. Not Assigned is always last and cannot be moved.')
        if ids!=order[category]:SurveyProcessingEvent.objects.create(revision=revision,actor=actor,action='qa_display_order',
            payload={'category':category,'field_ids':ids},reason='QA personal checklist display order')
        return
    if name not in LINK_ACTIONS:raise ValidationError('Choose a supported photo link action.')
    if data.get('expected_review_digest')!=review_digest(payload):raise ValidationError('The QA review changed. Refresh before saving another decision.')
    pid=data.get('photo_id');ident=data.get('field_id')
    if type(pid) is not int or pid not in {p['id'] for p in revision.snapshot['photos']}:raise ValidationError('Choose a photo from this submitted evidence revision.')
    if name=='reassign_link':ident=data.get('to_field_id')
    if not isinstance(ident,str) or ident not in fields:raise ValidationError('Choose an actual approved checklist point.')
    require_field_editable(c,ident)
    reason=data.get('reason','')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>4000:raise ValidationError('Record a photo matching reason of at most 4000 characters.')
    links=link_state(revision,payload)
    existing={(link['photo_id'],link['field_id']):link for link in links}
    changes=[]
    if name in {'unlink','reassign_link'}:
        old=data.get('from_field_id') if name=='reassign_link' else ident
        if not isinstance(old,str) or old not in fields or (pid,old) not in existing:raise ValidationError('This source photo is not linked to the selected checklist point. Refresh the workspace.')
        if name=='reassign_link' and old==ident:raise ValidationError('Choose a different target checklist point.')
        require_field_editable(c,old)
        changes.append((old,'removed'))
    if name!='unlink':
        if existing.get((pid,ident),{}).get('state')!='qa_confirmed':changes.append((ident,'qa_confirmed'))
    for field,state in changes:
        SurveyProcessingEvent.objects.create(revision=revision,actor=actor,action='qa_link',reason=reason.strip(),
            payload={'field_id':field,'photo_id':pid,'state':state,'operation':name})
