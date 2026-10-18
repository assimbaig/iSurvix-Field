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
    return [{'id':f['id'],'label':f['label'],'type':f['type'],'required':f.get('required',False),'section_id':s['id'],'section_title':s['title'],'locked':field_is_locked(checklist,f['id'])} for s in checklist.schema_snapshot.get('sections',[]) for f in s['fields']]

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
        slots.append({'field_id':field['id'],'label':field['label'],'section_id':field['section_id'],'status':state,'required':bool(mandatory),'requirement':'Required photo' if mandatory else 'Recommended evidence','photo_ids':accepted,'proposed_photo_ids':proposed[field['id']]})
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
        audit(request.user,'photo_mapping_'+action,c.project,checklist_id=c.pk,photo_id=pid,field_id=fid,placement_id=current.pk)
    return c



def analysis_state(checklist):
    """Processing completion comes from durable jobs, even when no drafts were found."""
    from .models import PhotoJob
    source_ids=set(checklist.photo_evidence.values_list('pk',flat=True))
    analyzed=set()
    active=0
    for job in PhotoJob.objects.filter(checklist=checklist).prefetch_related('photos'):
        if job.schema!=checklist.schema_snapshot:
            continue
        active+=job.status in {'queued','running'}
        job_ids={p.pk for p in job.photos.all()}
        analyzed.update(pid for pid in job.processed_photo_ids if type(pid)==int and pid in job_ids and pid in source_ids)
    unprocessed=source_ids-analyzed
    pending=placements(checklist).filter(status='proposed').count()
    return {'analyzed_photo_ids':sorted(analyzed),'unprocessed_photo_ids':sorted(unprocessed),'active_job_count':active,'pending_mapping_count':pending,'review_ready':not unprocessed and not active,'photo_count':len(source_ids)}
