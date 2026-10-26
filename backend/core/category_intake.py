"""Category evidence intake and QA-owned derived review, using existing records.

Engineer source snapshots never contain QA edits. Human QA decisions are an
append-only overlay, and late inference cannot replace a completed QA package.
"""
from copy import deepcopy, copy
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError,transaction
from django.db.models import Max
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from .access import can_access_project, role_for
from .models import Checklist, Profile, PhotoEvidence, WorkAssignment
from .survey_processing_models import (SurveyProcessingRevision, SurveyProcessingJob,
    SurveyProcessingEvent, SurveyProcessingResult)

VERSION = 1
CATEGORIES = [{'value': 'Civil', 'label': 'Civil'}, {'value': 'Electrical', 'label': 'Electrical'},
              {'value': 'Tower', 'label': 'Tower'}]
CONTROL_KEYS = {'category_intake_version', 'category_intake_cycle', 'category_intake_revision', 'category_intake_excluded'}


def enabled(c):
    return (c.intake_metadata or {}).get('category_intake_version') == VERSION


def revision_enabled(revision):
    return revision.snapshot.get('category_intake_version') == VERSION


def deny_engineer_ai(request,checklist_id):
    if role_for(request.user)==Profile.Roles.ENGINEER:
        access(request,checklist_id)
        raise PermissionDenied('Checklist matching and AI decisions belong to the assigned QA Engineer. Upload site photos and submit them to QA.')


def qa_id(c):
    policy = getattr(c, 'review_policy', None)
    return policy.l2_reviewer_id if c.governance_mode == 'independent' and policy else c.quality_reviewer_id


def access(request, checklist_id, edit=False, quality=False):
    actor = request.user
    if not actor.is_authenticated:
        raise Http404()
    actor = User.objects.select_related('profile').get(pk=actor.pk)
    request.user = actor
    c = get_object_or_404(Checklist.objects.select_related('project__company', 'checklist_template', 'quality_reviewer'), pk=checklist_id)
    if not actor.is_active or actor.profile.is_locked or not can_access_project(actor, c.project_id):
        raise Http404()
    role = role_for(actor)
    owner = role == Profile.Roles.ENGINEER and c.user_id == actor.pk
    if role==Profile.Roles.ENGINEER and not owner:raise Http404()
    assigned_qa = role == Profile.Roles.QUALITY_ENGINEER and qa_id(c) == actor.pk
    if role==Profile.Roles.QUALITY_ENGINEER and not assigned_qa:raise Http404()
    if c.governance_mode == 'independent':
        from .independent_workflow import assigned_site_access
        if not assigned_site_access(actor,c): raise Http404()
    if not (owner or assigned_qa or role in {Profile.Roles.ADMIN, Profile.Roles.TEAM_LEAD,Profile.Roles.CLIENT}):
        raise PermissionDenied('Use the assigned project evidence workspace.')
    if role==Profile.Roles.CLIENT:
        from .template_views import survey_access
        survey_access(request,c.pk)
    from .review_route_service import route_for
    route = route_for(c) if c.governance_mode == 'independent' else None
    editable = owner and c.status in {Checklist.Status.DRAFT, Checklist.Status.REJECTED} and (not route or route.stage == 'engineer')
    qa_editable = assigned_qa and enabled(c) and c.status in {Checklist.Status.SUBMITTED, Checklist.Status.REVIEW} and (not route or route.stage == 'quality_engineer')
    if edit and not editable:
        raise PermissionDenied('Only the assigned Engineer may change evidence before submission or after return.')
    if quality and not qa_editable:
        raise PermissionDenied('Only the assigned QA Engineer may review this evidence at the current stage.')
    return c, {'can_edit': bool(editable), 'can_submit': bool(editable), 'can_review': bool(qa_editable), 'owner': owner}


