"""Authenticated, CSRF protected photo pilot endpoints."""
import json
import uuid
from copy import deepcopy
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import JsonResponse, FileResponse, HttpResponse, Http404
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

def photo_limit():
    return getattr(settings,'PHOTO_MAX_PER_SITE',500)


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


def track_survey_upload(view):
    @wraps(view)
    def tracked(request, checklist_id):
        from .survey_processing import enabled
        from .survey_upload_sessions import upload_batch
        from .access import role_for
        from .category_intake import access as capture_access
        capture=role_for(request.user)=='ENGINEER'
        c = capture_access(request,checklist_id,edit=True)[0] if capture else survey_access(request, checklist_id, edit=True)['checklist']
        if capture or enabled(c):
            with upload_batch(request, checklist_id, request.POST.get('processing_upload_token')) as session:
                request._survey_upload_token = session.token
                return view(request, checklist_id)
        return view(request, checklist_id)
    return tracked


@require_POST
@api_errors
def processing_upload_session(request, checklist_id):
    from .survey_processing import enabled, upload_session
    from .category_intake import access as capture_access
    from .access import role_for
    c,flags=capture_access(request,checklist_id)
    if not enabled(c) and role_for(request.user)!='ENGINEER' and not c.survey_upload_sessions.exists():
        return JsonResponse({'enabled': False})
    data = body(request)
    from . import survey_upload_sessions
    operation = data.get('action', 'finish' if data.get('token') else 'start')
    if operation == 'heartbeat':
        session = survey_upload_sessions.heartbeat(request, checklist_id, data.get('token'))
    elif operation == 'interrupt':
        session = survey_upload_sessions.interrupt(request, checklist_id, data.get('token'))
    elif operation in {'start', 'finish'}:
        session = upload_session(request, checklist_id, data.get('token'))
    elif operation == 'recover':
        session=survey_upload_sessions.recover(request,checklist_id,data.get('token'),data.get('reason',''))
    else:
        raise ValidationError('Unknown upload session action.')
    return JsonResponse({'enabled': True, 'token': str(session.token)})

def body(request):
    if len(request.body)>30000:
        raise ValueError('Request too large.')
    data=json.loads(request.body or b'{}')
    if not isinstance(data,dict):
        raise ValueError('Expected JSON object.')
    return data

def url(checklist, photo, variant):
    return reverse('photo_evidence', args=[checklist.pk,photo.pk,variant])


