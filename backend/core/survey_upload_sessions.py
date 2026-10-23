"""Audited upload leases. Recovery closes abandoned envelopes, never evidence.

The short database locks cover counters and permissions, never image decoding or
file transfer. A live browser heartbeat extends an in-flight batch lease; a dead
browser/process becomes recoverable without silently treating its uploads as done.
"""
import math
import uuid
from contextlib import contextmanager
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from .access import role_for
from .models import Checklist, Profile
from .survey_processing_models import SurveyUploadSession, SurveyUploadSessionEvent


def _access(request, checklist_id):
    from .survey_processing import access
    Checklist.objects.select_for_update().get(pk=checklist_id)
    from .category_intake import access as capture_access
    return capture_access(request, checklist_id)


def _session(c, token):
    try:
        return SurveyUploadSession.objects.select_for_update().get(checklist=c, token=uuid.UUID(str(token)))
    except (ValueError, TypeError, AttributeError, SurveyUploadSession.DoesNotExist):
        raise Http404('Upload session not found.')


def _writer(flags):
    if not flags['can_submit']:
        raise PermissionDenied('Only the assigned Engineer can manage an active upload.')


def _owner(session, actor):
    if session.actor_id != actor.pk:
        raise Http404('Upload session not found.')


def _event(session, actor, action, reason='', **payload):
    SurveyUploadSessionEvent.objects.create(session=session, actor=actor, action=action, reason=reason, payload=payload)


def _lease_seconds():
    return max(60, int(getattr(settings, 'SURVEY_UPLOAD_BATCH_LEASE_SECONDS', 900)))


def _stale_seconds():
    return max(30, int(getattr(settings, 'SURVEY_UPLOAD_STALE_SECONDS', 300)))


def activity(session, now=None):
    now = now or timezone.now()
    active_transfer = bool(session.active_batches and session.active_until and session.active_until > now)
    stale_at = session.heartbeat_at + timedelta(seconds=_stale_seconds())
    if session.finished_at:
        return 'recovered' if session.recovered_by_id else 'finished', 0
    if session.interrupted_at and not active_transfer:
        return 'interrupted', 0
    eligible = max(stale_at, session.active_until) if active_transfer else stale_at
    wait = max(0, math.ceil((eligible - now).total_seconds()))
    return ('active' if wait else 'stale'), wait


def _may_recover(request, flags):
    return bool(flags['can_submit'] or role_for(request.user) in {Profile.Roles.ADMIN, Profile.Roles.TEAM_LEAD})


def state(request, c, flags=None):
    if flags is None:
        from .survey_processing import access
        c, flags = access(request, c.pk)
    sessions = list(c.survey_upload_sessions.filter(finished_at__isnull=True).select_related('actor').order_by('created_at'))
    can_recover = _may_recover(request, flags)
    items = []
    now = timezone.now()
    for session in sessions:
        status, wait = activity(session, now)
        own = session.actor_id == request.user.pk
        if not own and not can_recover:
            continue
        items.append({'token': str(session.token), 'actor': session.actor.get_full_name() or session.actor.get_username(),
            'own': own, 'status': status, 'last_activity': session.heartbeat_at.isoformat(),
            'active_batches': session.active_batches, 'recovery_wait_seconds': wait,
            'recoverable': can_recover and status in {'stale', 'interrupted'},
            'can_finish': bool(own and flags['can_submit'] and not (session.active_batches and session.active_until and session.active_until > now))})
    return {'inflight': len(sessions), 'own_tokens': [str(s.token) for s in sessions if s.actor_id == request.user.pk],
            'can_recover': can_recover, 'sessions': items, 'heartbeat_seconds': 30}


def require_complete(c):
    if c.survey_upload_sessions.filter(finished_at__isnull=True).exists():
        raise ValidationError('Uploads are still open. Finish active uploads or recover an interrupted/stale upload session in AI Checklist & Drawings. Saved files are preserved.')


def require_batch_open(c, token):
    """Call under the checklist write lock, immediately before persisting files.

    A process delayed longer than its lease must not append files after another
    actor recovered that envelope and submitted a new immutable snapshot.
    """
    session = _session(c, token)
    if session.finished_at or not session.active_batches:
        raise ValidationError('This interrupted upload was closed. Saved files are preserved; start a new upload to retry this batch.')


@transaction.atomic
def start(request, checklist_id):
    c, flags = _access(request, checklist_id)
    _writer(flags)
    session = SurveyUploadSession.objects.create(token=uuid.uuid4(), checklist=c, actor=request.user)
    _event(session, request.user, 'started')
    return session