def source_snapshot(c):
    from . import survey_processing as pipeline
    snapshot = pipeline.freeze_data(c, category=False)
    excluded = set((c.intake_metadata or {}).get('category_intake_excluded', []))
    groups = dict(c.photo_evidence.values_list('pk','group'))
    snapshot['photos'] = [{**photo, 'group': groups[photo['id']]}
                          for photo in snapshot['photos'] if photo['id'] not in excluded]
    from .engineer_documents import snapshot as document_snapshot
    snapshot['documents']=document_snapshot(c,snapshot['documents'])
    snapshot['intake'] = {key: value for key, value in snapshot['intake'].items() if key not in CONTROL_KEYS}
    from .engineer_general_info import CONTEXT_KEY,CONTEXT_VERSION
    context=snapshot['intake'].get(CONTEXT_KEY,{})
    if isinstance(context,dict) and context.get('version')==CONTEXT_VERSION:
        snapshot['project']=context.get('project',snapshot['project'])
        snapshot['company']=context.get('company',snapshot['company'])
    snapshot['category_intake_version'] = VERSION
    snapshot['category_intake_cycle'] = (c.intake_metadata or {}).get('category_intake_cycle', 0)
    return snapshot


def current_revision(c):
    ident = (c.intake_metadata or {}).get('category_intake_revision')
    return c.processing_revisions.filter(pk=ident).select_related('processing_job').first() if ident else None


def configuration_error(c):
    template = c.checklist_template
    if not template or not template.published or template.disabled or not c.schema_snapshot.get('sections'):
        return 'QA configuration required: assign an approved checklist template. Uploaded evidence is preserved.'
    allowed = {field['id']: field for section in template.definition.get('sections', []) for field in section.get('fields', [])}
    for section in c.schema_snapshot.get('sections', []):
        for field in section.get('fields', []):
            if field['id'] not in allowed or field != allowed[field['id']]:
                return 'QA configuration required: the saved checklist does not match its approved revision.'
    return ''


def photos(snapshot, c):
    import math
    result=[]
    for photo in snapshot['photos']:
        recorded=photo.get('metadata')
        recorded=recorded if isinstance(recorded,dict) else {}
        metadata={}
        captured=recorded.get('captured_at')
        if isinstance(captured,str) and captured.strip():metadata['captured_at']=captured
        gps=recorded.get('gps')
        if isinstance(gps,dict):
            lat,lon=gps.get('latitude'),gps.get('longitude')
            if (type(lat) in (int,float) and type(lon) in (int,float)
                    and -90<=lat<=90 and -180<=lon<=180
                    and math.isfinite(lat) and math.isfinite(lon)):
                metadata['gps']={'latitude':lat,'longitude':lon}
        result.append({'id':photo['id'],'filename':photo['filename'],'group':photo.get('group',''),
            'metadata':metadata,
            'preview_url':reverse('photo_evidence',args=[c.pk,photo['id'],'preview']),
            'original_url':reverse('photo_evidence',args=[c.pk,photo['id'],'original'])})
    return result


def state(request, checklist_id):
    from . import survey_processing as pipeline, survey_upload_sessions as uploads
    c, flags = access(request, checklist_id)
    if role_for(request.user)==Profile.Roles.CLIENT:
        raise PermissionDenied('Use the shared QA-reviewed evidence view for this activity.')
    snapshot = source_snapshot(c)
    revision = current_revision(c)
    job = revision.processing_job if revision else None
    info = (c.intake_metadata or {}).get('site_information', {})
    if not isinstance(info, dict): info = {}
    qa = User.objects.filter(pk=qa_id(c)).first()
    from .review_route_service import route_for
    route = route_for(c) if c.governance_mode == 'independent' else None
    correction_reason=''
    if flags['can_edit'] and c.status==Checklist.Status.REJECTED:
        returned=route.events.filter(to_stage='engineer',action__in=['reject','return']).order_by('-sequence').first() if route else None
        correction_reason=returned.reason if returned else c.comment or ''
    from .engineer_general_info import describe as general_information
    from .engineer_documents import rows as document_rows,limits as document_limits
    return {'site_id': c.site_id, 'project': c.project.name,
        'general_information':general_information(c,flags,revision),
        'site_info': {key: info.get(key, '') for key in ('site_name', 'address', 'city', 'region')},
        'photos': photos(snapshot, c), 'categories': CATEGORIES, **flags,
        'documents':document_rows(snapshot,c),'document_upload':document_limits(),
        'submitted': c.status not in {Checklist.Status.DRAFT, Checklist.Status.REJECTED},
        'stage': route.stage if route else 'quality_engineer' if c.status in {Checklist.Status.SUBMITTED, Checklist.Status.REVIEW} else 'engineer',
        'qa_name': (qa.get_full_name() or qa.get_username()) if qa else '',
        'correction_reason':correction_reason,
        'ai': ({'status': job.status, 'completed': job.completed, 'total': job.total, 'error': job.error} if job else
            {'status': 'not_submitted', 'completed': 0, 'total': 0, 'error': ''}) if role_for(request.user)==Profile.Roles.QUALITY_ENGINEER else
            {'status':'submitted' if revision else 'not_submitted'},
        'digest': pipeline.digest(snapshot), 'config_error': configuration_error(c),
        'upload_state': uploads.state(request, c, flags)}