def client_photo_state(checklist):
    """Project-authorized sources and human links, without internal AI history.

    Read-only is a mutation permission, not permission to see pending inference
    proposals, cached model observations, provider details or previous answers.
    This projection is shared by the Client JSON views; internal roles keep the
    existing complete review data and source download authorization is unchanged.
    """
    from .field_photo_service import coverage, field_catalog, mapping_state, schema_digest
    photo_query=checklist.photo_evidence.select_related('uploaded_by').order_by('pk')
    from .category_intake import enabled as capture_enabled,current_revision
    if capture_enabled(checklist):
        revision=current_revision(checklist)
        photo_query=photo_query.filter(pk__in=[p['id'] for p in revision.snapshot['photos']] if revision else [])
    photos = list(photo_query)
    shared_photos = []
    for photo in photos:
        metadata = {key: photo.metadata[key] for key in
                    ('format', 'width', 'height', 'captured_at', 'modified_at') if key in photo.metadata}
        gps = photo.metadata.get('gps')
        if isinstance(gps, dict):
            metadata['gps'] = {key: gps[key] for key in ('latitude', 'longitude') if key in gps}
        shared_photos.append({'id': photo.pk, 'filename': photo.filename, 'group': photo.group,
            'uploaded_by': photo.uploaded_by.get_username() if photo.uploaded_by_id else None,
            'uploaded_at': photo.created_at.isoformat(), 'metadata': metadata,
            'metadata_ready': None, 'visual_metadata': None, 'advisories': [],
            'preview_url': url(checklist, photo, 'preview'), 'original_url': url(checklist, photo, 'original')})
    mappings = [{key: entry[key] for key in
                 ('id', 'photo_id', 'field_id', 'section_id', 'label', 'status', 'group')}
                for entry in mapping_state(checklist) if entry['status'] in {'confirmed', 'manual'}]
    allowed_photo_ids={photo.pk for photo in photos}
    mappings=[mapping for mapping in mappings if mapping['photo_id'] in allowed_photo_ids]
    shared_coverage = coverage(checklist)
    if capture_enabled(checklist) and revision:
        from .category_intake import reviewed_payload
        field_details={field['id']:(section['id'],field['label']) for section in revision.snapshot['schema'].get('sections',[]) for field in section['fields']}
        confirmed={}
        for item in reviewed_payload(revision)['checklist_items']:
            if not item.get('accepted'):continue
            ids=[]
            for source in item.get('sources',[]):
                ident=str(source.get('source_id',''))
                if ident.startswith('photo:') and ident.split(':')[1].isdigit() and int(ident.split(':')[1]) in allowed_photo_ids:ids.append(int(ident.split(':')[1]))
            confirmed[item['id']]=ids
            for ident in ids:
                section,label=field_details[item['id']]
                mappings.append({'id':'qa:'+str(revision.pk)+':'+item['id']+':'+str(ident),'photo_id':ident,'field_id':item['id'],
                    'section_id':section,'label':label,'status':'confirmed','group':next(photo.group for photo in photos if photo.pk==ident)})
        for slot in shared_coverage['required']:
            slot['photo_ids']=confirmed.get(slot['field_id'],[])
            slot['status']='covered' if slot['photo_ids'] else 'missing'
            if slot['photo_ids']:slot['evidence_requirements']=[]
    for slot in shared_coverage['required']:
        # Proposal identities and their presence are internal until a human
        # confirms a source link. Explicit saved requirements remain visible.
        if slot['status'] == 'uncertain' and not slot['photo_ids'] and not slot['evidence_requirements']:
            slot['status'] = 'missing'
        slot['proposed_photo_ids'] = []
    slots = shared_coverage['required']
    shared_coverage.update({
        'required_missing_count': sum(slot['required'] and slot['status'] != 'covered' for slot in slots),
        'recommended_missing_count': sum(not slot['required'] and slot['status'] in {'missing', 'uncertain'} for slot in slots),
        **{status + '_count': sum(slot['status'] == status for slot in slots)
           for status in ('missing', 'uncertain', 'covered', 'not_applicable')}})
    return {'evidence_analysis': None, 'analysis': None, 'max_photos': photo_limit(),
        'field_catalog': field_catalog(checklist), 'mappings': mappings, 'coverage': shared_coverage,
        'schema_digest': schema_digest(checklist), 'photos': shared_photos, 'jobs': [], 'drafts': []}


@require_GET
@api_errors
def fast_state(request,checklist_id):
    from .category_intake import deny_engineer_ai
    deny_engineer_ai(request,checklist_id)
    c=survey_access(request,checklist_id)['checklist']
    from .access import role_for
    if role_for(request.user)=='CLIENT':return JsonResponse({'enabled':False})
    from .photo_search import state as search_state,MODELS
    if not (MODELS/'manifest.json').exists():return JsonResponse({'enabled':False})
    try:page=int(request.GET.get('page','1'))
    except ValueError:raise ValueError('Invalid page.')
    response=JsonResponse(search_state(c,list(c.photo_evidence.order_by('pk')),page))
    response['Cache-Control']='private, no-store'
    return response

