"""Audited processing controls. Pause intent survives worker and browser restarts."""
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .access import role_for
from .models import Checklist, Profile
from .survey_processing_models import SurveyProcessingJob, SurveyProcessingEvent


CONTROL_EVENTS = {'pause_ai': 'pause_requested', 'resume_ai': 'resumed'}
CONTROL_SALT = 'isurvix.processing-control-generation.v1'


def _token(request, revision, generation):
    return signing.Signer(salt=CONTROL_SALT).sign_object({
        'revision': revision.pk, 'source': revision.digest,
        'actor': request.user.pk, 'generation': generation}, compress=True)


def _generation(request, revision, action, token, latest):
    """Accept one observed intent, or the exact latest successful retry only."""
    try:
        observed = signing.Signer(salt=CONTROL_SALT).unsign_object(token)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValidationError('Processing controls changed. Refresh before pausing or resuming AI Analysis.')
    if (not isinstance(observed, dict) or
            observed.get('revision') != revision.pk or observed.get('source') != revision.digest or
            observed.get('actor') != request.user.pk or type(observed.get('generation')) is not int):
        raise ValidationError('Choose the current processing control for this submission.')
    generation = latest['pk'] if latest else 0
    if observed['generation'] == generation:
        return generation, False
    if (latest and latest['actor_id'] == request.user.pk and
            latest['action'] == CONTROL_EVENTS.get(action) and
            latest['payload'].get('observed_control_generation') == observed['generation']):
        return observed['generation'], True
    raise ValidationError('A newer Pause or Resume changed this job. Refresh before controlling AI Analysis.')


class ProcessingPaused(Exception):
    """A requested source-boundary stop, not a processing failure."""


def _allowed(request, c):
    from .category_intake import enabled, qa_id
    role = role_for(request.user)
    quality = role == Profile.Roles.QUALITY_ENGINEER and qa_id(c) == request.user.pk
    if enabled(c):
        route = getattr(c, 'review_route_record', None)
        return quality and c.status in {Checklist.Status.SUBMITTED, Checklist.Status.REVIEW} and (
            not route or route.stage == 'quality_engineer')
    # The retained legacy processing service does not restore Engineer AI
    # responsibilities. Processing controls belong to the assigned QA reviewer.
    return quality and c.status != Checklist.Status.FINAL


def flags(request, c, revision=None, *, status=None):
    from .survey_processing import ACTIVE
    status = status if status is not None else revision.processing_job.status if revision else None
    allowed = _allowed(request, c)
    control_token = None
    if allowed and revision:
        # Read status and its control generation in the same SQL snapshot. A
        # polling response cannot combine old Resume permissions with a token
        # issued after another browser's newer Pause. No source JSON is loaded.
        latest = SurveyProcessingEvent.objects.filter(revision_id=revision.pk,
            action__in=CONTROL_EVENTS.values()).order_by('-pk').values('pk')[:1]
        saved = SurveyProcessingJob.objects.filter(revision_id=revision.pk).annotate(
            control_generation=Subquery(latest)).values('status', 'control_generation').first()
        if saved:
            status = saved['status']
            control_token = _token(request, revision, saved['control_generation'] or 0)
    message = ('Pause requested. The current evidence task will finish and save before processing stops.'
               if status == 'pausing' else
               'AI Analysis is paused. Saved analyses and original evidence are retained. Resume to continue.'
               if status == 'paused' else '')
    return {'can_pause': bool(allowed and status in ACTIVE),
            'can_resume': bool(allowed and status == 'paused'), 'pause_message': message,
            'control_token': control_token}


def _paused(job):
    job.status, job.lease_owner, job.lease_until = 'paused', '', None
    job.save(update_fields=['status', 'lease_owner', 'lease_until', 'updated_at'])


def settle_expired(project_ids=None):
    """A dead worker cannot acknowledge intent; never reclaim its paused work."""
    now = timezone.now()
    jobs = SurveyProcessingJob.objects.filter(status='pausing').filter(
        Q(lease_until__lte=now) | Q(lease_until__isnull=True))
    if project_ids is not None:
        jobs = jobs.filter(revision__checklist__project_id__in=project_ids)
    with transaction.atomic():
        for job in jobs.select_for_update():
            _paused(job)


