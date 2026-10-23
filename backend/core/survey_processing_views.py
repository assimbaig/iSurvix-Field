"""Authenticated saved-survey processing workspace and private revision assets."""
import json
import uuid
from copy import deepcopy
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import F, Max
from django.core.paginator import Paginator
from django.http import JsonResponse, FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from . import survey_processing as pipeline
from . import survey_upload_sessions as uploads
from .models import Checklist
from .survey_processing_models import (SurveyDocument, SurveyUploadSession, SurveyProcessingRevision,
    SurveyProcessingResult, SurveyDrawingSet)


def private(response):
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


def guarded(fn):
    @wraps(fn)
    def call(*args, **kwargs):
        try:
            return private(fn(*args, **kwargs))
        except ValidationError as exc:
            return private(JsonResponse({'error': '; '.join(exc.messages)}, status=409))
        except (ValueError, TypeError, KeyError):
            return private(JsonResponse({'error': 'Invalid processing request.'}, status=400))
        except OSError:
            return private(JsonResponse({'error': 'Local storage is unavailable. Saved inputs are preserved.'}, status=503))
    return call


def source_link(revision, source):
    ident = source.get('source_id', '')
    result = {**source, 'label': source.get('reference') or ident}
    if ident.startswith('photo:'):
        try:
            number = int(ident.split(':')[1])
        except ValueError:
            return result
        if any(p['id'] == number for p in revision.snapshot['photos']):
            result['url'] = reverse('photo_evidence', args=[revision.checklist_id, number, 'original'])
            result['thumbnail_url'] = reverse('photo_evidence', args=[revision.checklist_id, number, 'preview'])
    elif ident.startswith('document:'):
        try:
            number = int(ident.split(':')[1])
        except ValueError:
            return result
        if any(d['id'] == number for d in revision.snapshot['documents']):
            result['url'] = reverse('survey_processing_document', args=[revision.checklist_id, number])
    cache = getattr(revision, '_source_cache', None)
    saved = cache.get(ident) if cache is not None else revision.source_analyses.filter(source_id=ident).first()
    if saved and saved.payload.get('preview_file'):
        result['thumbnail_url'] = reverse('survey_processing_source', args=[revision.checklist_id, saved.pk])
    return result


def _page(query, number, size):
    page = Paginator(query, size).get_page(number)
    return page.object_list, {'page': page.number, 'total_pages': page.paginator.num_pages, 'total': page.paginator.count}


def _summary(row):
    return {'id': row['id'], 'revision': row['number'], 'status': row['processing_job__status'],
        'label': pipeline.STAGES.get(row['processing_job__status'], row['processing_job__status']),
        'completed': row['processing_job__completed'], 'total': row['processing_job__total'],
        'error': row['processing_job__error'], 'created_at': row['created_at'].isoformat(), 'detailed': False}


def _summaries(c):
    return c.processing_revisions.values('id', 'number', 'created_at', 'processing_job__status',
        'processing_job__completed', 'processing_job__total', 'processing_job__error').order_by('-number')


def _detail_token(c, latest):
    # A photo-count tick should never trigger a reload of evidence and history.
    events = c.processing_revisions.aggregate(last_event=Max('processing_events__pk'))
    outputs = c.processing_revisions.aggregate(last_output=Max('drawing_sets__pk'))
    return pipeline.digest({'updated': str(c.updated_at), 'latest': latest and latest['id'],
        'stage': latest and latest['status'], **events, **outputs})