@transaction.atomic
def finish(request, checklist_id, token):
    c, flags = _access(request, checklist_id)
    _writer(flags)
    session = _session(c, token)
    _owner(session, request.user)
    if session.finished_at:
        return session
    now = timezone.now()
    if session.active_batches and session.active_until and session.active_until > now:
        raise ValidationError('An upload batch is still active. Wait for it to finish before closing this session.')
    session.finished_at = now
    session.save(update_fields=['finished_at'])
    _event(session, request.user, 'finished')
    return session


@transaction.atomic
def heartbeat(request, checklist_id, token):
    c, flags = _access(request, checklist_id)
    _writer(flags)
    session = _session(c, token)
    _owner(session, request.user)
    if session.finished_at:
        raise ValidationError('This upload session is closed. Start a new upload for additional files.')
    session.heartbeat_at = timezone.now()
    fields = ['heartbeat_at']
    if session.active_batches:
        session.active_until = session.heartbeat_at + timedelta(seconds=_lease_seconds())
        fields.append('active_until')
    session.save(update_fields=fields)
    return session


@transaction.atomic
def interrupt(request, checklist_id, token):
    c, flags = _access(request, checklist_id)
    _writer(flags)
    session = _session(c, token)
    _owner(session, request.user)
    if not session.finished_at and not session.interrupted_at:
        session.interrupted_at = timezone.now()
        session.save(update_fields=['interrupted_at'])
        _event(session, request.user, 'interrupted', active_batches=session.active_batches)
    return session


@transaction.atomic
def recover(request, checklist_id, token, reason):
    c, flags = _access(request, checklist_id)
    if not _may_recover(request, flags):
        raise PermissionDenied('Recovery requires the assigned Engineer, project Admin or Team Lead.')
    session = _session(c, token)
    if session.finished_at:
        return session
    if not isinstance(reason, str) or not 5 <= len(reason.strip()) <= 1000:
        raise ValidationError('Explain why this interrupted upload can be closed (5–1000 characters).')
    status, wait = activity(session)
    if status not in {'stale', 'interrupted'}:
        raise ValidationError(f'This upload is still active. Wait for its Engineer or heartbeat to finish; recovery is available after {wait} seconds without activity.')
    session.finished_at = timezone.now()
    session.recovered_by = request.user
    session.recovery_reason = reason.strip()
    session.save(update_fields=['finished_at', 'recovered_by', 'recovery_reason'])
    _event(session, request.user, 'recovered', reason=session.recovery_reason,
           previous_actor_id=session.actor_id, previous_state=status, stale_batch_count=session.active_batches)
    return session


@contextmanager
def upload_batch(request, checklist_id, token=None):
    """Protect a real transfer, including concurrent requests and a crashed process."""
    standalone = not token
    session = start(request, checklist_id) if standalone else None
    token = session.token if standalone else token
    with transaction.atomic():
        c, flags = _access(request, checklist_id)
        _writer(flags)
        session = _session(c, token)
        _owner(session, request.user)
        if session.finished_at:
            raise ValidationError('The upload session is closed. Start a new upload for additional files.')
        now = timezone.now()
        # Expired request counters are retained for audit until recovery. A new
        # request may not resurrect a known abandoned transfer implicitly.
        if session.active_batches and session.active_until and session.active_until <= now:
            raise ValidationError('A previous transfer was interrupted. Recover its session before uploading again.')
        session.active_batches += 1
        session.heartbeat_at = now
        session.active_until = now + timedelta(seconds=_lease_seconds())
        session.interrupted_at = None
        session.save(update_fields=['active_batches', 'heartbeat_at', 'active_until', 'interrupted_at'])
    try:
        yield session
    finally:
        # Server-owned completion can decrement an already-started transfer even
        # when its Engineer was reassigned/revoked while the request was running.
        with transaction.atomic():
            Checklist.objects.select_for_update().get(pk=checklist_id)
            saved = SurveyUploadSession.objects.select_for_update().get(token=session.token)
            saved.active_batches = max(0, saved.active_batches - 1)
            saved.heartbeat_at = timezone.now()
            if not saved.active_batches:
                saved.active_until = None
            saved.save(update_fields=['active_batches', 'heartbeat_at', 'active_until'])
            if standalone and not saved.finished_at:
                saved.finished_at = timezone.now()
                saved.save(update_fields=['finished_at'])
                _event(saved, request.user, 'finished')
