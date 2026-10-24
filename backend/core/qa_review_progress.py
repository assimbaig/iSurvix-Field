"""Scalar QA analysis ticks; full evidence is loaded only when review changes."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Max
from django.http import Http404
from django.shortcuts import get_object_or_404

from .access import role_for
from .models import Profile
from .survey_processing_models import SurveyProcessingRevision


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
          **flags(request, c, status=job.status)}
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
