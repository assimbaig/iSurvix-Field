"""One cross-process, expiring inference lease for text chat and photo workers."""
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
def inference_lease():
    owner = uuid.uuid4().hex
    now = timezone.now()
    with transaction.atomic():
        PhotoWorkerLease.objects.get_or_create(key='inference', defaults={'owner':'', 'expires_at':now})
        acquired = PhotoWorkerLease.objects.filter(key='inference', expires_at__lte=now).update(owner=owner, expires_at=now+timedelta(seconds=lease_seconds()))
    if not acquired:
        raise InferenceBusy('The local inference queue is busy.')
    stop = threading.Event()
    lost = threading.Event()
    def heartbeat():
        close_old_connections()
        try:
            while not stop.wait(15):
                try:
                    if not PhotoWorkerLease.objects.filter(key='inference', owner=owner).update(expires_at=timezone.now()+timedelta(seconds=lease_seconds())):
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
        if lost.is_set() or not PhotoWorkerLease.objects.filter(key='inference', owner=owner, expires_at__gt=timezone.now()).exists():
            raise RuntimeError('Inference lease expired; results were discarded.')
    try:
        yield check
    finally:
        stop.set()
        thread.join(timeout=20)
        PhotoWorkerLease.objects.filter(key='inference', owner=owner).update(expires_at=timezone.now())


def process_next():
    # Idle polling must stay read-only: acquiring a lease would otherwise write
    # twice and start a heartbeat thread every two seconds without any work.
    if not PhotoJob.objects.filter(status__in=['queued','running']).exists():
        return False
    from .photo_service import analyze_photo
    from .template_views import survey_access
    with inference_lease() as check:
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
            attempt_started=time.monotonic()
            attempt_completed=0
            fields = {f['id']: f for section in job.schema['sections'] for f in section['fields']}
            for photo in job.photos.order_by('pk'):
                if photo.pk in job.processed_photo_ids:
                    continue
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
                    check()
                    job.progress={**job.progress,'stage':stage,'photo_id':photo.pk,'cache_reused':bool(cache_reused),'started_at':timezone.now().isoformat()}
                    job.save(update_fields=['progress','updated_at'])
                proposals = analyze_photo(photo, job.schema, job.model, lease_check=check,progress_callback=report_stage)
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
                    job.progress={**job.progress,'stage':'matching_checklist','last_photo_seconds':round(time.monotonic()-photo_started,3),'average_seconds':round((time.monotonic()-attempt_started)/attempt_completed,3)}
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
                job.error=f'Photo {photo.pk}, catalog batch {exc.batch_index} [{exc.code}]: {exc.safe_message}'
            else:
                job.error='Photo processing failed ('+type(exc).__name__+'). Check the local model and retry. Original photos and approval controls were preserved.'
            job.save(update_fields=['status','error','progress','updated_at'])
        return True