@require_GET
def workspace(request, checklist_id):
    from .access import role_for
    from . import category_intake as capture
    if role_for(request.user)=='ENGINEER':
        c,flags=capture.access(request,checklist_id)
        return render(request,'dashboards/engineer_capture.html',{'checklist':c,'can_edit':flags['can_edit'],
            'capture_state_url':reverse('photo_capture_state',args=[c.pk]),'capture_submit_url':reverse('photo_capture_submit',args=[c.pk]),
            'capture_category_url':reverse('photo_capture_category',args=[c.pk]),'capture_remove_url':reverse('photo_capture_remove',args=[c.pk]),
            'upload_url':reverse('photo_upload',args=[c.pk]),'upload_session_url':reverse('photo_processing_upload_session',args=[c.pk])})
    access=None
    if role_for(request.user) in {'QUALITY_ENGINEER','TEAM_LEAD'}:
        checklist,_=capture.access(request,checklist_id)
    else:
        access=survey_access(request,checklist_id)
        checklist=access['checklist']
    qa_context={}
    if role_for(request.user)=='QUALITY_ENGINEER':
        from .review_route_service import route_context
        routed=route_context(request.user,checklist)
        qa_context={'is_quality_engineer':True,'review_route':routed,
            'qa_quick_review':capture.enabled(checklist),
            'qa_decision_return_to':reverse('photo_workspace',args=[checklist.pk])+'?qa_step=decision',
            'qa_legacy_fallback':not capture.enabled(checklist) or not routed,
            'qa_legacy_decision_url':reverse('roadmap_activity' if checklist.governance_mode=='independent' else 'custom_checklist',args=[checklist.pk]),
            'qa_history_url':reverse('roadmap_activity',args=[checklist.pk])+'#review-submissions',
            'qa_report_url':reverse('custom_checklist_download',args=[checklist.pk])}
    if capture.enabled(checklist) and role_for(request.user) in {'QUALITY_ENGINEER','TEAM_LEAD'}:
        capture.access(request,checklist_id)
        return render(request,'dashboards/qa_evidence_review.html',{'checklist':checklist,
            'review_state_url':reverse('photo_capture_review_state',args=[checklist.pk]),
            'review_action_url':reverse('photo_capture_review_action',args=[checklist.pk]),
            'qa_approval_url':reverse('custom_checklist',args=[checklist.pk]),
            'evidence_role_title':'Team Lead evidence review' if role_for(request.user)=='TEAM_LEAD' else 'QA evidence review',
            'evidence_review_role':role_for(request.user),
            'decision_label':'Team Lead decision & workflow' if role_for(request.user)=='TEAM_LEAD' else 'QA decision & workflow',**qa_context})
    if access is None:
        access=survey_access(request,checklist_id)
        checklist=access['checklist']
    from .field_intake_service import site_information_fields
    from .access import role_for
    from .survey_processing import enabled
    internal=role_for(request.user) in {'ENGINEER','QUALITY_ENGINEER','TEAM_LEAD'}
    client=role_for(request.user)=='CLIENT'
    return render(request,'dashboards/photo_workspace.html',{'client_evidence_view':client,'checklist_processing_enabled':enabled(checklist),'can_use_evidence_learning':internal,'evidence_learning_url':reverse('evidence_learning',args=[checklist.pk]),'site_info_fields':site_information_fields(checklist),'site_info_save_url':reverse('checklist_site_information',args=[checklist.pk]),'site_info_updated_at':checklist.updated_at.isoformat(),'checklist':checklist,'can_process_photos':access['can_edit'],'photos':checklist.photo_evidence.all(),'jobs':checklist.photo_jobs.none() if client else checklist.photo_jobs.all(),'drafts':PhotoDraft.objects.none() if client else PhotoDraft.objects.filter(job__checklist=checklist),'surveys':allowed_surveys(request).select_related('project').order_by('project__name','site_id','pk'),'model':'' if client else settings.OLLAMA_MODEL,**qa_context})