def serialize(request, checklist_id, compact=False):
    c, flags = pipeline.access(request, checklist_id)
    current_digest = pipeline.digest(pipeline.freeze_data(c))
    revisions, pagination = [], {}
    queryset = c.processing_revisions.select_related('processing_job', 'processing_result', 'submitted_by')
    selected_id = None
    section = request.GET.get('section') if compact else None
    if section and section not in {'findings', 'events', 'drawings'}:
        raise ValidationError('Unknown processing detail section.')
    if compact and not flags['is_client']:
        summaries, pagination['history'] = _page(_summaries(c), request.GET.get('history_page', 1), 25)
        revisions = [_summary(row) for row in summaries]
        selected_id = request.GET.get('revision_id') or (revisions[0]['id'] if revisions else None)
        if selected_id:
            selected = get_object_or_404(queryset, pk=selected_id)
            selected_id = selected.pk
            queryset = [selected]
        else:
            queryset = []
    for revision in queryset:
        job = revision.processing_job
        is_current = pipeline.matches_revision(revision, current_digest)
        if compact:
            revision._source_cache = {a['source_id']: SimpleNamespace(pk=a['pk'], source_id=a['source_id'],
                payload={'reference': a['reference'], 'preview_file': a['preview_file']})
                for a in revision.source_analyses.exclude(source_id__startswith='mapping:').values('pk', 'source_id',
                    reference=F('payload__reference'), preview_file=F('payload__preview_file'))}
        else:
            revision._source_cache = {a.source_id: a for a in revision.source_analyses.all() if not a.source_id.startswith('mapping:')}
        if flags['is_client'] and (not is_current or not revision.drawing_sets.filter(released=True).exists()):
            continue
        data = {'id': revision.pk, 'revision': revision.number, 'status': job.status,
            'label': pipeline.STAGES.get(job.status, job.status), 'current': is_current,
            'completed': job.completed, 'total': job.total, 'error': job.error,
            'created_at': revision.created_at.isoformat(), 'findings': [], 'checklist_items': [],
            'missing': [], 'conflicts': [], 'drawings': [], 'events': [], 'sources': [], 'drawing_records': [],
            'can_release': False, 'release_blocker': 'Processing must finish first.', 'detailed': True}
        from .category_intake import revision_enabled
        has_result=hasattr(revision,'processing_result')
        if has_result or revision_enabled(revision):
            payload = pipeline.reviewed_payload(revision)
            data.update(deepcopy(payload))
            originals = {f.get('finding_key'): f for f in revision.processing_result.payload.get('findings', [])} if has_result else {}
            for item in data['checklist_items']:
                from .template_views import field_is_locked
                item['locked'] = field_is_locked(c, item['id'])
                item['sources'] = [source_link(revision, src) for src in item.get('sources', [])]
            data['sources'] = [source_link(revision, {'source_id': a.source_id, 'reference': a.payload.get('reference', '')}) for a in revision._source_cache.values()]
            if compact:
                data['pagination'] = {}
                data['findings'], data['pagination']['findings'] = _page(data['findings'],
                    request.GET.get('page', 1) if section == 'findings' else 1, 50)
            for finding in data['findings']:
                original = originals.get(finding.get('finding_key'), {})
                finding['original_value'] = original.get('value')
                finding['original_unit'] = original.get('unit', '')
                finding['sources'] = [source_link(revision, finding)]
            signature = pipeline.review_digest(payload)
            data['release_blocker'] = pipeline.release_gate(revision, payload) if is_current else 'This is a previous input revision. Release the current revision only.'
            data['can_release'] = bool(flags['can_release'] and is_current and not data['release_blocker'])
            data['engineer_complete'] = revision.processing_events.filter(action='engineer_complete', payload__review_digest=signature).exists()
            data['technical_approved'] = revision.processing_events.filter(action='technical_approve', payload__review_digest=signature).exists()
            events = revision.processing_events.select_related('actor').order_by('-pk' if compact else 'pk')
            outputs = revision.drawing_sets.defer('geometry').order_by('-edition')
            if compact:
                events, data['pagination']['events'] = _page(events, request.GET.get('page', 1) if section == 'events' else 1, 50)
                # Current review content comes first; every retained edition is still pageable.
                from django.db.models import Case, When, Value, IntegerField
                outputs = outputs.annotate(current_first=Case(When(review_digest=signature, then=Value(0)),
                    default=Value(1), output_field=IntegerField())).order_by('current_first', '-edition')
                outputs, data['pagination']['drawings'] = _page(outputs, request.GET.get('page', 1) if section == 'drawings' else 1, 1)
            data['events'] = [{'id': e.pk, 'action': e.action, 'actor': e.actor.get_full_name() or e.actor.get_username(),
                'reason': e.reason, 'at': e.created_at.isoformat()} for e in events]
            for output in outputs:
                if flags['is_client'] and not output.released:
                    continue
                if flags['is_client'] and output.review_digest != signature:
                    continue
                for number, sheet in enumerate(output.manifest.get('sheets', [])):
                    args = [c.pk, output.pk, number]
                    data['drawings'].append({'id': output.pk, 'edition': output.edition, 'title': sheet['title'],
                        'number': sheet['number'], 'scale': sheet.get('scale', 'Not to Scale'), 'released': output.released,
                        'current': output.review_digest == signature,
                        'pdf_url': reverse('survey_processing_output', args=args + ['pdf']),
                        'dxf_url': reverse('survey_processing_output', args=args + ['dxf']),
                        'preview_url': reverse('survey_processing_output', args=args + ['preview'])})
                    if output.manifest.get('bundle'):
                        data['drawings'][-1]['bundle_url'] = reverse('survey_processing_output', args=args + ['bundle'])
        if flags['is_client']:
            # AI drafts, internal comments and evidence suggestions stay internal.
            for name in ['findings', 'conflicts', 'missing', 'suggested_items', 'sources', 'events', 'drawing_records', 'checklist_items']:
                data[name] = []
        if compact and section:
            data = {k: v for k, v in data.items() if k in {'id', 'revision', 'status', 'label', section, 'pagination'}}
        revisions = [r for r in revisions if r['id'] != revision.pk]
        revisions.append(data)
    revisions.sort(key=lambda r: r['revision'], reverse=True)
    active = next((r for r in revisions if r.get('current')), revisions[0] if revisions else None)
    return {'enabled': True, 'stages': [{'status': k, 'label': v} for k, v in pipeline.STAGES.items()],
        'access': flags, 'active': active, 'revisions': revisions,
        'selected_revision_id': selected_id, 'pagination': pagination,
        'detail_token': _detail_token(c, revisions[0] if revisions else None) if compact else None,
        'documents': [] if flags['is_client'] else [{'id': d.pk, 'filename': d.filename, 'size': d.size,
            'url': reverse('survey_processing_document', args=[c.pk, d.pk])} for d in c.survey_documents.order_by('pk')],
        'upload_state': uploads.state(request, c, flags)}


