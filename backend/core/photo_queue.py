"""Durable photo analysis with bounded staging and endpoint-specific leases."""
import threading
import uuid
import time
from types import SimpleNamespace
from contextlib import contextmanager
from datetime import timedelta
from django.conf import settings
from django.db import transaction, close_old_connections
from django.utils import timezone
from .models import PhotoWorkerLease, PhotoJob, PhotoDraft
from .local_ai import InferenceBusy


def lease_seconds():
    return max(300, settings.OLLAMA_TIMEOUT + 120)


@contextmanager
def inference_lease(key='inference'):
    owner = uuid.uuid4().hex
    now = timezone.now()
    with transaction.atomic():
        PhotoWorkerLease.objects.get_or_create(key=key, defaults={'owner':'', 'expires_at':now})
        acquired = PhotoWorkerLease.objects.filter(key=key, expires_at__lte=now).update(owner=owner, expires_at=now+timedelta(seconds=lease_seconds()))
    if not acquired:
        raise InferenceBusy('The local inference queue is busy.')
    stop = threading.Event()
    lost = threading.Event()
    def heartbeat():
        close_old_connections()
        try:
            while not stop.wait(15):
                try:
                    if not PhotoWorkerLease.objects.filter(key=key, owner=owner).update(expires_at=timezone.now()+timedelta(seconds=lease_seconds())):
                        lost.set()
                        return
                except Exception:
                    lost.set()
                    return
        finally:
            close_old_connections()
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    def check():
        if lost.is_set() or not PhotoWorkerLease.objects.filter(key=key, owner=owner, expires_at__gt=timezone.now()).exists():
            raise RuntimeError('Inference lease expired; results were discarded.')
    try:
        yield check
    finally:
        stop.set()
        thread.join(timeout=20)
        PhotoWorkerLease.objects.filter(key=key, owner=owner).update(expires_at=timezone.now())


def photo_inference_lease():
    # Identical endpoints still serialize against chat. An independent native
    # photo server has its own lock and cannot block the assistant.
    from urllib.parse import urlsplit
    def endpoint(url):
        parsed=urlsplit(url)
        return (parsed.scheme,parsed.port or 80)
    separate=endpoint(getattr(settings,'PHOTO_OLLAMA_BASE_URL',settings.OLLAMA_BASE_URL))!=endpoint(settings.OLLAMA_BASE_URL)
    return inference_lease('photo-inference') if separate else inference_lease()


@contextmanager
def photo_worker_lease():
    # Queue ownership is global to the database even when workers use different
    # endpoints. Otherwise a manually started fallback consumer could race the
    # dedicated consumer and recover its live job.
    with inference_lease('photo-worker') as worker_check,photo_inference_lease() as native_check:
        def check():
            worker_check()
            native_check()
        yield check