def _same_source(c, expected):
    from .survey_processing import digest
    if not expected or expected != digest(source_snapshot(c)):
        raise ValidationError('The evidence changed. Refresh the saved photos before submitting or changing a category.')


@transaction.atomic
def move_or_remove(request, checklist_id, data, remove=False):
    Checklist.objects.select_for_update().get(pk=checklist_id)
    c, flags = access(request, checklist_id, edit=True)
    _same_source(c, data.get('expected_digest'))
    from .governance_views import audit
    if remove:
        photo = get_object_or_404(c.photo_evidence, pk=data.get('photo_id'))
        # Retain the source row and original bytes for every historical revision.
        excluded = list((c.intake_metadata or {}).get('category_intake_excluded', []))
        if photo.pk not in excluded: excluded.append(photo.pk)
        c.intake_metadata = {**(c.intake_metadata or {}), 'category_intake_excluded': excluded}
        c.save(update_fields=['intake_metadata', 'updated_at'])
        audit(request.user,'capture_photo_removed',c.project,checklist_id=c.pk,photo_id=photo.pk)
        return state(request,checklist_id)
    if 'photo_ids' in data:
        if 'photo_id' in data:raise ValidationError('Choose photo_ids or photo_id, not both.')
        requested=data['photo_ids']
    else:requested=[data.get('photo_id')]
    if not isinstance(requested,list) or not 1<=len(requested)<=1000:
        raise ValidationError('Select between 1 and 1000 saved photos for a category change.')
    if any(type(ident) is not int or ident<=0 for ident in requested):
        raise ValidationError('Select saved photos using positive integer photo IDs.')
    ids=list(dict.fromkeys(requested))
    group = data.get('group')
    if not isinstance(group,str) or group not in {category['value'] for category in CATEGORIES}:
        raise ValidationError('General Info contains site data. Choose Civil, Electrical or Tower for photos.')
    selected={photo.pk:photo for photo in c.photo_evidence.select_for_update().filter(pk__in=ids)}
    if len(selected)!=len(ids):raise Http404()
    excluded=set((c.intake_metadata or {}).get('category_intake_excluded',[]))
    if excluded.intersection(ids):raise ValidationError('Removed photos are outside the current capture. Refresh the saved photo selection.')
    changes=[{'photo_id':ident,'from_group':selected[ident].group,'to_group':group}
        for ident in ids if selected[ident].group!=group]
    if changes:
        changed_ids=[change['photo_id'] for change in changes]
        try:
            PhotoEvidence.objects.filter(checklist=c,pk__in=changed_ids).update(group=group)
            details={'checklist_id':c.pk,'photo_ids':changed_ids,'selected_photo_ids':ids,'changes':changes}
            if len(ids)==1:details['photo_id']=ids[0]
            audit(request.user,'capture_photo_category',c.project,**details)
        except DatabaseError as exc:
            raise ValidationError('Photo category changes could not be saved. Refresh the saved photos and retry.') from exc
    result=state(request,checklist_id)
    result['category_update']={'photo_ids':ids,'requested_count':len(requested),'selected_count':len(ids),
        'changed_count':len(changes),'unchanged_count':len(ids)-len(changes),
        'duplicate_count':len(requested)-len(ids),'group':group,'no_op':not changes}
    return result