@require_GET
@api_errors
def state(request, checklist_id):
    access=survey_access(request,checklist_id)
    c=access['checklist']
    from .access import role_for
    from .category_intake import state as capture_state
    if role_for(request.user)=='ENGINEER':return JsonResponse(capture_state(request,checklist_id))
    if role_for(request.user)=='CLIENT':
        response=JsonResponse(client_photo_state(c))
        response['Cache-Control']='private, no-store'
        return response
    from .field_photo_service import field_catalog,mapping_state,coverage,schema_digest,analysis_state,metadata_workflow
    from .photo_metadata import metadata_is_current
    photos=list(c.photo_evidence.select_related('uploaded_by').order_by('pk'))
    ready={p.pk:metadata_is_current(p,settings.OLLAMA_MODEL) for p in photos}
    analysis={**analysis_state(c),'metadata_ready_count':sum(ready.values())}
    jobs=[{'current_schema':job.schema==c.schema_snapshot,**{key:getattr(job,key) for key in ('id','status','error','completed','total','attempts','progress')},'photo_ids':[photo.pk for photo in job.photos.all()]} for job in c.photo_jobs.order_by('-pk').prefetch_related('photos')]
    analysis['workflow']=metadata_workflow(c,photos,ready,analysis,jobs)
    from .evidence_pipeline import saved_state
    evidence_analysis=saved_state(c,access['can_edit'],reverse('evidence_learning',args=[c.pk]))
    return JsonResponse({'evidence_analysis':evidence_analysis,'max_photos':photo_limit(),'analysis':analysis,'field_catalog':field_catalog(c),'mappings':mapping_state(c),'coverage':coverage(c),'schema_digest':schema_digest(c),'photos':[{'id':p.pk,'filename':p.filename,'group':p.group,'uploaded_by':p.uploaded_by.get_username() if p.uploaded_by_id else None,'uploaded_at':p.created_at.isoformat(),'metadata_ready':ready[p.pk],'visual_metadata':p.analysis_metadata if ready[p.pk] else None,'preview_url':url(c,p,'preview'),'original_url':url(c,p,'original'),'metadata':p.metadata,'advisories':p.advisories} for p in photos], 'jobs':jobs, 'drafts':list(PhotoDraft.objects.filter(job__checklist=c).order_by('-pk').values('id','photo_id','field_id','label','value','reason','uncertainty','status','missing_information','anomalies'))})

