"""Versioned model pins and explicit zero-progress QA recovery.

Legacy opaque pins require exact metadata proof. Never guess their weights or
discard completed inference to make an old job use another configuration.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from .survey_processing_models import SurveyProcessingEvent

VERSION='ollama-manifest-v1'
MISMATCH='[model_identity_changed]'


def verified_identity(model,pipeline_version):
    from .photo_service import verify_vision
    from .survey_processing import digest
    details=verify_vision(model,base_url=getattr(settings,'PHOTO_OLLAMA_BASE_URL',settings.OLLAMA_BASE_URL))
    details=dict(details)
    manifest=details.pop('_manifest_digest','')
    if not isinstance(manifest,str) or len(manifest)!=64 or any(char not in '0123456789abcdef' for char in manifest):
        raise ValidationError('The local service did not provide a valid installed model manifest identity. No processing pin was changed.')
    return {'version':VERSION,'model':model,'manifest_digest':manifest,
        'fingerprint':digest({'version':VERSION,'model':model,'manifest_digest':manifest,'pipeline':pipeline_version}),
        'legacy_fingerprint':digest({'model':model,'details':details,'pipeline':pipeline_version})}


def pin(job,identity):
    from django.db import transaction
    from .survey_processing import progress
    previous=job.model_digest
    current=identity['fingerprint']
    if previous and previous not in {current,identity['legacy_fingerprint']}:
        raise ValidationError(MISMATCH+' The saved model configuration identity differs from the current local service. '
            'Saved progress is preserved. QA can explicitly retry with the current model only when no source analysis exists; '
            'otherwise retain this revision and arrange a new submission.')
    if previous==current:return
    with transaction.atomic():
        progress(job,model_digest=current)
        SurveyProcessingEvent.objects.create(revision=job.revision,actor_id=job.revision.submitted_by_id,
            action='model_identity_migrated' if previous else 'model_identity',payload={
                **identity,'previous_model_digest':previous,
                'proof':'exact_legacy_metadata_match' if previous else 'installed_manifest'})


def recovery_blocker(c,revision,job):
    from .category_intake import completion_event
    if job.status not in {'failed','queued'}:return 'The job is active or already complete. Its running work is preserved.'
    if not job.model_digest:return 'This job has no saved model pin and can use the ordinary processing queue.'
    if c.section_approvals or c.quality_approval or completion_event(revision):return 'The reviewed or approved package is locked.'
    if job.completed>0:return 'Completed processing is recorded. Preserve its model identity and saved progress.'
    if revision.source_analyses.exists():return 'Saved source analysis exists. Preserve its model identity and use a new submission rather than mixing model attempts.'
    if hasattr(revision,'processing_result') or revision.drawing_sets.exists():return 'Saved processing results or drawings exist and must be preserved.'
    if job.status=='queued' and revision.processing_events.filter(
        action__in=['model_identity','model_identity_migrated','qa_model_recovery'],payload__fingerprint=job.model_digest).exists():
        return 'This verified processing attempt is already queued. Wait for the worker or use ordinary retry after a failure.'
    return ''


def recovery_state(c,revision,can_review):
    if not revision:return {'available':False,'blocked_reason':'No current submission.'}
    job=revision.processing_job
    blocker=recovery_blocker(c,revision,job)
    return {'available':bool(can_review and not blocker),
        'expected_model_digest':job.model_digest,
        'message':'Explicitly use the currently installed local model for this unchanged submission. '
            'No completed source analysis, result or drawing will be replaced.',
        'blocked_reason':blocker or ''}


def _checked_recovery(request,c,revision,data):
    from .survey_processing import digest,review_digest
    from .category_intake import reviewed_payload
    reason=data.get('reason','')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>4000:
        raise ValidationError('Record why QA is explicitly selecting the current local model.')
    if data.get('expected_review_digest')!=review_digest(reviewed_payload(revision)):
        raise ValidationError('The QA review changed. Refresh before changing the processing attempt.')
    expected=data.get('expected_model_digest')
    if not isinstance(expected,str) or not expected:raise ValidationError('Refresh the saved model identity before recovery.')
    key=digest({'revision_id':revision.pk,'source_digest':revision.digest,'previous_model_digest':expected,
        'actor_id':request.user.pk,'reason':reason.strip()})
    if revision.processing_events.filter(action='qa_model_recovery',payload__request_key=key).exists():return key,True
    job=revision.processing_job
    if job.model_digest!=expected:raise ValidationError('The job model identity changed. Refresh before retrying.')
    blocked=recovery_blocker(c,revision,job)
    if blocked:raise ValidationError(blocked)
    return key,False


def prepare_recovery(request,checklist_id,data):
    """Authorise metadata reads before the write transaction; recheck on save."""
    from .category_intake import access,current_revision,configuration_error
    from .qa_matching import require_revision
    from .survey_processing import current
    c,_=access(request,checklist_id,quality=True)
    revision=current_revision(c)
    if not revision or not current(revision):raise ValidationError('The submitted source changed. Return it for Engineer correction.')
    require_revision(revision,data)
    config=configuration_error(c)
    if config:raise ValidationError(config)
    _,done=_checked_recovery(request,c,revision,data)
    if done:return None
    return verified_identity(revision.processing_job.model,revision.processing_job.pipeline_version)


def recover(request,c,revision,data,verified=None):
    """Called inside the locked QA action; never modifies source snapshots."""
    from django.utils import timezone
    from .survey_processing_models import SurveyProcessingJob
    job=SurveyProcessingJob.objects.select_for_update().get(revision=revision)
    revision.processing_job=job
    key,done=_checked_recovery(request,c,revision,data)
    if done:return
    if verified is None:raise ValidationError('Refresh and use the authenticated current-model recovery action.')
    identity=verified
    reason=data['reason']
    SurveyProcessingEvent.objects.create(revision=revision,actor=request.user,action='qa_model_recovery',
        reason=reason.strip(),payload={**identity,'previous_model_digest':job.model_digest,'request_key':key,
            'source_digest':revision.digest,'project_id':c.project_id,'previous_status':job.status})
    job.model_digest=identity['fingerprint'];job.status='queued';job.error='';job.lease_owner='';job.lease_until=None
    job.updated_at=timezone.now()
    job.save(update_fields=['model_digest','status','error','lease_owner','lease_until','updated_at'])