def validate_handoff(c):
    from .survey_upload_sessions import require_complete
    require_complete(c)
    if not c.site_id.strip(): raise ValidationError('Record the site ID before submission.')
    if not source_snapshot(c)['photos']: raise ValidationError('Upload at least one site photo before submission.')
    from .quality_workflow import require_quality_reviewer
    reviewer = User.objects.filter(pk=qa_id(c)).first()
    require_quality_reviewer(c.project_id, reviewer, c.user_id)


@transaction.atomic
def submit(request, checklist_id, data):
    from . import survey_processing as pipeline
    Checklist.objects.select_for_update().get(pk=checklist_id)
    c, flags = access(request, checklist_id)
    if not flags['owner']: raise PermissionDenied('Only the assigned Engineer may submit site evidence.')
    if data.get('uploads_finished') is not True: raise ValidationError('Confirm that all uploads have finished.')
    existing = current_revision(c)
    if not flags['can_edit']:
        previous=existing.processing_events.filter(action='capture_submitted').last() if existing else None
        replay=previous and previous.payload.get('request_digest')==data.get('expected_digest')
        if existing and pipeline.current(existing) and (replay or data.get('expected_digest')==pipeline.digest(source_snapshot(c))):return existing, False
        raise PermissionDenied('This evidence is already submitted or approved.')
    _same_source(c, data.get('expected_digest'))
    validate_handoff(c)
    from .engineer_general_info import freeze_for_submission
    freeze_for_submission(c)
    c.intake_metadata = {**(c.intake_metadata or {}), 'category_intake_version': VERSION,
                         'category_intake_cycle': (c.intake_metadata or {}).get('category_intake_cycle', 0) + 1}
    c.save(update_fields=['intake_metadata', 'updated_at'])
    snapshot = source_snapshot(c)
    number = (c.processing_revisions.aggregate(n=Max('number'))['n'] or 0) + 1
    revision = SurveyProcessingRevision.objects.create(checklist=c, number=number, digest=pipeline.digest(snapshot), snapshot=snapshot, submitted_by=request.user)
    config = configuration_error(c)
    SurveyProcessingJob.objects.create(revision=revision, model=__import__('django.conf', fromlist=['settings']).settings.OLLAMA_MODEL,
        total=len(snapshot['photos']), status='failed' if config else 'queued', error=config)
    c.intake_metadata = {**c.intake_metadata, 'category_intake_revision': revision.pk}
    c.save(update_fields=['intake_metadata', 'updated_at'])
    SurveyProcessingEvent.objects.create(revision=revision, actor=request.user, action='capture_submitted', payload={'source_digest': revision.digest,'request_digest':data.get('expected_digest')})
    from .independent_workflow import is_independent, submit_revision
    if is_independent(c):
        submit_revision(request.user, c)
    else:
        c.status = Checklist.Status.SUBMITTED; c.quality_approval = {}; c.client_approval = {}
        c.save(update_fields=['status', 'quality_approval', 'client_approval', 'updated_at'])
        WorkAssignment.objects.filter(checklist=c).update(status=WorkAssignment.Status.SUBMITTED, submitted_at=timezone.now(), completed_at=None)
    from .governance_views import audit
    audit(request.user, 'category_evidence_submitted', c.project, checklist_id=c.pk, revision_id=revision.pk)
    return revision, True


def completion_event(revision):
    last=revision.processing_events.filter(action='qa_complete').order_by('-pk').first()
    if last and not revision.processing_events.filter(action='qa_reopen',pk__gt=last.pk).exists():return last
    return None