def process_next():
    # Idle polling must stay read-only: acquiring a lease would otherwise write
    # twice and start a heartbeat thread every two seconds without any work.
    if not PhotoJob.objects.filter(status__in=['queued','running']).exists():
        return False
    from .photo_service import analyze_photo
    from .template_views import survey_access
    with photo_worker_lease() as check:
        # Acquiring the single inference lease proves no live worker owns a running job.
        PhotoJob.objects.filter(status='running').update(status='queued', error='Recovered after worker interruption.')
        with transaction.atomic():
            job = PhotoJob.objects.filter(status='queued').order_by('created_at','pk').first()
            if not job:
                return False
            job.status='running'
            job.attempts+=1
            job.error=''
            job.save(update_fields=['status','attempts','error','updated_at'])
        try:
            failed_photo_id=None
            attempt_started=time.monotonic()
            attempt_completed=0
            fields = {f['id']: f for section in job.schema['sections'] for f in section['fields']}
            staged=set()
            context=job.progress.get('evidence_context')
            pending_ids=list(job.photos.exclude(pk__in=job.processed_photo_ids).order_by('pk').values_list('pk',flat=True))
            def authorize(candidate):
                check()
                if not job.requested_by_id:
                    raise ValueError('Requesting user no longer has access.')
                job.requested_by.refresh_from_db()
                if not job.requested_by.is_active:
                    raise ValueError('Requesting user no longer has access.')
                current=survey_access(SimpleNamespace(user=job.requested_by),job.checklist_id,edit=True)['checklist']
                if candidate.checklist_id!=job.checklist_id or current.schema_snapshot!=job.schema:
                    raise ValueError('Photo or checklist schema no longer matches this job.')
            for photo in job.photos.order_by('pk'):
                if photo.pk in job.processed_photo_ids:
                    continue
                # A bounded durable buffer prevents repeated vision if a later
                # OCR, semantic search, or targeted verification needs retrying.
                if context and photo.pk not in staged:
                    from .evidence_pipeline import prepare_observation
                    offset=pending_ids.index(photo.pk)
                    for candidate in job.photos.filter(pk__in=pending_ids[offset:offset+4]).order_by('pk'):
                        failed_photo_id=candidate.pk
                        authorize(candidate)
                        started=time.monotonic()
                        job.progress={**job.progress,'stage':'extracting_metadata','photo_id':candidate.pk,
                                      'pipeline':'dedicated-photo-v1'}
                        job.save(update_fields=['progress','updated_at'])
                        prepare_observation(candidate,job.model,context,lambda:authorize(candidate))
                        ready=set(job.progress.get('analysis_ready_photo_ids',[]))|{candidate.pk}
                        job.progress={**job.progress,'analysis_ready_photo_ids':sorted(ready),
                                      'last_analysis_seconds':round(time.monotonic()-started,3)}
                        job.save(update_fields=['progress','updated_at'])
                        staged.add(candidate.pk)
                    photo.refresh_from_db()
                failed_photo_id=photo.pk
                check()
                if not job.requested_by_id:
                    raise ValueError('Requesting user no longer has access.')
                job.requested_by.refresh_from_db()
                if not job.requested_by.is_active:
                    raise ValueError('Requesting user no longer has access.')
                access=survey_access(SimpleNamespace(user=job.requested_by),job.checklist_id,edit=True)
                if photo.checklist_id!=job.checklist_id or access['checklist'].schema_snapshot!=job.schema:
                    raise ValueError('Photo or checklist schema no longer matches this job.')
                photo_started=time.monotonic()
                def report_stage(stage,cache_reused=False):
                    from .photo_metadata import MATCHER_VERSION
                    check()
                    job.progress={**job.progress,'stage':stage,'matcher_version':MATCHER_VERSION,'matched_photo_ids':job.progress.get('matched_photo_ids',[]) if job.progress.get('matcher_version')==MATCHER_VERSION else [],'photo_id':photo.pk,'cache_reused':bool(cache_reused),'started_at':timezone.now().isoformat()}
                    job.save(update_fields=['progress','updated_at'])
                options={'lease_check':check,'progress_callback':report_stage}
                if job.progress.get('evidence_context'):
                    options['evidence_context']=job.progress['evidence_context']
                proposals = analyze_photo(photo, job.schema, job.model, **options)
                check()
                with transaction.atomic():
                    from .governance_views import lock_governance
                    from django.contrib.auth.models import User
                    lock_governance(job.requested_by)
                    requester=User.objects.select_related('profile','profile__project').get(pk=job.requested_by_id)
                    latest=survey_access(SimpleNamespace(user=requester),job.checklist_id,edit=True)['checklist']
                    if latest.schema_snapshot!=job.schema:
                        raise ValueError('Checklist schema changed during analysis.')
                    job.checklist=latest
                    check()
                    for proposal in proposals:
                        fid=proposal['field_id']
                        PhotoDraft.objects.create(job=job,photo=photo,field_id=fid,label=fields[fid]['label'],value=proposal.get('value'),reason=proposal['reason'],uncertainty=proposal['uncertainty'],missing_information=proposal['missing_information'],anomalies=proposal.get('anomalies',[]),baseline=job.baseline.get(fid),baseline_present=fid in job.baseline)
                    from .field_photo_service import record_proposals
                    record_proposals(job,photo,proposals)
                    job.processed_photo_ids.append(photo.pk)
                    job.completed=len(job.processed_photo_ids)
                    attempt_completed+=1
                    from .photo_metadata import MATCHER_VERSION
                    matched_ids=job.progress.get('matched_photo_ids',[]) if job.progress.get('matcher_version')==MATCHER_VERSION else []
                    average=(time.monotonic()-attempt_started)/attempt_completed
                    job.progress={**job.progress,'matcher_version':MATCHER_VERSION,'matched_photo_ids':sorted(set(matched_ids)|{photo.pk}),'stage':'matching_checklist','last_photo_seconds':round(time.monotonic()-photo_started,3),'average_seconds':round(average,3),'photos_per_minute':round(60/average,2) if average>0 else 0}
                    job.save(update_fields=['processed_photo_ids','completed','progress','updated_at'])
            with transaction.atomic():
                check()
                job.status='completed'
                job.progress={**job.progress,'stage':'completed'}
                job.save(update_fields=['status','progress','updated_at'])
        except Exception as exc:
            try:
                check()
            except RuntimeError:
                # Another owner may already be recovering this job. Do not alter it.
                return True
            job.status='failed'
            job.progress={**job.progress,'stage':'failed'}
            # Only controlled diagnostics may be exposed; no model text or images.
            from .photo_service import PhotoProcessingError
            if isinstance(exc,PhotoProcessingError):
                job.error=f'Photo {failed_photo_id}, catalog batch {exc.batch_index} [{exc.code}]: {exc.safe_message}'
            else:
                from django.core.exceptions import ValidationError
                if isinstance(exc,ValidationError):
                    job.error='Photo '+str(failed_photo_id)+': '+'; '.join(exc.messages)[:1000]
                else:
                    job.error='Photo processing failed ('+type(exc).__name__+'). Check the local model and retry. Original photos and approval controls were preserved.'
            job.save(update_fields=['status','error','progress','updated_at'])
        return True
