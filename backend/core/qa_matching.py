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
    """Return high-confidence evidence locations, independent of answer state.

    A photo can be relevant to an unanswered inspection point without proving
    pass/fail or supplying an answer value. Evidence location and checklist
    answer confidence are separate decisions; conflicts still suppress AI links.
    """
    if item.get('conflict'):return []
    from .survey_checklist_mapping import has_source_observation
    result=[]
    for source in item.get('sources',[]):
        matching=[f for f in findings if f.get('source_id')==source.get('source_id') and f.get('field_hint')==item['id'] and
            f.get('confidence')=='high' and not f.get('mapping_unassigned') and
            has_source_observation(f)]
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
            evidence_findings=[finding for finding in payload.get('findings',[])
                if photo_id(finding)==pid and finding.get('field_hint')==item['id']
                and finding.get('confidence')=='high' and not finding.get('mapping_unassigned')]
            result.append({'photo_id':pid,'field_id':item['id'],
                'state':'qa_confirmed' if confirmed else 'ai_suggested',
                'reason':source.get('mapping_reason',item.get('reason','')) if confirmed else ' · '.join(dict.fromkeys(explanations))[:4000],
                'confidence':None if confirmed else 'high' if evidence_findings else item.get('confidence'),
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


def legacy_photo_match(pid,links):
    """Project retained AI links, without inventing rankings or changing history.

    Only the already validated, replayed links are authoritative here. Reading raw
    field hints would resurrect QA removals or unassigned/uncertain observations.
    """
    candidates=[{'field_id':link['field_id'],'rank':rank,'reason':link.get('reason') or
        'This retained AI source link requires QA confirmation.'}
        for rank,link in enumerate((link for link in links
            if link['photo_id']==pid and link['state']=='ai_suggested'),1)]
    return {'state':'proposed','reason':'Retained AI source links; QA confirmation is required.',
        'candidates':candidates} if candidates else None


def state(revision,payload,actor,private=True):
    links=link_state(revision,payload)
    if not private:links=[link for link in links if link['state']=='qa_confirmed']
    assigned={link['photo_id'] for link in links}
    ids=[p['id'] for p in revision.snapshot['photos']]
    order,signature=order_state(revision,actor.pk)
    observations={pid:[] for pid in ids}
    final_findings={finding.get('finding_key'):finding for finding in payload.get('findings',[])
        if isinstance(finding,dict) and isinstance(finding.get('finding_key'),str)}
    durable_mappings=[]
    analysed_payloads=[]
    analysed_sources=set()
    for record in revision.source_analyses.all() if private else []:
        from .survey_processing import digest
        if digest(record.payload)!=record.digest:raise ValidationError('Saved source analysis integrity verification failed.')
        if record.source_id.startswith('mapping:'):
            durable_mappings.append((record.source_id, record.payload))
            continue
        analysed_payloads.append(record.payload)
        pid=photo_id({'source_id':record.source_id})
        if pid not in observations:continue
        analysed_sources.add(record.source_id)
        for finding in record.payload.get('findings',[]):
            enriched=deepcopy(finding)
            final=final_findings.get(finding.get('finding_key'))
            if final:enriched.update(deepcopy(final))
            observations[pid].append({**enriched,'source_id':record.source_id,
                'reference':record.payload.get('reference','')})
    photo_matches={}
    if private:
        fields=catalog(revision)
        saved_matches={str(row.get('source_id','')):row for row in payload.get('photo_matches',[])
            if isinstance(row,dict) and isinstance(row.get('source_id'),str)}
        job_status=getattr(getattr(revision,'processing_job',None),'status','')
        partial_matches={}
        if job_status=='preparing_checklist' and durable_mappings:
            from .survey_checklist_mapping import (photo_candidate_outcomes,
                partial_mapping_context, verified_partial_mapping)
            job=revision.processing_job
            context=partial_mapping_context(analysed_payloads,revision.snapshot['schema'],
                job.model,job.model_digest)
            current_mappings=[mapped for source_id,mapped in durable_mappings
                if verified_partial_mapping(source_id,mapped,context)]
            mapped_sources={row.get('source_id') for mapped in current_mappings
                for row in mapped.get('photo_matches',[]) if isinstance(row,dict)}
            partial_matches={row['source_id']:row for row in photo_candidate_outcomes(
                [{'source_id':source} for source in analysed_sources & mapped_sources],current_mappings)}
        display_names=payload.get('photo_names') if isinstance(payload.get('photo_names'),dict) else {}
        if not display_names:
            from .survey_processing import generated_photo_names
            display_names=generated_photo_names(revision.snapshot,payload.get('findings',[]))
        for photo in revision.snapshot.get('photos',[]):
            pid=photo.get('id')
            source_id='photo:'+str(pid)
            saved=saved_matches.get(source_id)
            if saved is None:
                saved=partial_matches.get(source_id)
            if saved is None and job_status=='ready_for_review':
                saved=legacy_photo_match(pid,links)
            if saved:
                status=saved.get('state') if saved.get('state') in {'proposed','unmatched'} else 'unmatched'
                reason=str(saved.get('reason') or '')[:4000]
                raw_candidates=saved.get('candidates',[])
            elif job_status=='ready_for_review':
                status='unmatched';reason='No supported checklist match was saved for this photo.';raw_candidates=[]
            elif job_status=='failed':
                status='failed';reason='AI analysis failed. The original photo is available for manual review.';raw_candidates=[]
            else:
                status='pending';reason='AI analysis has not completed for this photo.';raw_candidates=[]
            candidates=[]
            if isinstance(raw_candidates,list):
                for candidate in raw_candidates[:10]:
                    if not isinstance(candidate,dict):continue
                    ident=candidate.get('field_id');field=fields.get(ident)
                    if not field:continue
                    score=candidate.get('score');kind=candidate.get('score_kind')
                    if type(score) not in (int,float) or not isinstance(kind,str) or not kind.endswith('_similarity'):
                        score=None;kind=''
                    candidates.append({'field_id':ident,'label':next((entry['label'] for section in revision.snapshot['schema'].get('sections',[]) for entry in section.get('fields',[]) if entry.get('id')==ident),ident),
                        'section':field['section_title'],'category':field['category'],'rank':candidate.get('rank') if type(candidate.get('rank')) is int else len(candidates)+1,
                        'reason':str(candidate.get('reason') or '')[:600],'score':score,'score_kind':kind})
            photo_matches[str(pid)]={'status':status,'reason':reason,'display_name':display_names.get(str(pid),''),
                'candidates':candidates,'requires_qa':True}
    history=[{'id':event.pk,'action':event.action,'by':event.actor.get_username(),
        'time':event.created_at.isoformat(),'reason':event.reason,'details':event.payload}
        for event in revision.processing_events.filter(action__in=['qa_link','qa_display_order','qa_mapping','qa_answer']).select_related('actor').order_by('-pk')[:100]] if private else []
    counts={'total':len(ids),'assigned':len(assigned),'unassigned':len(set(ids)-assigned),
        'suggested':sum(link['state']=='ai_suggested' for link in links),
        'confirmed':sum(link['state']=='qa_confirmed' for link in links)}
    return {'links':links,'unassigned_photo_ids':[pid for pid in ids if pid not in assigned],
        'counts':counts,'display_order':order,'order_digest':signature,
        'observations':observations,'photo_matches':photo_matches,'matching_history':history}


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