def reviewed_payload(revision):
    from . import survey_processing as pipeline
    completed = completion_event(revision)
    if completed: return deepcopy(completed.payload['package'])
    result = SurveyProcessingResult.objects.filter(revision=revision).first()
    if result:
        if pipeline.digest(result.payload) != result.digest: raise ValidationError('Saved AI result integrity verification failed.')
        payload = deepcopy(result.payload)
    else:
        if revision.snapshot.get('schema',{}).get('sections'):
            payload = pipeline.prepare_checklist(revision.snapshot, {'findings': [], 'missing': [], 'conflicts': []})
        else:
            payload={'checklist_items':[],'findings':[],'missing':[],'conflicts':[],
                'suggested_items':[],'drawing_records':[]}
    from .qa_matching import replay
    return replay(revision,payload)


def missing_for_review(c):
    revision = current_revision(c)
    config = configuration_error(c)
    if config: return [config]
    if not revision: return ['Submit site evidence for QA review.']
    from .template_service import validate_answer
    fields = {field['id']: field for section in c.schema_snapshot.get('sections', []) for field in section.get('fields', [])}
    missing = []
    for item in reviewed_payload(revision)['checklist_items']:
        if item['id'] not in fields:continue
        field = fields[item['id']]
        required = field.get('required')
        value = item.get('value')
        sources = item.get('sources', [])
        from .qa_matching import photo_id
        photo_sources={photo_id(source) for source in sources if photo_id(source) is not None}
        if required and (not item.get('accepted') or (field['type'] != 'photo' and value in (None, '', [], {}))):
            missing.append(field['label'] + ' requires a QA-reviewed answer')
        if (field.get('photo_required') or field['type'] == 'photo' and required or field.get('evidence_rules')) and not photo_sources:
            missing.append(field['label'] + ' requires matched source evidence')
        if field.get('evidence_rules'):
            from .evidence_rules import validate_evidence_rules
            try:
                rules=validate_evidence_rules(field['evidence_rules'])
                from .qa_matching import photo_id
                originals={photo_id(s) for s in sources if photo_id(s) is not None}
                if len(originals)<rules.get('min_photos',1):missing.append(field['label']+' requires '+str(rules.get('min_photos',1))+' distinct source photos')
                # Rich criteria remain explicit QA attestations tied to actual
                # sources/reason; an available image alone never satisfies them.
                if any(key not in {'version','min_photos','notes'} and value not in (False,None,[],{},'any') for key,value in rules.items()) and (not item.get('accepted') or not item.get('reason')):
                    missing.append(field['label']+' requires an explicit source-backed QA assessment')
            except ValueError:missing.append(field['label']+' has invalid evidence requirements')
        if value not in (None, '', [], {}) and field['type'] != 'photo':
            try: validate_answer(field, value)
            except ValidationError as exc: missing.extend(exc.messages)
    return missing


def require_qa_complete(c):
    from .survey_processing import current, review_digest
    revision = current_revision(c)
    if not revision or not current(revision): raise ValidationError('Review the current submitted evidence revision.')
    event = completion_event(revision)
    if event and event.actor_id!=qa_id(c):event=None
    if not event or event.payload.get('review_digest') != review_digest(reviewed_payload(revision)):
        raise ValidationError('The assigned QA Engineer must complete this reviewed checklist before approval.')
    missing = missing_for_review(c)
    if missing: raise ValidationError(missing)


def record_qa_approval(c,actor):
    if not enabled(c):return
    require_qa_complete(c)
    if actor.pk!=qa_id(c):raise PermissionDenied('Only the assigned QA Engineer can approve this package.')
    from .survey_processing import review_digest
    revision=current_revision(c)
    SurveyProcessingEvent.objects.get_or_create(revision=revision,actor=actor,action='technical_approve',
        payload={'review_digest':review_digest(reviewed_payload(revision))})


