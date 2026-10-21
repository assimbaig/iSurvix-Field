"""Authenticated saved-survey processing workspace and private revision assets."""
import json
import uuid
from copy import deepcopy
from functools import wraps
from pathlib import Path
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import JsonResponse, FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from . import survey_processing as pipeline
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


def serialize(request, checklist_id):
    c, flags = pipeline.access(request, checklist_id)
    current_digest = pipeline.digest(pipeline.freeze_data(c))
    revisions = []
    for revision in c.processing_revisions.select_related('processing_job', 'processing_result', 'submitted_by').all():
        job = revision.processing_job
        is_current = pipeline.matches_revision(revision, current_digest)
        revision._source_cache = {a.source_id: a for a in revision.source_analyses.all() if not a.source_id.startswith('mapping:')}
        if flags['is_client'] and (not is_current or not revision.drawing_sets.filter(released=True).exists()):
            continue
        data = {'id': revision.pk, 'revision': revision.number, 'status': job.status,
            'label': pipeline.STAGES.get(job.status, job.status), 'current': is_current,
            'completed': job.completed, 'total': job.total, 'error': job.error,
            'created_at': revision.created_at.isoformat(), 'findings': [], 'checklist_items': [],
            'missing': [], 'conflicts': [], 'drawings': [], 'events': [], 'sources': [], 'drawing_records': [],
            'can_release': False, 'release_blocker': 'Processing must finish first.'}
        if SurveyProcessingResult.objects.filter(revision=revision).exists():
            payload = pipeline.reviewed_payload(revision)
            data.update(deepcopy(payload))
            originals = {f.get('finding_key'): f for f in revision.processing_result.payload.get('findings', [])}
            for item in data['checklist_items']:
                from .template_views import field_is_locked
                item['locked'] = field_is_locked(c, item['id'])
                item['sources'] = [source_link(revision, src) for src in item.get('sources', [])]
            data['sources'] = [source_link(revision, {'source_id': a.source_id, 'reference': a.payload.get('reference', '')}) for a in revision._source_cache.values()]
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
            data['events'] = [{'id': e.pk, 'action': e.action, 'actor': e.actor.get_full_name() or e.actor.get_username(),
                'reason': e.reason, 'at': e.created_at.isoformat()} for e in revision.processing_events.select_related('actor').order_by('pk')]
            for output in revision.drawing_sets.order_by('-edition'):
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
        revisions.append(data)
    active = next((r for r in revisions if r['current']), revisions[0] if revisions else None)
    open_sessions = c.survey_upload_sessions.filter(actor=request.user, finished_at__isnull=True)
    return {'enabled': True, 'stages': [{'status': k, 'label': v} for k, v in pipeline.STAGES.items()],
        'access': flags, 'active': active, 'revisions': revisions,
        'documents': [] if flags['is_client'] else [{'id': d.pk, 'filename': d.filename, 'size': d.size,
            'url': reverse('survey_processing_document', args=[c.pk, d.pk])} for d in c.survey_documents.order_by('pk')],
        'upload_state': {'inflight': c.survey_upload_sessions.filter(finished_at__isnull=True).count(),
            'own_tokens': [str(token) for token in open_sessions.values_list('token', flat=True)]}}


@login_required(login_url='/login/')
@require_GET
@guarded
def workspace(request, checklist_id):
    c, flags = pipeline.access(request, checklist_id)
    data = serialize(request, checklist_id)
    return render(request, 'dashboards/survey_processing.html', {'checklist': c, 'access': flags,
        'pipeline': data, 'documents': data['documents'], 'task_page_title': 'AI Checklist & Drawings'})


@login_required(login_url='/login/')
@require_GET
@guarded
def state(request, checklist_id):
    return JsonResponse(serialize(request, checklist_id))


@login_required(login_url='/login/')
@require_POST
@guarded
def action(request, checklist_id):
    c, flags = pipeline.access(request, checklist_id)
    if sum(len(k) + len(v) for k, values in request.POST.lists() for v in values) > 256000:
        raise ValidationError('The review form is too large. Save smaller groups of records.')
    name = request.POST.get('action', '')
    if name == 'start_upload':
        session = pipeline.upload_session(request, checklist_id)
        return JsonResponse({'token': str(session.token)}, status=201)
    if name == 'finish_upload':
        session = get_object_or_404(SurveyUploadSession, token=request.POST.get('token'), checklist=c, actor=request.user)
        pipeline.upload_session(request, checklist_id, session.token)
    elif name == 'upload_document':
        from .survey_evidence import validate_document
        files = request.FILES.getlist('files')
        if not 1 <= len(files) <= 5:
            raise ValidationError('Upload between one and five documents per batch.')
        prepared = [validate_document(f) for f in files]
        session = pipeline.upload_session(request, checklist_id)
        stored = []
        try:
            with transaction.atomic():
                Checklist.objects.select_for_update().get(pk=checklist_id)
                c, checked = pipeline.access(request, checklist_id)
                if not checked['can_submit']:
                    raise ValidationError('The survey is no longer editable.')
                if c.survey_documents.count() + len(prepared) > 50:
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
        finally:
            pipeline.upload_session(request, checklist_id, session.token)
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