@login_required(login_url='/login/')
@require_GET
@guarded
def progress(request, checklist_id):
    c, flags = pipeline.access(request, checklist_id)
    # Clients use the authorised released-output view. Processing drafts stay private.
    rows = [] if flags['is_client'] else [_summary(row) for row in _summaries(c)[:25]]
    active = rows[0] if rows else None
    data = {'enabled': True, 'access': flags, 'revisions': rows, 'active': active,
        'latest_revision_id': active and active['id'], 'detail_token': _detail_token(c, active),
        'upload_state': uploads.state(request, c, flags)}
    if active and active['status'] in pipeline.ACTIVE:
        from .remote_worker_models import RemoteWorkerProject
        if RemoteWorkerProject.objects.filter(project_id=c.project_id, enabled=True).exists():
            from django.utils import timezone
            lease = c.processing_revisions.filter(pk=active['id']).values_list('processing_job__lease_until', flat=True).first()
            if active['status'] == 'queued':
                message = 'Waiting for the assigned local PC worker. Queued work remains safe while the PC is offline.'
            elif not lease or lease <= timezone.now():
                message = 'The local PC worker connection has expired. Completed checkpoints are preserved; processing resumes when an authorised worker reconnects.'
            else:
                message = 'The local PC worker has an active processing lease. Progress resumes as each saved evidence task completes.'
            data['queue_message'] = active['message'] = message
    return JsonResponse(data)


@login_required(login_url='/login/')
@require_GET
@guarded
def workspace(request, checklist_id):
    from .category_intake import access as capture_access
    from .access import role_for
    from django.shortcuts import redirect
    if role_for(request.user)=='ENGINEER':
        capture_access(request,checklist_id)
        return redirect('photo_workspace',checklist_id=checklist_id)
    c, flags = pipeline.access(request, checklist_id)
    data = serialize(request, checklist_id, compact=True)
    return render(request, 'dashboards/survey_processing.html', {'checklist': c, 'access': flags,
        'pipeline': data, 'documents': data['documents'], 'task_page_title': 'AI Checklist & Drawings'})


@login_required(login_url='/login/')
@require_GET
@guarded
def state(request, checklist_id):
    return JsonResponse(serialize(request, checklist_id, compact=request.GET.get('compact') == '1'))