def projected_checklist(c):
    """Read projection only; never save QA-derived answers over frozen sources."""
    if not enabled(c):return c
    revision=current_revision(c)
    if not revision:return c
    view=copy(c);view.answer_data=deepcopy(c.answer_data or {});view.image_data={}
    answers=view.answer_data.setdefault('custom',{})
    sources={p['id']:p for p in revision.snapshot['photos']}
    payload=reviewed_payload(revision)
    for item in payload['checklist_items']:
        answers.pop(item['id'],None)
        if item.get('accepted'):
            answers[item['id']]=deepcopy(item.get('value'))
    from .qa_matching import link_state
    for link in link_state(revision,payload):
        if link['state']!='qa_confirmed':continue
        source=sources[link['photo_id']]
        paths=view.image_data.setdefault(link['field_id'],[])
        if source['original'] not in paths:paths.append(source['original'])
    return view


def review_state(request, checklist_id):
    from . import survey_processing as pipeline
    c, flags = access(request, checklist_id)
    if flags['owner']: raise PermissionDenied('Checklist matching and AI findings belong to QA review.')
    revision = current_revision(c)
    if not revision: raise ValidationError('This site evidence has not been submitted.')
    payload = reviewed_payload(revision)
    review_signature = pipeline.review_digest(payload)
    completed = bool(completion_event(revision))
    from .template_views import field_is_locked
    field_details = {field['id']: {'type': field['type'], 'required': field.get('required', False),
        'section_id':section['id'],'section_title': section['title'], 'options': field.get('options', []),
        'columns':field.get('columns',[]),'unit':field.get('unit',''),'system':field.get('system',''),
        'locked':field_is_locked(c,field['id'])}
        for section in c.schema_snapshot.get('sections', []) for field in section.get('fields', [])}
    for item in payload['checklist_items']: item.update(field_details.get(item['id'], {}))
    client=role_for(request.user)==Profile.Roles.CLIENT
    if client:
        if not completed:raise PermissionDenied('QA review is not yet shared with the Client.')
        for item in payload['checklist_items']:
            for key in ('reason','qa_by','confidence','conflict'):item.pop(key,None)
            if not item.get('accepted'):item.update(value=None,proposed_answer=None,status='Missing',sources=[])
            else:
                item['sources']=[{key:value for key,value in source.items() if key not in {'mapping_reason','reviewed_by'}}
                    for source in item.get('sources',[])]
    result={'revision_id': revision.pk, 'source_digest': revision.digest, 'review_digest': review_signature,
        'revision_number':revision.number,'workflow_label':c.workflow_label,'workflow_stage':c.workflow_stage,
        'workflow_status':c.status,
        'evidence_review_role':role_for(request.user),
        'can_review': flags['can_review'] and not completed, 'completed': completed,
        'config_error': configuration_error(c), 'ai': {'status':'reviewed','completed':0,'total':0,'error':''} if client else state(request, checklist_id)['ai'],
        'photos': photos(revision.snapshot, c), 'items': payload['checklist_items'],
        'can_complete': flags['can_review'] and not completed and not missing_for_review(c),
        'missing': missing_for_review(c)}
    if role_for(request.user) in {Profile.Roles.QUALITY_ENGINEER,Profile.Roles.TEAM_LEAD}:
        from .models import ChecklistTemplate
        template=c.checklist_template
        template_id=revision.snapshot.get('template_id')
        if not template or template.pk!=template_id:
            template=ChecklistTemplate.objects.filter(pk=template_id).first()
        result['template']={'id':template.pk,'name':template.name,'version':template.version} if template else None
        from .engineer_documents import rows as document_rows
        result['documents']=document_rows(revision.snapshot,c,revision=revision,
            include_analysis=role_for(request.user)==Profile.Roles.QUALITY_ENGINEER)
        from .engineer_general_info import describe as general_information
        result['general_information']=general_information(c,{'can_edit':False},revision)
    if role_for(request.user)==Profile.Roles.QUALITY_ENGINEER:
        from .survey_pause import flags as pause_flags
        result['ai'].update(pause_flags(request,c,revision))
        from .survey_model_identity import recovery_state
        result['model_recovery']=recovery_state(c,revision,flags['can_review'] and not completed)
        from .survey_processing import ACTIVE
        from django.db.models import Q
        result['ai']['queue_ahead']=SurveyProcessingJob.objects.filter(
            Q(status__in=ACTIVE-{'queued'})|Q(status='queued',pk__lt=revision.processing_job.pk)
            ).exclude(pk=revision.processing_job.pk).count() if revision.processing_job.status=='queued' else 0
        result['ai']['error_code']='model_identity_changed' if revision.processing_job.error.startswith('[model_identity_changed]') else ''
        result['ai']['note']='Photo observations are saved as analysis runs. Checklist suggestions appear after all submitted evidence has been analysed.'
    if not client:
        from . import qa_matching
        private=role_for(request.user)==Profile.Roles.QUALITY_ENGINEER
        result.update(qa_matching.state(revision,payload,request.user,private=private))
        details=qa_matching.catalog(revision)
        for item in result['items']:item.update(details.get(item['id'],{}))
        for photo in result['photos']:
            photo['observations']=result['observations'].get(photo['id'],[])
            if private:
                match=result['photo_matches'].get(str(photo['id']))
                if match:
                    original=photo.get('filename','')
                    display=match.get('display_name') or original
                    photo['original_filename']=original
                    photo['display_name']=display
                    photo['filename']=display
                    photo['photo_match']={key:value for key,value in match.items() if key!='display_name'}
        if not private:
            confirmed={(link['photo_id'],link['field_id']) for link in result['links']}
            for item in result['items']:
                item['sources']=[source for source in item.get('sources',[]) if (qa_matching.photo_id(source),item['id']) in confirmed]
                for key in ('reason','qa_by','confidence','conflict'):item.pop(key,None)
                if not item.get('accepted'):item.update(value=None,proposed_answer=None,status='Missing')
            result['ai']={'status':'reviewed' if completed else 'pending_qa_review','completed':0,'total':0,'error':''}
    if role_for(request.user)==Profile.Roles.QUALITY_ENGINEER:
        from .qa_site_information import table as site_information_table
        result['site_information_table']=site_information_table(c,result['general_information'],result['items'],
            can_review=result['can_review'] and not result['config_error'])
        from .qa_review_progress import token as progress_token
        result['progress_token']=progress_token(c,revision)
        from .survey_acceleration import photo_duplicates
        duplicates=photo_duplicates(revision)
        for photo in result['photos']:
            photo.update({'duplicate':None,'analysis_reused':None,**duplicates.get(photo['id'],{})})
    return result


