"""Scalar QA analysis ticks; full evidence is loaded only when review changes."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Max
from django.http import Http404
from django.shortcuts import get_object_or_404

from .access import role_for
from .models import Profile
from .survey_processing_models import SurveyProcessingRevision,SurveyProcessingResult


def phase_projection(status,completed,total,saved_batches,has_result):
    """Describe observed stages; equal counters alone do not prove a boundary.

    Observation extraction is part of source analysis, not another queued job.
    Mapping totals are not persisted, so saved batches never imply a percentage.
    """
    analysis_done=has_result or saved_batches>0 or status in {'preparing_checklist','preparing_drawings','ready_for_review'}
    matching_done=has_result or status in {'preparing_drawings','ready_for_review'}
    active_states={'queued':'queued','analysing_evidence':'running','preparing_checklist':'running',
        'paused':'paused','pausing':'pausing','failed':'failed'}
    analysis_state='complete' if analysis_done else active_states.get(status,'unavailable')
    matching_state='complete' if matching_done else active_states.get(status,'unavailable') if analysis_done else 'waiting'
    if status=='analysing_evidence' and analysis_done and not matching_done:matching_state='waiting'
    return {
        'analysis':{'label':'Analysis','state':analysis_state,'completed':completed,'total':total,'unit':'sources',
            'note':'Submitted photos and document pages are analysed; saved results are retained.'},
        'findings':{'label':'Findings','state':analysis_state,'completed':None,'total':None,'unit':'observations',
            'shared_with':'analysis','note':'Findings are extracted during source analysis; no separate extraction job.'},
        'matching':{'label':'Checklist tagging','state':matching_state,'completed':saved_batches,'total':None,
            'unit':'saved_batches','note':'Saved mapping batches are durable checkpoints, not photo totals. The planned batch total is unknown.'}}


def phases(revision,job=None):
    """Only scalar counts/exists checks; never load source JSON or snapshots."""
    job=job if job is not None else revision.processing_job
    saved=revision.source_analyses.filter(source_id__startswith='mapping:').count()
    result=SurveyProcessingResult.objects.filter(revision_id=revision.pk).exists()
    return phase_projection(job.status,job.completed,job.total,saved,result)


def token(c, revision):
    from .survey_processing import digest
    row = SurveyProcessingRevision.objects.filter(pk=revision.pk, checklist=c).values(
        'digest', 'processing_job__status', 'processing_result__pk').first()
    if row is None:
        raise Http404()
    event = revision.processing_events.exclude(action='source_fingerprints').aggregate(last=Max('pk'))['last']
    return digest({'revision': revision.pk, 'source': row['digest'], 'status': row['processing_job__status'],
                   'result': row['processing_result__pk'], 'event': event, 'updated': str(c.updated_at)})


def progress(request, checklist_id):
    from .category_intake import access
    from .survey_pause import flags
    from .survey_processing import digest
    c, _ = access(request, checklist_id)
    if role_for(request.user) != Profile.Roles.QUALITY_ENGINEER:
        raise PermissionDenied('Analysis progress belongs to the assigned QA review workspace.')
    ident = (c.intake_metadata or {}).get('category_intake_revision')
    revision = get_object_or_404(c.processing_revisions.only('id', 'digest'), pk=ident)
    job = revision.processing_job
    ai = {'status': job.status, 'completed': job.completed, 'total': job.total, 'error': job.error,
          **flags(request, c, status=job.status),'phases':phases(revision,job)}
    result = {'revision_id': revision.pk, 'progress_token': token(c, revision), 'ai': ai}
    photo = request.GET.get('photo_id')
    if photo is not None:
        if not isinstance(photo, str) or not photo.isdigit():
            raise ValidationError('Choose a submitted source photo.')
        ident = int(photo)
        if not c.photo_evidence.filter(pk=ident).exists():
            raise Http404()
        rows = revision.source_analyses.filter(source_id='photo:' + str(ident))
        findings = []
        for saved in rows:
            if digest(saved.payload) != saved.digest:
                raise ValidationError('Saved photo analysis integrity verification failed.')
            findings.extend(saved.payload.get('findings', []))
        result['photo'] = {'id': ident, 'observations': findings}
    return result
