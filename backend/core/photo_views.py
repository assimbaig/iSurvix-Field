"""Authenticated, CSRF protected photo pilot endpoints."""
import json
import uuid
from copy import deepcopy
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import JsonResponse, FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from functools import wraps
from .models import Checklist, PhotoEvidence, PhotoJob, PhotoDraft
from .template_views import survey_access, require_field_editable
from .template_service import field_map
from .local_ai import allowed_surveys
from .photo_service import prepare_image, verify_vision, validate_drafts

def api_errors(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except ValidationError as exc:
            return error(exc, 409)
        except (ValueError, TypeError) as exc:
            return error(ValueError('Invalid request.'), 400)
        except (OSError, TimeoutError):
            return error(ValueError('Local storage or model unavailable. Retry after checking the local service.'), 503)
    return wrapped

def error(exc, status=400):
    return JsonResponse({'error': '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)}, status=status)

def body(request):
    if len(request.body)>30000:
        raise ValueError('Request too large.')
    data=json.loads(request.body or b'{}')
    if not isinstance(data,dict):
        raise ValueError('Expected JSON object.')
    return data

def url(checklist, photo, variant):
    return reverse('photo_evidence', args=[checklist.pk,photo.pk,variant])

@require_GET
def workspace(request, checklist_id):
    access=survey_access(request,checklist_id)
    checklist=access['checklist']
    from .field_intake_service import site_information_fields
    return render(request,'dashboards/photo_workspace.html',{'site_info_fields':site_information_fields(checklist),'site_info_save_url':reverse('checklist_site_information',args=[checklist.pk]),'site_info_updated_at':checklist.updated_at.isoformat(),'checklist':checklist,'can_process_photos':access['can_edit'],'photos':checklist.photo_evidence.all(),'jobs':checklist.photo_jobs.all(),'drafts':PhotoDraft.objects.filter(job__checklist=checklist),'surveys':allowed_surveys(request).select_related('project').order_by('project__name','site_id','pk'),'model':settings.OLLAMA_MODEL})

@require_GET
def state(request, checklist_id):
    c=survey_access(request,checklist_id)['checklist']
    from .field_photo_service import field_catalog,mapping_state,coverage,schema_digest,analysis_state
    from .photo_metadata import metadata_is_current
    photos=list(c.photo_evidence.order_by('pk'))
    ready={p.pk:metadata_is_current(p,settings.OLLAMA_MODEL) for p in photos}
    analysis={**analysis_state(c),'metadata_ready_count':sum(ready.values())}
    jobs=[{**{key:getattr(job,key) for key in ('id','status','error','completed','total','attempts','progress')},'photo_ids':[photo.pk for photo in job.photos.all()]} for job in c.photo_jobs.order_by('-pk').prefetch_related('photos')]
    return JsonResponse({'max_photos':400,'analysis':analysis,'field_catalog':field_catalog(c),'mappings':mapping_state(c),'coverage':coverage(c),'schema_digest':schema_digest(c),'photos':[{'id':p.pk,'filename':p.filename,'group':p.group,'metadata_ready':ready[p.pk],'visual_metadata':p.analysis_metadata if ready[p.pk] else None,'preview_url':url(c,p,'preview'),'original_url':url(c,p,'original'),'metadata':p.metadata,'advisories':p.advisories} for p in photos], 'jobs':jobs, 'drafts':list(PhotoDraft.objects.filter(job__checklist=c).order_by('-pk').values('id','photo_id','field_id','label','value','reason','uncertainty','status','missing_information','anomalies'))})

@require_POST
@api_errors
def upload(request, checklist_id):
    survey_access(request,checklist_id,edit=True)
    from .field_photo_service import GROUPS
    group=request.POST.get('group','')
    if group not in GROUPS:
        raise ValidationError('Choose Civil, Electrical or Tower for the upload group.')
    files=request.FILES.getlist('files')
    if not 1<=len(files)<=20:
        return error(ValueError('Submit between 1 and 20 photos per batch.'))
    stored=[]
    try:
        prepared=[(f,prepare_image(f)) for f in files]
        with transaction.atomic():
            c=Checklist.objects.select_for_update().get(pk=checklist_id)
            survey_access(request,checklist_id,edit=True)
            # Serialize SQLite writers as well as databases supporting row locks.
            Checklist.objects.filter(pk=c.pk).update(updated_at=c.updated_at)
            hashes=set(c.photo_evidence.values_list('sha256',flat=True))
            new={item[1][2] for item in prepared}-hashes
            count=PhotoEvidence.objects.filter(checklist__project=c.project,checklist__site_id=c.site_id).count()
            if count+len(new)>400:
                raise ValidationError('This site already has the maximum 400 photos.')
            ids=[]
            for f,(raw,preview,digest,metadata,advisories) in prepared:
                existing=c.photo_evidence.filter(sha256=digest).first()
                if existing:
                    ids.append({'id':existing.pk,'duplicate':True})
                    continue
                p=PhotoEvidence(checklist=c,uploaded_by=request.user,filename=f.name[:255],group=group,sha256=digest,metadata=metadata,advisories=advisories)
                p.original.save(uuid.uuid4().hex+'.bin',ContentFile(raw),save=False)
                stored.append(p.original)
                p.preview.save(uuid.uuid4().hex+'.jpg',ContentFile(preview),save=False)
                stored.append(p.preview)
                p.save()
                ids.append({'id':p.pk,'duplicate':False})
        return JsonResponse({'photos':ids},status=201)
    except Exception as exc:
        for file in stored:
            file.delete(save=False)
        if isinstance(exc, (ValidationError, ValueError)):
            return error(exc, 400)
        raise

@require_GET
def evidence(request,checklist_id,photo_id,variant):
    c=survey_access(request,checklist_id)['checklist']
    p=get_object_or_404(PhotoEvidence,pk=photo_id,checklist=c)
    if variant not in {'original','preview'}:
        return HttpResponse(status=404)
    file=p.original if variant=='original' else p.preview
    response=FileResponse(file.open('rb'),content_type='image/jpeg' if variant=='preview' else {'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp'}[p.metadata['format']],as_attachment=variant=='original',filename=p.filename if variant=='original' else 'preview.jpg')
    response['Cache-Control']='private, no-store'
    response['X-Content-Type-Options']='nosniff'
    return response

@require_POST
@api_errors
def enqueue(request,checklist_id):
    c=survey_access(request,checklist_id,edit=True)['checklist']
    try:
        data=body(request)
        ids=data.get('photo_ids')
        queue_when_busy=data.get('queue_when_busy',False)
        if type(queue_when_busy)!=bool:
            raise ValueError('queue_when_busy must be a boolean.')
        if not isinstance(ids,list) or not 1<=len(ids)<=400 or any(type(i)!=int for i in ids) or len(set(ids))!=len(ids):
            raise ValueError('Choose 1 to 400 distinct photos.')
        photos=list(c.photo_evidence.filter(pk__in=ids))
        if len(photos)!=len(ids):
            raise ValueError('A photo is outside this survey.')
        model=data.get('model') or settings.OLLAMA_MODEL
        if not isinstance(model,str) or len(model)>160:
            raise ValueError('Invalid model.')
        verify_vision(model)
        with transaction.atomic():
            c=Checklist.objects.select_for_update().get(pk=c.pk)
            survey_access(request,c.pk,edit=True)
            Checklist.objects.filter(pk=c.pk).update(updated_at=c.updated_at)
            active=c.photo_jobs.filter(status__in=['queued','running'])
            if active.exists() and not queue_when_busy:
                return error(ValueError('A photo job is already active for this survey.'),409)
            if active.count()>=10:
                return error(ValueError('This survey already has 10 pending photo jobs. Wait for processing before queuing more.'),409)
            if active.filter(photos__pk__in=ids).exists():
                return error(ValueError('One or more selected photos are already queued or processing.'),409)
            job=PhotoJob.objects.create(checklist=c,requested_by=request.user,model=model,total=len(photos),baseline=deepcopy((c.answer_data or {}).get('custom',{})),schema=deepcopy(c.schema_snapshot))
            job.photos.set(photos)
        return JsonResponse({'id':job.pk,'status':job.status},status=201)
    except (ValueError,ValidationError,OSError) as exc:
        return error(ValueError('Local model unavailable or invalid photo request. Check vision support and retry.'))

@require_POST
@api_errors
def retry(request,checklist_id,job_id):
    survey_access(request,checklist_id,edit=True)
    with transaction.atomic():
        c=Checklist.objects.select_for_update().get(pk=checklist_id)
        Checklist.objects.filter(pk=c.pk).update(updated_at=c.updated_at)
        survey_access(request,checklist_id,edit=True)
        job=get_object_or_404(PhotoJob.objects.select_for_update(),pk=job_id,checklist_id=checklist_id)
        if c.photo_jobs.exclude(pk=job.pk).filter(status__in=['queued','running']).exists():
            return error(ValueError('A photo job is already active for this survey.'),409)
        if job.status!='failed':
            return error(ValueError('Only failed jobs can be retried.'),409)
        # Reuse the original baseline so retry cannot legitimize stale evidence.
        job.status='queued'
        job.error=''
        job.save(update_fields=['status','error','updated_at'])
    return JsonResponse({'id':job.pk,'status':job.status})

@require_POST
@api_errors
def accept(request,checklist_id,draft_id):
    survey_access(request,checklist_id,edit=True)
    try:
        with transaction.atomic():
            c=Checklist.objects.select_for_update().get(pk=checklist_id)
            Checklist.objects.filter(pk=c.pk).update(updated_at=c.updated_at)
            survey_access(request,checklist_id,edit=True)
            draft=get_object_or_404(PhotoDraft.objects.select_for_update(),pk=draft_id,job__checklist=c)
            if draft.status!='pending' or draft.value is None:
                raise ValidationError('This draft has no pending answer to accept.')
            if c.schema_snapshot!=draft.job.schema:
                raise ValidationError('Checklist schema changed; analyze the evidence again.')
            field=field_map(c).get(draft.field_id)
            if not field or field.get('system'):
                raise ValidationError('This field cannot be updated by a photo draft.')
            require_field_editable(c,draft.field_id)
            validate_drafts({'drafts':[{'field_id':draft.field_id,'value':draft.value,'reason':draft.reason,'uncertainty':draft.uncertainty,'missing_information':draft.missing_information,'anomalies':draft.anomalies}]},[field])
            answers=deepcopy(c.answer_data or {})
            custom=answers.setdefault('custom',{})
            if (draft.field_id in custom)!=draft.baseline_present or custom.get(draft.field_id)!=draft.baseline:
                return error(ValueError('Answer changed since analysis. Review a new draft.'),409)
            custom[draft.field_id]=draft.value
            c.answer_data=answers
            c.review_history=[*c.review_history,{'action':'accept_photo_draft','draft_id':draft.pk,'photo_id':draft.photo_id,'field_id':draft.field_id,'by':request.user.pk,'name':request.user.username,'time':timezone.now().isoformat(),'previous':draft.baseline,'value':draft.value}]
            c.save(update_fields=['answer_data','review_history','updated_at'])
            draft.status='accepted'
            draft.accepted_by=request.user
            draft.accepted_at=timezone.now()
            draft.save(update_fields=['status','accepted_by','accepted_at'])
            from .governance_views import audit
            audit(request.user,'photo_draft_accepted',c.project,checklist_id=c.pk,draft_id=draft.pk,photo_id=draft.photo_id,field_id=draft.field_id)
        return JsonResponse({'status':'accepted'})
    except ValidationError as exc:
        return error(exc,409)

@require_GET
def report(request,checklist_id):
    c=survey_access(request,checklist_id)['checklist']
    from .field_photo_service import mapping_state,coverage
    response=JsonResponse({'placements':mapping_state(c),'coverage':coverage(c),'notice':'Draft evidence only. No engineering certification. Absence of detections is not a pass.','site_id':c.site_id,'checklist_id':c.pk,'template_revision':{'id':c.checklist_template_id,'version':c.checklist_template.version if c.checklist_template_id else None,'family_id':str(c.checklist_template.family_id) if c.checklist_template_id else None},'jobs':list(c.photo_jobs.values('id','model','status','requested_by_id','created_at','updated_at','attempts','completed','total','schema')),'drafts':list(PhotoDraft.objects.filter(job__checklist=c).values('id','job_id','photo_id','field_id','label','value','reason','uncertainty','missing_information','anomalies','status','accepted_by_id','accepted_at','baseline','baseline_present')),'evidence':[{'id':p.pk,'filename':p.filename,'sha256':p.sha256,'group':p.group,'metadata':p.metadata,'uploaded_by_id':p.uploaded_by_id,'created_at':p.created_at,'source':url(c,p,'original')} for p in c.photo_evidence.all()],'audit':c.review_history},json_dumps_params={'indent':2})
    response['Content-Disposition']='attachment; filename="photo-evidence-report.json"'
    response['Cache-Control']='private, no-store'
    return response

@require_POST
@api_errors
def mapping(request,checklist_id):
    survey_access(request,checklist_id,edit=True)
    from .field_photo_service import review_mappings,coverage
    data=body(request)
    c=review_mappings(request,checklist_id,data.get('decisions'),data.get('expected_schema_digest'))
    return JsonResponse({'status':'saved','coverage':coverage(c)})