@transaction.atomic
def review_action(request, checklist_id, data, *, verified_model_identity=None):
    from . import survey_processing as pipeline
    from .template_service import validate_answer
    Checklist.objects.select_for_update().get(pk=checklist_id)
    c, flags = access(request, checklist_id, quality=True)
    revision = current_revision(c)
    if not revision or not pipeline.current(revision): raise ValidationError('The submitted source changed. Return it for Engineer correction.')
    from . import qa_matching
    qa_matching.require_revision(revision,data)
    if data.get('action') in {'pause_ai','resume_ai'}:
        from .survey_pause import control
        control(request,checklist_id,revision.pk,data['action'],data.get('expected_digest') or data.get('source_digest'))
        return review_state(request,checklist_id)
    if data.get('action')=='retry_current_model':
        if configuration_error(c):raise ValidationError(configuration_error(c))
        from .survey_model_identity import recover
        try:
            with transaction.atomic():recover(request,c,revision,data,verified=verified_model_identity)
        except DatabaseError as exc:
            raise ValidationError('Model recovery could not be saved. No processing attempt was changed; refresh and retry.') from exc
        return review_state(request,checklist_id)
    if data.get('action') == 'retry':
        if configuration_error(c): raise ValidationError(configuration_error(c))
        job = revision.processing_job
        if job.status == 'failed':
            job.status='queued';job.error='';job.lease_owner='';job.lease_until=None
            job.save(update_fields=['status','error','lease_owner','lease_until'])
            SurveyProcessingEvent.objects.create(revision=revision,actor=request.user,action='qa_retry')
        return review_state(request, checklist_id)
    if completion_event(revision): raise ValidationError('This QA package is complete and locked. Use the review route to return it for correction.')
    payload = reviewed_payload(revision)
    if data.get('action') in qa_matching.LINK_ACTIONS|{'reorder'}:
        if configuration_error(c):raise ValidationError(configuration_error(c))
        qa_matching.action(revision,c,request.user,data,payload)
        return review_state(request,checklist_id)
    if data.get('expected_review_digest') != pipeline.review_digest(payload): raise ValidationError('The QA review changed. Refresh before saving another decision.')
    action = data.get('action')
    if action == 'complete':
        missing = missing_for_review(c)
        if missing: raise ValidationError(missing)
        from .roadmap_service import require_qualified_template
        require_qualified_template(c)
        SurveyProcessingEvent.objects.create(revision=revision,actor=request.user,action='qa_complete',
            payload={'package':payload,'review_digest':pipeline.review_digest(payload)})
        return review_state(request, checklist_id)
    if action not in {'answer', 'map'}: raise ValidationError('Choose a supported QA review action.')
    preserve=data.get('preserve_evidence',False)
    if type(preserve) is not bool or preserve and (action!='answer' or data.get('photo_ids')):
        raise ValidationError('Save a checklist value separately from changes to its photo evidence.')
    ident = data.get('field_id'); reason = data.get('reason', '')
    fields = {field['id']:field for section in revision.snapshot['schema'].get('sections',[]) for field in section.get('fields',[])}
    if ident not in fields: raise ValidationError('Choose an actual item from the approved checklist.')
    if not isinstance(reason,str) or len(reason)>4000: raise ValidationError('Reviewer remarks must be text of at most 4000 characters.')
    rules=fields[ident].get('evidence_rules') or {}
    attestation=any(key not in {'version','min_photos','notes'} and value not in (False,None,[],{},'any')
                    for key,value in rules.items())
    if not reason.strip() and (action=='map' or attestation):
        raise ValidationError('Record the source-backed QA review reason required by this evidence policy.')
    ids = data.get('photo_ids',[])
    if not isinstance(ids,list) or len(ids)>500 or any(type(i) is not int for i in ids) or len(set(ids))!=len(ids): raise ValidationError('Choose valid distinct source photos.')
    allowed = {p['id']:p for p in revision.snapshot['photos']}
    if any(i not in allowed for i in ids): raise ValidationError('A photo is outside this submitted evidence revision.')
    field = fields[ident]
    from .template_views import require_field_editable
    require_field_editable(c,ident)
    if field.get('system') and data.get('value',c.site_id)!=c.site_id: raise ValidationError('The linked site ID must match the saved survey.')
    from .engineer_documents import retained_item_sources
    updates={'sources':[{'source_id':'photo:'+str(i),'reference':allowed[i]['filename']} for i in ids]+
             retained_item_sources(revision,payload,ident),
             'reason':reason.strip()[:4000],'qa_by':request.user.pk}
    existing=next((item for item in payload['checklist_items'] if item['id']==ident),{})
    if preserve:
        # A value-only cell save neither freezes an empty photo selection nor
        # turns AI suggestions into confirmed assignments. Existing link events
        # and any later AI proposals retain their independent matching state.
        updates={'reason':reason.strip()[:4000],'qa_value_by':request.user.pk}
    if action=='answer':
        value=data.get('value')
        if field['type']=='number' and type(value) in (int,float):value=str(value)
        if value not in (None,'',[],{}) and field['type']!='photo':validate_answer(field,value)
        updates.update(value=value,proposed_answer=value,accepted=True,conflict=False,
            status='Confirmed from evidence' if (existing.get('sources') if preserve else updates['sources']) else 'Reported' if value not in (None,'',[],{}) else 'Missing')
    SurveyProcessingEvent.objects.create(revision=revision,actor=request.user,action='qa_answer' if action=='answer' else 'qa_mapping',
        reason=reason.strip()[:4000],payload={'items':{ident:updates}})
    return review_state(request,checklist_id)
