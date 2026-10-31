"""Versioned, outbound-only compute bridge for the existing survey pipeline.

Workers can return proposals, never answers, decisions, approvals or file paths.
All authority, immutable evidence, checkpoints and drawing rendering stay in Django.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import uuid
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from pydantic import ValidationError as SchemaError

from . import survey_evidence as evidence, survey_processing as pipeline
from .access import can_access_project, company_id_for, role_for
from .models import GovernanceAudit, Profile, Project
from .remote_worker_models import RemoteWorkerCredential, RemoteWorkerProject, RemoteSurveyLease, RemoteSurveyTask
from .survey_processing_models import SurveyProcessingJob, SurveyProcessingResult, SurveySourceAnalysis,SurveyProcessingEvent

PROTOCOL = 'isurvix-survey-worker-v1'
LEASE_SECONDS = 600


def versions():
    from . import survey_checklist_mapping as mapping, measurement_units, pdf_tools, local_evidence_tools
    # Windows Git checkouts may use CRLF while the VPS checkout uses LF. Their
    # reviewed Python implementation is identical; transport compatibility must
    # not depend on the operating system's checkout line-ending convention.
    # Numeric reconciliation also depends on the shared unit vocabulary. Pin
    # that source so a helper-only semantic change cannot mix PC/server releases.
    source = b''.join(Path(module.__file__).read_bytes().replace(b'\r\n', b'\n')
                      for module in (evidence, mapping, measurement_units, pdf_tools, local_evidence_tools))
    return {'protocol': PROTOCOL, 'pipeline': pipeline.PIPELINE_VERSION,
            'evidence': evidence.EXTRACTION_VERSION, 'mapping': mapping.VERSION,
            'implementation': hashlib.sha256(source).hexdigest()}


def _audit(credential, action, project=None, **details):
    GovernanceAudit.objects.create(actor=credential.created_by, actor_name=credential.created_by.get_username(),
        action='remote_worker.' + action, project=project, details={'credential_id': str(credential.pk), **details})


def provision(admin, projects, label='Local survey PC', hours=720):
    admin = get_user_model().objects.select_related('profile').get(pk=admin.pk)
    requested_ids = set(projects)
    projects = list(Project.objects.filter(pk__in=requested_ids))
    if requested_ids != {project.pk for project in projects}:
        raise PermissionDenied('Every requested project must exist within the current Admin scope.')
    company_id = company_id_for(admin)
    if (role_for(admin) != Profile.Roles.ADMIN or company_id is None or not projects
            or any(p.company_id != company_id or p.administrator_id != admin.pk
                   or not can_access_project(admin, p.pk) for p in projects)):
        raise PermissionDenied('Only the current project Admin may provision that project worker.')
    if not 1 <= hours <= 2160:
        raise ValidationError('Worker credentials must expire within 1 to 2160 hours.')
    secret = secrets.token_urlsafe(48)
    with transaction.atomic():
        credential = RemoteWorkerCredential.objects.create(label=str(label)[:100], created_by=admin,
            issuing_company_id=company_id,
            secret_hash=hashlib.sha256(secret.encode()).hexdigest(), expires_at=timezone.now() + timedelta(hours=hours))
        credential.projects.set(projects)
        for project in projects:
            RemoteWorkerProject.objects.update_or_create(project=project, defaults={'enabled': True})
            _audit(credential, 'provisioned', project, company_id=company_id)
    return credential, credential.pk.hex + '.' + secret


def revoke(admin, credential_id):
    credential = RemoteWorkerCredential.objects.select_related('created_by').get(pk=credential_id)
    if credential.created_by_id != admin.pk or role_for(admin) != Profile.Roles.ADMIN:
        raise PermissionDenied('Only the provisioning project Admin may revoke this worker.')
    if credential.revoked_at is None:
        credential.revoked_at = timezone.now()
        credential.save(update_fields=['revoked_at'])
        _audit(credential, 'revoked')
    return credential


def authenticate(token):
    try:
        identifier, secret = token.split('.', 1)
        if len(secret) > 128:
            raise ValueError()
        credential = RemoteWorkerCredential.objects.select_related('created_by__profile').get(pk=uuid.UUID(identifier))
    except (ValueError, AttributeError, RemoteWorkerCredential.DoesNotExist):
        raise PermissionDenied('Worker credentials are invalid or expired.')
    if (not hmac.compare_digest(credential.secret_hash, hashlib.sha256(secret.encode()).hexdigest())
            or credential.revoked_at or credential.expires_at <= timezone.now()
            or role_for(credential.created_by) != Profile.Roles.ADMIN
            or credential.issuing_company_id is None
            or company_id_for(credential.created_by) != credential.issuing_company_id):
        raise PermissionDenied('Worker credentials are invalid or expired.')
    RemoteWorkerCredential.objects.filter(pk=credential.pk).update(last_seen_at=timezone.now())
    return credential


def _projects(credential):
    # Re-read a retained service object as well as browser/machine authentication:
    # in-flight callers cannot inherit a changed account/company or revoked token.
    current = RemoteWorkerCredential.objects.select_related('created_by__profile').filter(pk=credential.pk).first()
    if (current is None or current.revoked_at or current.expires_at <= timezone.now()
            or current.issuing_company_id is None or role_for(current.created_by) != Profile.Roles.ADMIN
            or company_id_for(current.created_by) != current.issuing_company_id):
        raise PermissionDenied('Worker credentials are invalid or expired.')
    return [p.pk for p in current.projects.filter(remote_worker_configuration__enabled=True,
            company_id=current.issuing_company_id, administrator_id=current.created_by_id)
            if can_access_project(current.created_by, p.pk)]


def _compatible(payload):
    if payload.get('versions') != versions():
        raise ValidationError('Worker software is incompatible. Update the PC and server to the same reviewed release.')


def _lock(credential, job_id, token, guard=True):
    job = SurveyProcessingJob.objects.select_for_update().select_related('revision__checklist').get(pk=job_id)
    lease = RemoteSurveyLease.objects.select_for_update().get(job=job)
    if (job.revision.checklist.project_id not in _projects(credential) or lease.credential_id != credential.pk
            or str(lease.token) != str(token) or job.lease_owner != 'remote:' + lease.token.hex
            or not job.lease_until or job.lease_until <= timezone.now() or job.status not in pipeline.ACTIVE | {'pausing'}):
        raise PermissionDenied('This worker lease is inactive, expired or outside its project scope.')
    if lease.versions != versions():
        raise ValidationError('This saved job is pinned to another reviewed worker release. Restore the matching release before resuming its checkpoints.')
    if guard:
        from .ai_processing_service import configured
        if configured(job):
            raise ValidationError('This job uses a configured AI policy. The current PC worker cannot execute that policy; keep its evidence queued for the policy-aware server worker.')
        pipeline.worker_guard(job.revision)
    return job, lease


def _extend(job, lease):
    job.lease_until = timezone.now() + timedelta(seconds=LEASE_SECONDS)
    job.save(update_fields=['lease_until', 'updated_at'])
    lease.heartbeat_at = timezone.now()
    lease.save(update_fields=['heartbeat_at'])


def claim(credential, payload):
    _compatible(payload)
    from .survey_pause import settle_expired
    settle_expired(_projects(credential))
    if payload.get('model') != getattr(settings, 'OLLAMA_MODEL', 'qwen3.5:4b') or not isinstance(payload.get('model_digest'), str) or not re.fullmatch(r'[a-f0-9]{64}', payload['model_digest']):
        raise ValidationError('The installed local vision model does not match the server model requirement.')
    proof=payload.get('model_identity')
    if proof is not None:
        from .survey_model_identity import VERSION
        if (not isinstance(proof,dict) or proof.get('version')!=VERSION or proof.get('model')!=payload['model']
            or any(not isinstance(proof.get(key),str) or not re.fullmatch(r'[a-f0-9]{64}',proof[key])
                for key in ['manifest_digest','fingerprint','legacy_fingerprint'])
            or proof['fingerprint']!=payload['model_digest']
            or pipeline.digest({'version':VERSION,'model':payload['model'],'manifest_digest':proof['manifest_digest'],
                'pipeline':pipeline.PIPELINE_VERSION})!=proof['fingerprint']):
            raise ValidationError('The worker model identity proof is invalid or incompatible.')
    now = timezone.now()
    with transaction.atomic():
        candidates = SurveyProcessingJob.objects.select_for_update().select_related('revision__checklist__project').filter(
            Q(status='queued') | Q(status__in=pipeline.ACTIVE, lease_until__lt=now) | Q(status__in=pipeline.ACTIVE, lease_until__isnull=True),
            revision__checklist__project_id__in=_projects(credential)).order_by('pk')
        from .ai_processing_service import configured
        job = None
        for candidate in candidates:
            if configured(candidate):
                message = 'This job uses a configured AI policy. The current PC worker cannot execute that policy; use the policy-aware server worker. Saved evidence remains queued.'
                if candidate.error != message:
                    candidate.error = message
                    candidate.save(update_fields=['error', 'updated_at'])
                continue
            job = candidate
            break
        if job is None:
            return None
        try:
            pipeline.worker_guard(job.revision)
        except ValidationError:
            job.status, job.error, job.lease_owner, job.lease_until = 'failed', 'The original submitter no longer has this survey assignment. Preserve this revision and submit the current assigned Engineer inputs.', '', None
            job.save()
            _audit(credential, 'failed', job.revision.checklist.project, job_id=job.pk, code='submitter_assignment')
            return None
        if job.pipeline_version != pipeline.PIPELINE_VERSION or job.model != payload['model']:
            raise ValidationError('This queued job uses an incompatible pipeline or model.')
        previous_pin=job.model_digest
        migrated=bool(previous_pin and previous_pin!=payload['model_digest'])
        if migrated and (not proof or previous_pin!=proof['legacy_fingerprint']):
            raise ValidationError('The pinned model changed. Restore the original installed model before resuming this revision.')
        lease, _ = RemoteSurveyLease.objects.get_or_create(job=job)
        if lease.versions and lease.versions != versions():
            raise ValidationError('The saved checkpoints belong to another reviewed worker release. Restore that release before resuming this revision.')
        lease.versions = versions()
        lease.credential, lease.token, lease.heartbeat_at = credential, uuid.uuid4(), now
        lease.save()
        job.model_digest, job.status, job.error = payload['model_digest'], 'analysing_evidence', ''
        job.lease_owner, job.lease_until = 'remote:' + lease.token.hex, now + timedelta(seconds=LEASE_SECONDS)
        job.attempts += 1
        job.save()
        if proof and previous_pin!=payload['model_digest']:
            SurveyProcessingEvent.objects.create(revision=job.revision,actor=credential.created_by,
                action='model_identity_migrated' if migrated else 'model_identity',payload={**proof,
                    'previous_model_digest':previous_pin,'proof':'exact_legacy_metadata_match' if migrated else 'installed_manifest',
                    'credential_id':str(credential.pk),'origin':'authenticated_local_worker'})
            _audit(credential,'model_identity_migrated' if migrated else 'model_identity',job.revision.checklist.project,
                job_id=job.pk,previous_model_digest=previous_pin,manifest_digest=proof['manifest_digest'],
                fingerprint=proof['fingerprint'],proof='exact_legacy_metadata_match' if migrated else 'installed_manifest')
        _audit(credential, 'claimed', job.revision.checklist.project, job_id=job.pk, revision_id=job.revision_id)
    return {'job_id': job.pk, 'lease': str(lease.token), 'revision_id': job.revision_id,
            'snapshot_digest': job.revision.digest, 'lease_seconds': LEASE_SECONDS, 'model': job.model}


def heartbeat(credential, job_id, token):
    with transaction.atomic():
        job, lease = _lock(credential, job_id, token)
        _extend(job, lease)
    return {'status': job.status, 'lease_seconds': LEASE_SECONDS}


def _prepare_sources(job, lease):
    if lease.sources_prepared:
        return
    snapshot = job.revision.snapshot
    catalog = [{key: field[key] for key in ('id', 'label', 'type') if key in field}
               for section in snapshot['schema']['sections'] for field in section['fields']]
    if len(catalog) > 40 or len(json.dumps(catalog, ensure_ascii=False)) > 12000:
        catalog = []
    def records(values):
        return [{**entry, 'path': default_storage.path(entry['original'])} for entry in values]
    count = 0
    for source in evidence.extract_sources(records(snapshot['photos']), records(snapshot['documents'])):
        count += 1
        source['field_catalog'] = catalog
        image = source.pop('image_b64', '')
        task, created = RemoteSurveyTask.objects.get_or_create(job=job, key=source['source_id'], defaults={'kind': 'source', 'payload': source})
        # An interrupted transfer/preparation may have created the row before its
        # normalized image. Recreate only the separate inference copy, never originals.
        if image and (not task.image or not default_storage.exists(task.image.name)):
            raw = base64.b64decode(image, validate=True)
            task.image.save(f'{job.pk}-{pipeline.digest(source["source_id"])}.jpg', ContentFile(raw), save=False)
            task.image_sha256, task.image_size = hashlib.sha256(raw).hexdigest(), len(raw)
            task.save(update_fields=['image', 'image_sha256', 'image_size'])
        cached = job.revision.source_analyses.filter(source_id=task.key).first()
        if cached and not task.completed_digest:
            if pipeline.digest(cached.payload) != cached.digest:
                raise ValidationError('Saved source analysis failed integrity verification.')
            task.completed_digest = cached.digest
            task.save(update_fields=['completed_digest'])
        if count % 20 == 0:
            _extend(job, lease)
    lease.sources_prepared = True
    lease.save(update_fields=['sources_prepared'])
    job.total = count
    job.completed = job.remote_tasks.filter(kind='source').exclude(completed_digest='').count()
    job.save(update_fields=['total', 'completed', 'updated_at'])


def _analyses(job):
    result = []
    for saved in job.revision.source_analyses.exclude(source_id__startswith='mapping:').order_by('source_id'):
        if pipeline.digest(saved.payload) != saved.digest:
            raise ValidationError('Saved source analysis failed integrity verification.')
        result.append(saved.payload)
    return result


def _prepare_mapping(job, lease):
    if lease.mapping_prepared:
        return
    from .survey_checklist_mapping import mapping_batches
    analyses = _analyses(job)
    if any(not finding.get('field_hint') for source in analyses for finding in source.get('findings', [])):
        for batch in mapping_batches(analyses, job.revision.snapshot['schema']):
            task, _ = RemoteSurveyTask.objects.get_or_create(job=job, key=batch['key'], defaults={'kind': 'mapping', 'payload': batch})
            cached = job.revision.source_analyses.filter(source_id=task.key).first()
            if cached and not task.completed_digest:
                from .survey_checklist_mapping import binding_identity
                if (pipeline.digest(cached.payload) != cached.digest or cached.payload.get('batch_identity') != batch['identity']
                        or cached.payload.get('identity') != binding_identity(batch, job.model)):
                    raise ValidationError('Saved checklist mapping is incompatible with this immutable task.')
                task.completed_digest = cached.digest
                task.save(update_fields=['completed_digest'])
    lease.mapping_prepared = True
    lease.save(update_fields=['mapping_prepared'])


def _finish(job, lease, credential):
    analyses = deepcopy(_analyses(job))
    bindings, unassigned = {}, set()
    for task in job.remote_tasks.filter(kind='mapping'):
        saved = job.revision.source_analyses.get(source_id=task.key)
        if pipeline.digest(saved.payload) != saved.digest:
            raise ValidationError('Saved mapping failed integrity verification.')
        bindings.update({entry['finding_key']: entry for entry in saved.payload['bindings']})
        unassigned.update(saved.payload['unassigned'])
    for analysis in analyses:
        for finding in analysis.get('findings', []):
            binding = bindings.get(finding['finding_key'])
            if binding:
                finding.update(field_hint=binding['field_id'], mapping_reason=binding['reason'])
            elif finding['finding_key'] in unassigned:
                finding['mapping_unassigned'] = True
    payload = pipeline.prepare_checklist(job.revision.snapshot, evidence.reconcile_results(analyses))
    result, _ = SurveyProcessingResult.objects.get_or_create(revision=job.revision, defaults={'payload': payload, 'digest': pipeline.digest(payload)})
    if pipeline.digest(result.payload) != result.digest:
        raise ValidationError('Saved processing output failed integrity verification.')
    job.status = 'preparing_drawings'
    job.save(update_fields=['status', 'updated_at'])
    pipeline.render_drawing_set(job.revision, result.payload)
    job.status, job.lease_owner, job.lease_until, job.error = 'ready_for_review', '', None, ''
    job.save()
    _audit(credential, 'completed', job.revision.checklist.project, job_id=job.pk, revision_id=job.revision_id)


def next_task(credential, job_id, token):
    with transaction.atomic():
        job, lease = _lock(credential, job_id, token)
        if job.status == 'pausing':
            from .survey_pause import _paused
            _paused(job)
            return {'complete': True, 'status': 'paused'}
        _extend(job, lease)
        _prepare_sources(job, lease)
        task = job.remote_tasks.filter(kind='source', completed_digest='').first()
        if task is None:
            job.status = 'preparing_checklist'
            job.save(update_fields=['status', 'updated_at'])
            _prepare_mapping(job, lease)
            task = job.remote_tasks.filter(kind='mapping', completed_digest='').first()
        if task is None:
            _finish(job, lease, credential)
            return {'complete': True, 'status': job.status}
        return {'complete': False, 'task_id': task.pk, 'kind': task.kind, 'input': task.payload,
                'input_digest': pipeline.digest(task.payload), 'image_sha256': task.image_sha256, 'image_size': task.image_size,
                'versions': versions(), 'model': job.model}


def image_input(credential, job_id, token, task_id):
    with transaction.atomic():
        job, lease = _lock(credential, job_id, token)
        task = RemoteSurveyTask.objects.get(pk=task_id, job=job)
        if not task.image or not task.image_sha256:
            raise ValidationError('This task has no normalized image input.')
        with task.image.open('rb') as handle:
            if hashlib.file_digest(handle, 'sha256').hexdigest() != task.image_sha256:
                raise ValidationError('Normalized worker input failed integrity verification.')
        _extend(job, lease)
        return task


def _validate_source(task, raw, model):
    if not isinstance(raw, dict) or raw.get('source_id') != task.key or raw.get('sha256') != task.payload['sha256'] or raw.get('model') != model:
        raise ValidationError('The returned evidence does not match this immutable source and model.')
    fields = set(evidence.Observation.model_fields)
    try:
        # The native normalizer may append one missing-information note per
        # withheld observation, beyond the model's 20 raw-note bound.
        missing_notes = raw.get('missing', [])
        if not isinstance(missing_notes, list) or len(missing_notes) > 64 or any(not isinstance(note, str) or not note.strip() or len(note) > 1000 for note in missing_notes):
            raise ValueError('Invalid normalized missing-information notes.')
        parsed = evidence.EvidenceResponse.model_validate({key: ([{k: v for k, v in item.items() if k in fields} for item in raw.get(key, [])]
            if key == 'findings' else [] if key == 'missing' else raw.get(key, [])) for key in ('findings', 'missing', 'conflicts', 'suggested_items')})
    except (SchemaError, ValueError, TypeError, AttributeError) as exc:
        raise ValidationError('The worker returned malformed structured evidence.') from exc
    allowed = {field['id'] for field in task.payload.get('field_catalog', [])}
    findings, missing = [], list(missing_notes)
    for index, observation in enumerate(parsed.findings, 1):
        item = observation.model_dump()
        if item['field_hint'] not in allowed:
            item['field_hint'] = ''
        if item['category'] in {'measurement', 'coordinate'}:
            recorded = item['basis'] == 'recorded' and bool(item['evidence_quote'].strip()) and (item['category'] != 'measurement' or bool(item['unit'].strip()))
            if not recorded:
                item['value'], item['confidence'] = None, 'low'
                missing.append('An unsupported dimension or coordinate was withheld; supply an explicit recorded value and unit/reference.')
            item['recorded_measurement'] = bool(recorded)
        item.update(source_id=task.key, source_type=task.payload.get('source_type', ''), reference=task.payload.get('reference', ''),
                    finding_key=f'{task.key}:finding:{index}', verification_status='needs_review', measured=False)
        findings.append(item)
    local_ocr = {}
    if 'local_ocr' in raw:
        from .pdf_tools import canonical_ocr_report
        if (task.payload.get('source_type') != 'pdf_page' or str(task.payload.get('text', '')).strip()
                or not task.image):
            raise ValidationError('Local OCR must refer to an image-only PDF page from this immutable task.')
        try:
            local_ocr = {'local_ocr': canonical_ocr_report(raw['local_ocr'])}
        except ValueError:
            raise ValidationError('The worker returned malformed local OCR evidence.') from None
    return {'source_id': task.key, 'source_type': task.payload.get('source_type', ''), 'reference': task.payload.get('reference', ''),
            'sha256': task.payload['sha256'], 'model': model, 'verification_status': 'needs_review',
            'findings': findings, 'missing': list(dict.fromkeys(missing)), 'conflicts': parsed.conflicts, 'suggested_items': parsed.suggested_items,
            **({'preview_file': task.image.name} if task.image else {}), **local_ocr}


def _validate_mapping(task, raw, model):
    from .survey_checklist_mapping import (MappingResponse, binding_identity, _with_candidates,
        partial_mapping_context, with_partial_mapping_context)
    try:
        parsed = MappingResponse.model_validate({'bindings': [{key: value for key, value in entry.items() if key in {'finding_key', 'field_id', 'reason'}}
            for entry in raw.get('bindings', [])], 'unassigned': raw.get('unassigned', [])})
    except (SchemaError, TypeError, AttributeError) as exc:
        raise ValidationError('The worker returned invalid checklist bindings.') from exc
    keys = {entry['finding_key'] for entry in task.payload['findings']}
    fields = {entry['id'] for entry in task.payload['catalog']}
    bound = [entry.finding_key for entry in parsed.bindings]
    if (len(bound) != len(set(bound)) or any(entry.finding_key not in keys or entry.field_id not in fields for entry in parsed.bindings)
            or len(parsed.unassigned) != len(set(parsed.unassigned)) or set(parsed.unassigned) & set(bound) or not set(parsed.unassigned) <= keys):
        raise ValidationError('A returned checklist binding is unknown, repeated or contradictory.')
    result = {'bindings': [{**entry.model_dump(), 'verification_status': 'needs_review', 'status': 'proposed'} for entry in parsed.bindings],
            'unassigned': sorted(keys - set(bound)), 'identity': binding_identity(task.payload, model),
            'batch_identity': task.payload['identity'], 'status': 'proposed',
            'ranking_method': task.payload.get('ranking_method'), 'notice': task.payload.get('notice', '')}
    # The remote client cannot supply a trusted read-projection receipt. Derive
    # it here from the immutable server task, saved sources and actual job pin.
    job = task.job
    context = partial_mapping_context(_analyses(job), job.revision.snapshot['schema'], model, job.model_digest)
    return with_partial_mapping_context(task.payload, _with_candidates(task.payload, result), context)


def complete_task(credential, job_id, token, task_id, payload):
    _compatible(payload)
    with transaction.atomic():
        job, lease = _lock(credential, job_id, token)
        task = RemoteSurveyTask.objects.select_for_update().get(pk=task_id, job=job)
        if payload.get('input_digest') != pipeline.digest(task.payload):
            raise ValidationError('The result was produced for a different immutable task input.')
        result = _validate_source(task, payload.get('result'), job.model) if task.kind == 'source' else _validate_mapping(task, payload.get('result'), job.model)
        signature = pipeline.digest(result)
        saved = job.revision.source_analyses.filter(source_id=task.key).first()
        if saved and (saved.digest != signature or pipeline.digest(saved.payload) != saved.digest):
            raise ValidationError('This task already has a different immutable result; no checkpoint was replaced.')
        if not saved:
            SurveySourceAnalysis.objects.create(revision=job.revision, source_id=task.key, payload=result, digest=signature)
        task.completed_digest = signature
        task.save(update_fields=['completed_digest'])
        job.completed = job.remote_tasks.filter(kind='source').exclude(completed_digest='').count()
        job.save(update_fields=['completed', 'updated_at'])
        _extend(job, lease)
        return {'accepted': True, 'duplicate': bool(saved), 'completed': job.completed, 'total': job.total}


def fail(credential, job_id, token, code, retryable=False):
    messages = {'local_unavailable': 'The local PC model is unavailable. Completed evidence is preserved; start Ollama and retry.',
        'invalid_response': 'The local model returned invalid structured evidence. Completed evidence is preserved; retry after checking the worker.',
        'local_busy': 'The local PC is busy. The queued job will resume automatically.',
        'input_transfer': 'The worker input transfer was interrupted. The queued job will resume from saved checkpoints.'}
    if code not in messages or type(retryable) is not bool:
        raise ValidationError('Use a supported, credential-free worker failure code.')
    with transaction.atomic():
        job, lease = _lock(credential, job_id, token)
        job.status, job.error = ('paused' if job.status == 'pausing' else 'queued' if retryable else 'failed'), messages[code]
        job.lease_owner, job.lease_until = '', None
        job.save()
        _audit(credential, 'interrupted' if retryable else 'failed', job.revision.checklist.project, job_id=job.pk, code=code)
    return {'status': job.status, 'message': job.error}


def preparation_failure(credential, job_id, token):
    """Turn a server input/render failure into an explicit recoverable job state."""
    try:
        with transaction.atomic():
            job, lease = _lock(credential, job_id, token, guard=False)
            job.status = 'paused' if job.status == 'pausing' else 'failed'
            job.error = 'Server evidence preparation or drawing generation failed. Saved source checkpoints and originals are preserved; check server storage/logs, then retry.'
            job.lease_owner, job.lease_until = '', None
            job.save()
            _audit(credential, 'failed', job.revision.checklist.project, job_id=job.pk, code='server_preparation')
    except (PermissionDenied, ValidationError, SurveyProcessingJob.DoesNotExist, RemoteSurveyLease.DoesNotExist):
        # Revoked/reassigned/expired jobs cannot be altered by the old worker.
        return