@require_POST
@api_errors
@track_survey_upload
def upload(request, checklist_id):
    from .access import role_for
    from .category_intake import access as capture_access
    def authorize():
        return capture_access(request,checklist_id,edit=True)[0] if role_for(request.user)=='ENGINEER' else survey_access(request,checklist_id,edit=True)['checklist']
    authorize()
    from .field_photo_service import GROUPS
    group=request.POST.get('group','')
    if group=='General Info' or role_for(request.user)=='ENGINEER' and group not in {'Civil','Electrical','Tower'}:
        raise ValidationError('General Info contains site data. Choose Civil, Electrical or Tower for photos.')
    if group not in GROUPS:
        raise ValidationError('Choose Civil, Electrical or Tower. Older uploads without a category remain Uncategorised.')
    files=request.FILES.getlist('files')
    if not 1<=len(files)<=20:
        return error(ValueError('Submit between 1 and 20 photos per batch.'))
    stored=[]
    try:
        prepared=[(f,prepare_image(f)) for f in files]
        with transaction.atomic():
            c=Checklist.objects.select_for_update().get(pk=checklist_id)
            authorize()
            if getattr(request, '_survey_upload_token', None):
                from .survey_upload_sessions import require_batch_open
                require_batch_open(c, request._survey_upload_token)
            # Serialize SQLite writers as well as databases supporting row locks.
            Checklist.objects.filter(pk=c.pk).update(updated_at=c.updated_at)
            hashes=set(c.photo_evidence.values_list('sha256',flat=True))
            new={item[1][2] for item in prepared}-hashes
            count=PhotoEvidence.objects.filter(checklist__project=c.project,checklist__site_id=c.site_id).count()
            if count+len(new)>photo_limit():
                raise ValidationError(f'This site already has the maximum {photo_limit()} photos.')
            ids=[]
            for f,(raw,preview,digest,metadata,advisories) in prepared:
                existing=c.photo_evidence.filter(sha256=digest).first()
                if existing:
                    excluded=list((c.intake_metadata or {}).get('category_intake_excluded',[]))
                    if existing.pk in excluded:
                        c.intake_metadata={**c.intake_metadata,'category_intake_excluded':[i for i in excluded if i!=existing.pk]}
                        c.save(update_fields=['intake_metadata','updated_at'])
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
    from .category_intake import access as capture_access
    from .access import role_for
    c=capture_access(request,checklist_id)[0] if role_for(request.user) in {'ENGINEER','QUALITY_ENGINEER','TEAM_LEAD'} else survey_access(request,checklist_id)['checklist']
    p=get_object_or_404(PhotoEvidence,pk=photo_id,checklist=c)
    from .category_intake import enabled as capture_enabled,current_revision
    from .access import role_for
    if capture_enabled(c) and role_for(request.user)=='CLIENT':
        revision=current_revision(c)
        if not revision or p.pk not in {photo['id'] for photo in revision.snapshot['photos']}:raise Http404()
    if variant not in {'original','preview'}:
        return HttpResponse(status=404)
    file=p.original if variant=='original' else p.preview
    if not file:raise Http404()
    content_type='image/jpeg' if variant=='preview' else {'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp'}.get((p.metadata or {}).get('format'),'application/octet-stream')
    response=FileResponse(file.open('rb'),content_type=content_type,as_attachment=variant=='original',filename=p.filename if variant=='original' else 'preview.jpg')
    response['Cache-Control']='private, no-store'
    response['X-Content-Type-Options']='nosniff'
    return response

@require_POST
@api_errors
def enqueue(request,checklist_id):
    from .category_intake import deny_engineer_ai
    deny_engineer_ai(request,checklist_id)
    c=survey_access(request,checklist_id,edit=True)['checklist']
    from .survey_processing import enabled
    if enabled(c):
        raise ValidationError('Submit this survey in AI Checklist & Drawings to start analysis. Uploaded originals are preserved.')
    try:
        data=body(request)
        ids=data.get('photo_ids')
        queue_when_busy=data.get('queue_when_busy',False)
        adopt=data.get('apply_current_rules',False)
        if type(adopt) is not bool:
            raise ValueError('apply_current_rules must be a boolean.')
        if type(queue_when_busy)!=bool:
            raise ValueError('queue_when_busy must be a boolean.')
        if not isinstance(ids,list) or not 1<=len(ids)<=photo_limit() or any(type(i)!=int for i in ids) or len(set(ids))!=len(ids):
            raise ValueError(f'Choose 1 to {photo_limit()} distinct photos.')
        photos=list(c.photo_evidence.filter(pk__in=ids))
        if len(photos)!=len(ids):
            raise ValueError('A photo is outside this survey.')
        model=data.get('model') or settings.OLLAMA_MODEL
        if not isinstance(model,str) or len(model)>160:
            raise ValueError('Invalid model.')
        verify_vision(model)
        from .evidence_pipeline import processing_context
        context=processing_context(c,model,adopt=adopt)
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
            job=PhotoJob.objects.create(checklist=c,requested_by=request.user,model=model,total=len(photos),baseline=deepcopy((c.answer_data or {}).get('custom',{})),schema=deepcopy(c.schema_snapshot),progress={'evidence_context':context})
            job.photos.set(photos)
        return JsonResponse({'id':job.pk,'status':job.status},status=201)
    except ValidationError as exc:
        return error(exc,409)
    except (ValueError,OSError) as exc:
        return error(ValueError('Local model unavailable or invalid photo request. Check vision support and retry.'))