def boundary(job):
    """Call between durable sources, outside any source-save transaction."""
    paused = False
    with transaction.atomic():
        saved = SurveyProcessingJob.objects.select_for_update().get(pk=job.pk)
        if saved.status == 'paused':
            paused = True
        elif saved.status == 'pausing' and saved.lease_owner == job.lease_owner:
            _paused(saved)
            paused = True
    if paused:
        raise ProcessingPaused()


def yield_job(job, *, error='', failed=False):
    """Busy/error handling must never erase a concurrent human pause request."""
    with transaction.atomic():
        saved = SurveyProcessingJob.objects.select_for_update().get(pk=job.pk)
        if saved.lease_owner != job.lease_owner:
            return
        saved.status = 'paused' if saved.status == 'pausing' else 'failed' if failed else 'queued'
        saved.error, saved.lease_owner, saved.lease_until = error, '', None
        saved.save(update_fields=['status', 'error', 'lease_owner', 'lease_until', 'updated_at'])


@transaction.atomic
def control(request, checklist_id, revision_id, action, expected_digest, expected_control_token=None):
    from . import survey_processing as pipeline
    from .category_intake import enabled, access as capture_access, current_revision
    Checklist.objects.select_for_update().get(pk=checklist_id)
    c, _ = pipeline.access(request, checklist_id)
    if enabled(c):
        capture_access(request, checklist_id, quality=True)
    if not _allowed(request, c):
        raise PermissionDenied('Only the authorised processing reviewer may control this job at its current stage.')
    job = get_object_or_404(SurveyProcessingJob.objects.select_for_update().select_related('revision'),
                           revision_id=revision_id, revision__checklist=c)
    revision = job.revision
    if (expected_digest != revision.digest or not pipeline.current(revision)
            or (enabled(c) and getattr(current_revision(c), 'pk', None) != revision.pk)):
        raise ValidationError('These inputs or the selected revision changed. Refresh before controlling AI Analysis.')
    if action not in CONTROL_EVENTS:
        raise ValidationError('Choose Pause AI or Resume AI.')
    latest = revision.processing_events.filter(action__in=CONTROL_EVENTS.values()).order_by('-pk').values(
        'pk', 'actor_id', 'action', 'payload').first()
    generation, replay = _generation(request, revision, action, expected_control_token, latest)
    if replay:
        return revision
    if action == 'pause_ai':
        if job.status in {'paused', 'pausing'}:
            return revision
        if job.status not in pipeline.ACTIVE:
            raise ValidationError('Only queued or processing AI Analysis can be paused.')
        running = bool(job.lease_owner and job.lease_until and job.lease_until > timezone.now())
        job.status = 'pausing' if running else 'paused'
        if not running:
            job.lease_owner, job.lease_until = '', None
        job.save(update_fields=['status', 'lease_owner', 'lease_until', 'updated_at'])
        SurveyProcessingEvent.objects.create(revision=revision, actor=request.user,
            action='pause_requested', payload={'status': job.status, 'completed': job.completed,
                'observed_control_generation': generation})
    elif action == 'resume_ai':
        if job.status == 'queued':
            return revision
        if job.status in pipeline.ACTIVE and latest and latest['action'] == 'resumed':
            # A successful reply can be lost while the worker already claims
            # the resumed job. Retrying must not reset its live lease or audit.
            return revision
        if job.status == 'pausing' and (not job.lease_until or job.lease_until <= timezone.now()):
            _paused(job)
        if job.status != 'paused':
            raise ValidationError('Wait for the current evidence task to save and pause before resuming.')
        job.status, job.error, job.lease_owner, job.lease_until = 'queued', '', '', None
        job.save(update_fields=['status', 'error', 'lease_owner', 'lease_until', 'updated_at'])
        SurveyProcessingEvent.objects.create(revision=revision, actor=request.user,
            action='resumed', payload={'completed': job.completed,
                'observed_control_generation': generation})
    else:
        raise ValidationError('Choose Pause AI or Resume AI.')
    return revision
