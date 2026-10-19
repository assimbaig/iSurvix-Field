"""Authoritative photo-to-field mapping, approval locks and evidence coverage."""
import hashlib
import json
from collections import defaultdict
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Checklist, PhotoPlacement, PhotoEvidence
from .template_views import require_field_editable, survey_access
from .governance_views import lock_governance, audit

GROUPS = {'Civil','Electrical','Tower',''}

def schema_digest(checklist):
    return hashlib.sha256(json.dumps(checklist.schema_snapshot,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def field_catalog(checklist):
    from .template_views import field_is_locked
    return [{'id':f['id'],'label':f['label'],'type':f['type'],'description':' '.join(f.get(key,'') for key in ('description','help_text','question','instructions') if isinstance(f.get(key,''),str)),'section_description':s.get('description',''),'group':f.get('group',s.get('group','')),'required':f.get('required',False),'section_id':s['id'],'section_title':s['title'],'locked':field_is_locked(checklist,f['id'])} for s in checklist.schema_snapshot.get('sections',[]) for f in s['fields']]

def placements(checklist):
    return PhotoPlacement.objects.filter(photo__checklist=checklist,schema_digest=schema_digest(checklist)).select_related('photo').order_by('photo_id','field_id')

def confirmed_placements(checklist):
    result=defaultdict(list)
    for item in placements(checklist).filter(status__in=['confirmed','manual']):
        result[item.field_id].append(item)
    return dict(result)

def coverage(checklist):
    confirmed=confirmed_placements(checklist)
    proposed=defaultdict(list)
    for item in placements(checklist).filter(status='proposed'):
        proposed[item.field_id].append(item.photo_id)
    slots=[]
    answers=(checklist.answer_data or {}).get('custom',{})
    schema_fields={f['id']:f for section in checklist.schema_snapshot.get('sections',[]) for f in section['fields']}
    for field in field_catalog(checklist):
        schema_field=schema_fields[field['id']]
        mandatory=field['type']=='photo' and field['required'] or schema_field.get('photo_required') is True
        if field['type'] not in {'photo','inspection'} and not mandatory:
            continue
        existing=(checklist.image_data or {}).get(field['id'],[])
        accepted=[p.photo_id for p in confirmed.get(field['id'],[])]
        answer=answers.get(field['id'])
        human_na=not mandatory and isinstance(answer,dict) and answer.get('result')=='Not applicable' and isinstance(answer.get('remarks'),str) and bool(answer['remarks'].strip())
        state='not_applicable' if human_na else 'covered' if accepted or existing else 'uncertain' if proposed[field['id']] else 'missing'
        requirements=[]
        if schema_field.get('evidence_rules'):
            from .template_service import declared_evidence_missing
            requirements=declared_evidence_missing(checklist,schema_field,confirmed.get(field['id'],[]),{})
            if requirements:
                mandatory=True
                if state=='covered':state='uncertain'
        slots.append({'field_id':field['id'],'label':field['label'],'section_id':field['section_id'],'status':state,'required':bool(mandatory),'requirement':'Required photo' if mandatory else 'Recommended evidence','photo_ids':accepted,'proposed_photo_ids':proposed[field['id']],'evidence_requirements':requirements})
    return {'required':slots,'evidence_slots':slots,'required_missing_count':sum(p['required'] and p['status']!='covered' for p in slots),'recommended_missing_count':sum(not p['required'] and p['status'] in {'missing','uncertain'} for p in slots),**{state+'_count':sum(item['status']==state for item in slots) for state in ('missing','uncertain','covered','not_applicable')}}
def mapping_state(checklist):
    catalog={f['id']:f for f in field_catalog(checklist)}
    return [{'id':p.pk,'photo_id':p.photo_id,'field_id':p.field_id,'section_id':p.section_id,'label':catalog.get(p.field_id,{}).get('label',p.field_id),'status':p.status,'confidence':p.confidence,'reason':p.reason,'uncertainty':p.uncertainty,'group':p.photo.group} for p in placements(checklist)]

def record_proposals(job,photo,proposals):
    """The durable worker already validated field IDs and original vision evidence."""
    catalog={f['id']:(s['id'],f) for s in job.schema['sections'] for f in s['fields']}
    digest=schema_digest(job.checklist)
    from .photo_service import meaningful_visual_match
    current_ids={p['field_id'] for p in proposals if p.get('evidence_match')=='visible' and meaningful_visual_match(p)}
    PhotoPlacement.objects.filter(photo=photo,status='proposed').exclude(field_id__in=current_ids).update(status='superseded')
    for proposal in proposals:
        # A null answer is not a location match. Legacy/insufficient/absent drafts
        # remain draft evidence only and can never populate field photo locations.
        if proposal.get('evidence_match')!='visible' or not meaningful_visual_match(proposal):
            continue
        fid=proposal['field_id']
        section,field=catalog[fid]
        if field.get('system'):
            continue
        current=PhotoPlacement.objects.filter(photo=photo,field_id=fid).first()
        # Human corrections, rejection and confirmation always win over reruns.
        if current and current.status in {'manual','confirmed','rejected'}:
            continue
        uncertainty=proposal['uncertainty']
        PhotoPlacement.objects.update_or_create(photo=photo,field_id=fid,defaults={'job':job,'section_id':section,'status':'proposed','confidence':{'low':'high','medium':'medium','high':'low'}[uncertainty],'reason':proposal['reason']+'\nObserved: '+proposal['visual_evidence'],'uncertainty':uncertainty,'schema_digest':digest})

@transaction.atomic
def review_mappings(request,checklist_id,decisions,expected_digest):
    from django.contrib.auth.models import User
    lock_governance(request.user)
    request.user=User.objects.select_related('profile','profile__project').get(pk=request.user.pk)
    c=Checklist.objects.select_for_update().get(pk=checklist_id)
    Checklist.objects.filter(pk=c.pk).update(updated_at=c.updated_at)
    survey_access(request,c.pk,edit=True)
    if expected_digest!=schema_digest(c):
        raise ValidationError('Checklist schema changed. Reload the photo catalog.')
    if not isinstance(decisions,list) or not 1<=len(decisions)<=100:
        raise ValidationError('Review 1 to 100 photo locations per batch.')
    catalog={f['id']:f for f in field_catalog(c)}
    seen=set()
    for decision in decisions:
        if not isinstance(decision,dict) or set(decision)-{'photo_id','field_id','action','mapping_id'}:
            raise ValidationError('Invalid location review.')
        pid,fid,action=decision.get('photo_id'),decision.get('field_id'),decision.get('action')
        if type(pid)!=int or not isinstance(fid,str) or fid not in catalog or action not in {'confirm','manual','reject'} or (pid,fid) in seen:
            raise ValidationError('Invalid or repeated location review.')
        seen.add((pid,fid))
        require_field_editable(c,fid)
        field=catalog[fid]
        if any(f.get('system') for s in c.schema_snapshot['sections'] for f in s['fields'] if f['id']==fid):
            raise ValidationError('A linked system field cannot receive photo evidence.')
        photo=PhotoEvidence.objects.filter(pk=pid,checklist=c).first()
        if not photo:
            raise ValidationError('This photo is outside the survey.')
        current=PhotoPlacement.objects.select_for_update().filter(photo=photo,field_id=fid).first()
        if action in {'confirm','reject'}:
            if not current or current.pk!=decision.get('mapping_id') or (current.status!='proposed' if action=='confirm' else current.status not in {'proposed','confirmed','manual'}) or current.schema_digest!=expected_digest:
                raise ValidationError('Photo proposal changed. Reload before confirming.')
        if action=='manual':
            current=current or PhotoPlacement(photo=photo,field_id=fid)
            current.section_id=field['section_id']
            current.schema_digest=expected_digest
            current.status='manual'
            current.reason='Reviewer assigned this source photo explicitly.'
            current.confidence='high'
            current.uncertainty='low'
        else:
            current.status='confirmed' if action=='confirm' else 'rejected'
        current.reviewed_by=request.user
        current.reviewed_at=timezone.now()
        current.save()
        from .evidence_learning import capture_correction
        capture_correction(request.user,c,photo,fid,action,mapping_id=current.pk)
        audit(request.user,'photo_mapping_'+action,c.project,checklist_id=c.pk,photo_id=pid,field_id=fid,placement_id=current.pk)
    return c



def analysis_state(checklist):
    """Processing completion comes from durable jobs, even when no drafts were found."""
    from .models import PhotoJob
    source_ids=set(checklist.photo_evidence.values_list('pk',flat=True))
    analyzed=set()
    current_matching=set()
    from .photo_metadata import MATCHER_VERSION
    active=0
    for job in PhotoJob.objects.filter(checklist=checklist).prefetch_related('photos'):
        if job.schema!=checklist.schema_snapshot:
            continue
        active+=job.status in {'queued','running'}
        job_ids={p.pk for p in job.photos.all()}
        valid_ids={pid for pid in job.processed_photo_ids if type(pid)==int and pid in job_ids and pid in source_ids}
        analyzed.update(valid_ids)
        if job.progress.get('matcher_version')==MATCHER_VERSION:current_matching.update(pid for pid in job.progress.get('matched_photo_ids',[]) if type(pid)==int and pid in valid_ids)
    unprocessed=source_ids-analyzed
    pending=placements(checklist).filter(status='proposed').count()
    return {'current_matching_photo_ids':sorted(current_matching),'analyzed_photo_ids':sorted(analyzed),'unprocessed_photo_ids':sorted(unprocessed),'active_job_count':active,'pending_mapping_count':pending,'review_ready':not unprocessed and not active,'photo_count':len(source_ids)}


def metadata_workflow(checklist,photos,metadata_ready,analysis,jobs):
    """A photo location is never an answer or an engineering approval."""
    source_ids={photo.pk for photo in photos}
    states=list(placements(checklist).values('photo_id','status'))
    proposed=defaultdict(int)
    accepted=set()
    counts={status:0 for status in ['proposed','confirmed','manual','rejected']}
    for row in states:
        status=row['status']
        if status in counts:counts[status]+=1
        if status=='proposed':proposed[row['photo_id']]+=1
        if status in {'confirmed','manual'}:accepted.add(row['photo_id'])
    analyzed=set(analysis['analyzed_photo_ids'])
    unmatched=sorted(analyzed-source_ids.intersection(accepted)-set(proposed))
    review=sorted((set(proposed)|set(unmatched))&source_ids)
    multiple=sorted(pid for pid,count in proposed.items() if count>1)
    ready_count=sum(bool(metadata_ready.get(pid)) for pid in source_ids)
    active=[job for job in jobs if job['status'] in {'queued','running'} and job.get('current_schema',True)]
    if not source_ids:stage='awaiting_upload'
    elif active:
        current=next((job for job in active if job['status']=='running'),None)
        stage='pending_analysis' if not current else 'matching_checklist' if current.get('progress',{}).get('stage')=='matching_checklist' else 'extracting_metadata'
    elif analysis['unprocessed_photo_ids'] or ready_count<len(source_ids):stage='pending_analysis'
    elif review:stage='awaiting_confirmation'
    else:stage='photo_locations_reviewed'
    labels={'awaiting_upload':'Add source photos','pending_analysis':'Extract metadata and match checklist points','extracting_metadata':'Extracting image metadata','matching_checklist':'Matching metadata to checklist points','awaiting_confirmation':'Review and confirm photo locations','photo_locations_reviewed':'Photo locations reviewed'}
    return {'metadata_ready_photo_ids':sorted(pid for pid in source_ids if metadata_ready.get(pid)),'rematch_recommended_photo_ids':sorted(pid for pid in source_ids if metadata_ready.get(pid) and pid not in analysis.get('current_matching_photo_ids',[])),'stage':stage,'label':labels[stage],'metadata_ready_count':ready_count,'metadata_pending_count':len(source_ids)-ready_count,'matched_photo_count':len((set(proposed)|accepted)&source_ids),'unmatched_photo_ids':unmatched,'multiple_proposal_photo_ids':multiple,'review_photo_ids':review,'proposed_mapping_count':counts['proposed'],'confirmed_mapping_count':counts['confirmed'],'manual_mapping_count':counts['manual'],'rejected_mapping_count':counts['rejected'],'requires_confirmation':True}