@require_POST
@api_errors
def retry(request,checklist_id,job_id):
    from .category_intake import deny_engineer_ai
    deny_engineer_ai(request,checklist_id)
    access=survey_access(request,checklist_id,edit=True)
    from .survey_processing import enabled
    if enabled(access['checklist']):
        raise ValidationError('Submit this survey in AI Checklist & Drawings to start analysis. Retry its saved survey revision there; uploaded originals are preserved.')
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
    from .category_intake import deny_engineer_ai
    deny_engineer_ai(request,checklist_id)
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
@api_errors
def report(request,checklist_id):
    from .category_intake import deny_engineer_ai
    deny_engineer_ai(request,checklist_id)
    c=survey_access(request,checklist_id)['checklist']
    from .access import role_for
    if role_for(request.user)=='CLIENT':
        shared=client_photo_state(c)
        source_rows={photo.pk:photo for photo in c.photo_evidence.all()}
        response=JsonResponse({'evidence_analysis':None,'placements':shared['mappings'],
            'coverage':shared['coverage'],'notice':'Shared source evidence and human-confirmed links. Checklist decisions are recorded separately.',
            'site_id':c.site_id,'checklist_id':c.pk,
            'template_revision':{'id':c.checklist_template_id,'version':c.checklist_template.version if c.checklist_template_id else None,
                                 'family_id':str(c.checklist_template.family_id) if c.checklist_template_id else None},
            'jobs':[],'drafts':[],'audit':[],
            'evidence':[{'id':photo['id'],'filename':photo['filename'],'sha256':source_rows[photo['id']].sha256,
                         'group':photo['group'],'metadata':photo['metadata'],
                         'uploaded_by_id':source_rows[photo['id']].uploaded_by_id,
                         'created_at':photo['uploaded_at'],'source':photo['original_url']} for photo in shared['photos']]},
            json_dumps_params={'indent':2})
        response['Content-Disposition']='attachment; filename="photo-evidence-report.json"'
        response['Cache-Control']='private, no-store'
        return response
    from .field_photo_service import mapping_state,coverage
    response=JsonResponse({'evidence_analysis':__import__('core.evidence_pipeline',fromlist=['saved_state']).saved_state(c),'placements':mapping_state(c),'coverage':coverage(c),'notice':'Draft evidence only. No engineering certification. Absence of detections is not a pass.','site_id':c.site_id,'checklist_id':c.pk,'template_revision':{'id':c.checklist_template_id,'version':c.checklist_template.version if c.checklist_template_id else None,'family_id':str(c.checklist_template.family_id) if c.checklist_template_id else None},'jobs':list(c.photo_jobs.values('id','model','status','requested_by_id','created_at','updated_at','attempts','completed','total','schema')),'drafts':list(PhotoDraft.objects.filter(job__checklist=c).values('id','job_id','photo_id','field_id','label','value','reason','uncertainty','missing_information','anomalies','status','accepted_by_id','accepted_at','baseline','baseline_present')),'evidence':[{'id':p.pk,'filename':p.filename,'sha256':p.sha256,'group':p.group,'metadata':p.metadata,'uploaded_by_id':p.uploaded_by_id,'created_at':p.created_at,'source':url(c,p,'original')} for p in c.photo_evidence.all()],'audit':c.review_history},json_dumps_params={'indent':2})
    response['Content-Disposition']='attachment; filename="photo-evidence-report.json"'
    response['Cache-Control']='private, no-store'
    return response

@require_POST
@api_errors
def mapping(request,checklist_id):
    from .category_intake import deny_engineer_ai
    deny_engineer_ai(request,checklist_id)
    survey_access(request,checklist_id,edit=True)
    from .field_photo_service import review_mappings,coverage
    data=body(request)
    c=review_mappings(request,checklist_id,data.get('decisions'),data.get('expected_schema_digest'))
    return JsonResponse({'status':'saved','coverage':coverage(c)})