@login_required(login_url='/login/')
@require_POST
@guarded
def action(request, checklist_id):
    name = request.POST.get('action', '')
    if name in {'submit','retry','review','release','geometry'}:
        from .category_intake import deny_engineer_ai
        deny_engineer_ai(request,checklist_id)
    c, flags = pipeline.access(request, checklist_id)
    if sum(len(k) + len(v) for k, values in request.POST.lists() for v in values) > 256000:
        raise ValidationError('The review form is too large. Save smaller groups of records.')
    if name == 'start_upload':
        session = pipeline.upload_session(request, checklist_id)
        return JsonResponse({'token': str(session.token)}, status=201)
    if name == 'finish_upload':
        session = get_object_or_404(SurveyUploadSession, token=request.POST.get('token'), checklist=c, actor=request.user)
        pipeline.upload_session(request, checklist_id, session.token)
    elif name in {'heartbeat_upload', 'interrupt_upload', 'recover_upload'}:
        if name == 'recover_upload':
            uploads.recover(request, checklist_id, request.POST.get('token'), request.POST.get('reason', ''))
        else:
            handler = uploads.heartbeat if name == 'heartbeat_upload' else uploads.interrupt
            handler(request, checklist_id, request.POST.get('token'))
    elif name == 'upload_document':
        from .survey_evidence import validate_document
        files = request.FILES.getlist('files')
        if not 1 <= len(files) <= 5:
            raise ValidationError('Upload between one and five documents per batch.')
        prepared = [validate_document(f) for f in files]
        stored = []
        try:
            with uploads.upload_batch(request, checklist_id, request.POST.get('token')) as session, transaction.atomic():
                Checklist.objects.select_for_update().get(pk=checklist_id)
                c, checked = pipeline.access(request, checklist_id)
                if not checked['can_submit']:
                    raise ValidationError('The survey is no longer editable.')
                uploads.require_batch_open(c, session.token)
                # Retries and repeated files do not consume extra capacity.
                # Count distinct new hashes while holding the survey write lock.
                existing_hashes = set(c.survey_documents.values_list('sha256', flat=True))
                new_hashes = {item['sha256'] for item in prepared} - existing_hashes
                if len(existing_hashes) + len(new_hashes) > 50:
                    raise ValidationError('Use at most 50 supporting documents per survey.')
                for item in prepared:
                    if c.survey_documents.filter(sha256=item['sha256']).exists():
                        continue
                    doc = SurveyDocument(checklist=c, uploaded_by=request.user, filename=item['filename'],
                        sha256=item['sha256'], content_type=item['content_type'], size=item['size'])
                    doc.original.save(uuid.uuid4().hex + Path(item['filename']).suffix.lower(), ContentFile(item['raw']), save=False)
                    stored.append(doc.original)
                    doc.save()
        except Exception:
            for file in stored:
                file.delete(save=False)
            raise
    elif name == 'submit':
        revision, created = pipeline.submit(request, checklist_id, request.POST.get('uploads_finished') in {'on', 'true', '1'})
        return JsonResponse({'revision_id': revision.pk, 'created': created}, status=201 if created else 200)
    elif name == 'retry':
        pipeline.retry(request, checklist_id, request.POST.get('revision_id'))
    elif name in {'review', 'release'}:
        pipeline.review(request, checklist_id, request.POST.get('revision_id'),
            'release' if name == 'release' else request.POST.get('decision'),
            ids=json.loads(request.POST.get('finding_ids', '[]')),
            corrections=json.loads(request.POST.get('corrections', '{}')),
            reason=request.POST.get('reason', ''), drawing_records=json.loads(request.POST.get('drawing_records', 'null')))
    else:
        raise ValidationError('Unknown processing action.')
    return JsonResponse({'ok': True})


@login_required(login_url='/login/')
@require_GET
@guarded
def document(request, checklist_id, document_id):
    c, flags = pipeline.access(request, checklist_id)
    if flags['is_client']:
        raise Http404()
    doc = get_object_or_404(SurveyDocument, pk=document_id, checklist=c)
    return FileResponse(doc.original.open('rb'), content_type=doc.content_type, as_attachment=True, filename=doc.filename)


@login_required(login_url='/login/')
@require_GET
@guarded
def source_preview(request, checklist_id, analysis_id):
    from .survey_processing_models import SurveySourceAnalysis
    c, flags = pipeline.access(request, checklist_id)
    if flags['is_client']:
        raise Http404()
    source = get_object_or_404(SurveySourceAnalysis, pk=analysis_id, revision__checklist=c)
    name = source.payload.get('preview_file', '')
    if not name:
        raise Http404()
    if pipeline.digest(source.payload) != source.digest:
        raise ValidationError('Source integrity verification failed.')
    return FileResponse(default_storage.open(name, 'rb'), content_type='image/jpeg')


@login_required(login_url='/login/')
@require_GET
@guarded
def output(request, checklist_id, asset_id, sheet, kind):
    c, flags = pipeline.access(request, checklist_id)
    asset = get_object_or_404(SurveyDrawingSet.objects.select_related('revision'), pk=asset_id, revision__checklist=c)
    if flags['is_client']:
        if not asset.released or not pipeline.current(asset.revision) or pipeline.release_gate(asset.revision, pipeline.reviewed_payload(asset.revision)):
            raise Http404()
        if asset.review_digest != pipeline.review_digest(pipeline.reviewed_payload(asset.revision)):
            raise Http404()
    sheets = asset.manifest.get('sheets', [])
    if not 0 <= sheet < len(sheets) or kind not in {'pdf', 'dxf', 'preview', 'bundle'}:
        raise Http404()
    name = asset.manifest.get(kind) if kind in {'pdf', 'bundle'} else sheets[sheet].get(kind)
    path = Path(name or '').resolve()
    media = Path(settings.MEDIA_ROOT).resolve()
    if not path.is_relative_to(media) or not path.is_file():
        raise Http404()
    import hashlib
    expected = asset.manifest.get('file_hashes', {}).get(str(path))
    if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValidationError('The drawing file failed integrity verification; use its retained revision or prepare it again.')
    return FileResponse(path.open('rb'), as_attachment=kind != 'preview', filename=path.name,
        content_type={'pdf': 'application/pdf', 'dxf': 'application/dxf', 'preview': 'image/png', 'bundle': 'application/zip'}[kind])
