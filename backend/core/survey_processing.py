"""Survey-only evidence-to-draft pipeline. Inference never approves a survey."""
import hashlib
import json
import logging
import math
import re
import uuid
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Max, Q
from django.http import Http404
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .access import role_for, can_access_project
from .models import Checklist, Profile
from .survey_processing_models import (SurveyDocument, SurveyUploadSession, SurveyProcessingRevision,
    SurveyProcessingJob, SurveySourceAnalysis, SurveyProcessingResult, SurveyProcessingEvent, SurveyDrawingSet)

STAGES = {
    'queued': 'Queued', 'analysing_evidence': 'Analysing evidence',
    'preparing_checklist': 'Preparing checklist', 'preparing_drawings': 'Preparing drawings',
    'ready_for_review': 'Ready for review', 'failed': 'Failed',
}
ACTIVE = set(STAGES) - {'ready_for_review', 'failed'}
PIPELINE_VERSION = 'survey-pipeline-1'
logger = logging.getLogger(__name__)


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def enabled(checklist):
    template = checklist.checklist_template
    return bool(checklist.workflow_type == Checklist.WorkflowType.TELECOM_SURVEY and template and template.published and template.checklist_required)


def access(request, checklist_id):
    from .template_views import survey_access
    actor = get_user_model().objects.select_related('profile').get(pk=request.user.pk) if request.user.is_authenticated else request.user
    request.user = actor
    existing = survey_access(request, checklist_id)
    c = existing['checklist']
    if not enabled(c):
        raise Http404('This survey type does not use checklist processing.')
    role = role_for(actor)
    owner = role == Profile.Roles.ENGINEER and c.user_id == actor.pk
    editable = bool(owner and existing['can_edit'])
    technical = role == Profile.Roles.QUALITY_ENGINEER and c.quality_reviewer_id == actor.pk
    if c.governance_mode == 'independent' and hasattr(c, 'review_policy'):
        technical = role == Profile.Roles.QUALITY_ENGINEER and c.review_policy.l2_reviewer_id == actor.pk
    return c, {'can_submit': editable, 'can_review': editable, 'can_complete': editable,
        'can_technical_review': bool(technical), 'can_release': role == Profile.Roles.TEAM_LEAD,
        'is_client': role == Profile.Roles.CLIENT}


def freeze_data(c):
    """Only controlling data; workflow approval changes do not invalidate inputs."""
    return {
        'pipeline_version': PIPELINE_VERSION, 'id': c.pk, 'site_id': c.site_id,
        'assigned_engineer_id': c.user_id,
        'project_id': c.project_id, 'project': c.project.name,
        'company': c.project.company.name if c.project.company_id else '',
        'workflow_type': c.workflow_type, 'template_id': c.checklist_template_id,
        'schema': deepcopy(c.schema_snapshot), 'answers': deepcopy(c.answer_data),
        'remarks': deepcopy(c.remark_data), 'intake': deepcopy(c.intake_metadata),
        'coordinates': deepcopy(c.coordinate_reference), 'branding': deepcopy(c.branding_snapshot),
        'photos': [dict(p) for p in c.photo_evidence.order_by('pk').values('id', 'filename', 'sha256', 'original', 'preview', 'metadata')],
        'documents': [dict(d) for d in c.survey_documents.order_by('pk').values('id', 'filename', 'sha256', 'original', 'content_type', 'size')],
    }


def current(revision):
    return matches_revision(revision, digest(freeze_data(Checklist.objects.select_related('project__company', 'checklist_template').get(pk=revision.checklist_id))))


def matches_revision(revision, signature):
    return revision.digest == signature or revision.processing_events.filter(action='applied', payload__source_digest=signature).exists()


def require_engineer_review(c):
    """Opt-in surveys cannot bypass the integrated review via an older submit URL."""
    if not enabled(c):
        return
    signature = digest(freeze_data(c))
    for revision in c.processing_revisions.filter(processing_job__status='ready_for_review'):
        if matches_revision(revision, signature):
            package = reviewed_payload(revision)
            if revision.processing_events.filter(action='engineer_complete', payload__review_digest=review_digest(package)).exists():
                return
    raise ValidationError('Complete AI Checklist & Drawings processing and Engineer review for the current survey inputs before submission.')


def processed_photo_ids(c):
    if not getattr(c, 'checklist_template_id', None) or not enabled(c):
        return set()
    signature = digest(freeze_data(c))
    for revision in c.processing_revisions.filter(processing_job__status='ready_for_review'):
        if matches_revision(revision, signature):
            result = revision.processing_result
            if digest(result.payload) != result.digest:
                raise ValidationError('Saved processing result integrity verification failed.')
            sources = set(revision.source_analyses.values_list('source_id', flat=True))
            return {p['id'] for p in revision.snapshot['photos'] if 'photo:' + str(p['id']) in sources}
    return set()


def verify_originals(revision):
    for source in revision.snapshot['photos'] + revision.snapshot['documents']:
        with default_storage.open(source['original'], 'rb') as handle:
            if hashlib.file_digest(handle, 'sha256').hexdigest() != source['sha256']:
                raise ValidationError('Original evidence integrity verification failed. Preserve this revision and investigate the source file.')


def validate_submission(c, uploads_finished):
    if uploads_finished is not True:
        raise ValidationError('Confirm that all survey data and uploads are complete.')
    if not c.site_id.strip() or not c.schema_snapshot.get('sections'):
        raise ValidationError('Provide the site ID and an administrator-approved checklist.')
    from .roadmap_service import require_qualified_template
    require_qualified_template(c)
    if c.survey_upload_sessions.filter(finished_at__isnull=True).exists():
        raise ValidationError('Uploads are still in progress. Finish or close your upload session first.')
    allowed = {f['id']: f for s in c.checklist_template.definition['sections'] for f in s['fields']}
    for section in c.schema_snapshot['sections']:
        for field in section['fields']:
            if field['id'] not in allowed or field != allowed[field['id']]:
                raise ValidationError('The saved checklist must use the administrator-published field definitions.')
            if field.get('survey_input') and field.get('required'):
                value = c.site_id if field.get('system') == 'site_id' else c.answer_data.get('custom', {}).get(field['id'])
                if value in ('', None, []):
                    raise ValidationError('Complete the required survey input: ' + field['label'])
    if not c.photo_evidence.exists() and not c.survey_documents.exists():
        raise ValidationError('Upload at least one photo or supported document.')


def submit(request, checklist_id, uploads_finished):
    with transaction.atomic():
        Checklist.objects.select_for_update().get(pk=checklist_id)
        c, flags = access(request, checklist_id)
        if not flags['can_submit']:
            raise PermissionDenied('Only the assigned Engineer may submit an editable survey.')
        validate_submission(c, uploads_finished)
        snapshot = freeze_data(c)
        signature = digest(snapshot)
        existing = c.processing_revisions.filter(digest=signature).first()
        if not existing:
            existing = c.processing_revisions.filter(processing_events__action='applied', processing_events__payload__source_digest=signature).first()
        if existing:
            return existing, False
        if c.processing_revisions.filter(processing_job__status__in=ACTIVE).exists():
            raise ValidationError('The previous revision is still processing. Wait for it to finish before submitting changed inputs.')
        number = (c.processing_revisions.aggregate(n=Max('number'))['n'] or 0) + 1
        revision = SurveyProcessingRevision.objects.create(checklist=c, number=number, digest=signature, snapshot=snapshot, submitted_by=request.user)
        SurveyProcessingJob.objects.create(revision=revision, model=settings.OLLAMA_MODEL, total=len(snapshot['photos']) + len(snapshot['documents']))
        SurveyProcessingEvent.objects.create(revision=revision, actor=request.user, action='submitted', payload={'snapshot_digest': signature})
        return revision, True


def upload_session(request, checklist_id, token=None):
    with transaction.atomic():
        Checklist.objects.select_for_update().get(pk=checklist_id)
        c, flags = access(request, checklist_id)
        if not flags['can_submit']:
            raise PermissionDenied('Only the assigned Engineer can upload processing evidence.')
        if token is None:
            return SurveyUploadSession.objects.create(token=uuid.uuid4(), checklist=c, actor=request.user)
        session = SurveyUploadSession.objects.get(token=token, checklist=c, actor=request.user)
        if session.finished_at is None:
            session.finished_at = timezone.now()
            session.save(update_fields=['finished_at'])
        return session


def retry(request, checklist_id, revision_id):
    with transaction.atomic():
        c, flags = access(request, checklist_id)
        if not flags['can_submit']:
            raise PermissionDenied('Only the assigned Engineer can retry processing.')
        job = get_object_or_404(SurveyProcessingJob.objects.select_for_update(), revision_id=revision_id, revision__checklist=c)
        if not current(job.revision):
            raise ValidationError('Survey inputs changed. Submit a new revision; the previous revision is preserved.')
        if job.status == 'failed':
            job.status, job.error, job.lease_owner, job.lease_until = 'queued', '', '', None
            job.save()
            SurveyProcessingEvent.objects.create(revision=job.revision, actor=request.user, action='retried')
        return job.revision


def worker_guard(revision):
    actor = get_user_model().objects.select_related('profile').get(pk=revision.submitted_by_id)
    c = Checklist.objects.get(pk=revision.checklist_id)
    if role_for(actor) != Profile.Roles.ENGINEER or actor.pk != c.user_id or not can_access_project(actor, c.project_id):
        raise ValidationError('The submitter no longer has the required project assignment.')
    if digest(revision.snapshot) != revision.digest:
        raise ValidationError('Submission integrity verification failed.')


def claim():
    now = timezone.now()
    with transaction.atomic():
        job = SurveyProcessingJob.objects.select_for_update().filter(
            Q(status='queued') | Q(status__in=ACTIVE, lease_until__lt=now) |
            Q(status__in=ACTIVE, lease_until__isnull=True)).order_by('pk').first()
        if not job:
            return None
        job.lease_owner = uuid.uuid4().hex
        job.lease_until = now + timedelta(seconds=max(300, getattr(settings, 'OLLAMA_TIMEOUT', 180) + 120))
        job.attempts += 1
        job.status, job.error = 'analysing_evidence', ''
        job.save()
        return job


def progress(job, status=None, **values):
    with transaction.atomic():
        worker_guard(job.revision)
        saved = SurveyProcessingJob.objects.select_for_update().get(pk=job.pk)
        if saved.lease_owner != job.lease_owner or saved.lease_until <= timezone.now():
            raise ValidationError('The processing lease expired; another worker may resume safely.')
        for name, value in values.items():
            setattr(saved, name, value)
        if status:
            saved.status = status
        if saved.status in ACTIVE:
            saved.lease_until = timezone.now() + timedelta(seconds=max(300, getattr(settings, 'OLLAMA_TIMEOUT', 180) + 120))
        saved.save()
        job.completed, job.total = saved.completed, saved.total


def tokens(value):
    return set(re.findall(r'[a-z0-9]+', str(value).lower())) - {'the', 'of', 'and', 'for', 'to', 'a', 'is', 'site', 'photo'}


def numeric_evidence_value(field, finding):
    """Convert an explicitly recorded unit, never silently reinterpret a number.

    Only a small dimensionally compatible conversion table is supported. Unknown
    or incompatible units remain visible findings requiring a human correction.
    """
    value = finding.get('value')
    expected = str(field.get('unit', '')).strip().casefold()
    observed = str(finding.get('unit', '')).strip().casefold()
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise InvalidOperation()
        if number and abs(number.adjusted()) > 10000:
            raise ValidationError('The recorded number exceeds the supported field length.')
    except InvalidOperation as exc:
        raise ValidationError('The recorded measurement is not a finite number.') from exc
    def formatted(value):
        if not value:
            return '0'
        if abs(value.adjusted()) > 10000:
            raise ValidationError('The recorded number exceeds the supported field length.')
        text = format(value, 'f')
        if '.' in text:
            text = text.rstrip('0').rstrip('.')
        if len(text) > 10000:
            raise ValidationError('The recorded number exceeds the supported field length.')
        return text
    if not expected:
        return formatted(number), observed
    if not observed:
        raise ValidationError('The recorded value is missing its measurement unit.')
    if expected == observed:
        return formatted(number), expected
    conversions = {
        'mm': ('length', Decimal('.001')), 'cm': ('length', Decimal('.01')),
        'm': ('length', Decimal(1)), 'km': ('length', Decimal(1000)),
        'mv': ('voltage', Decimal('.001')), 'v': ('voltage', Decimal(1)), 'kv': ('voltage', Decimal(1000)),
        'ma': ('current', Decimal('.001')), 'a': ('current', Decimal(1)),
        'w': ('power', Decimal(1)), 'kw': ('power', Decimal(1000)),
        'hz': ('frequency', Decimal(1)), 'khz': ('frequency', Decimal(1000)),
        'mhz': ('frequency', Decimal(1000000)), 'ghz': ('frequency', Decimal(1000000000)),
        'deg': ('angle', Decimal(1)), 'degrees': ('angle', Decimal(1)), '°': ('angle', Decimal(1)),
    }
    source, target = conversions.get(observed), conversions.get(expected)
    if not source or not target or source[0] != target[0]:
        raise ValidationError('The recorded unit does not match the checklist unit; confirm the intended value and unit.')
    try:
        # Exact powers-of-ten conversion must not round a recorded long decimal
        # to the default Decimal context's 28 significant digits.
        with localcontext() as context:
            context.prec = max(28, len(number.as_tuple().digits) + 32)
            converted = number * source[1] / target[1]
    except InvalidOperation as exc:
        raise ValidationError('The recorded measurement is not a finite number.') from exc
    return formatted(converted), expected


def prepare_checklist(snapshot, reconciliation):
    """Complete published structure; conservative mapping leaves ambiguity visible."""
    fields = [(s, f) for s in snapshot['schema']['sections'] for f in s['fields']]
    known_ids = {field['id'] for _, field in fields}
    proposals = []
    conflicts = deepcopy(reconciliation.get('conflicts', []))
    missing = deepcopy(reconciliation.get('missing', []))
    for section, field in fields:
        value = snapshot['site_id'] if field.get('system') == 'site_id' else snapshot['answers'].get('custom', {}).get(field['id'])
        reported_value = deepcopy(value)
        matches = []
        label = tokens(field['label'])
        for finding in reconciliation.get('findings', []):
            if finding.get('mapping_unassigned'):
                continue
            hint = str(finding.get('field_hint') or finding.get('component') or '')
            words = tokens(hint)
            score = len(words & label) / max(1, len(words))
            if hint == field['id'] or hint not in known_ids and len(words & label) >= 2 and score >= .8:
                matches.append(finding)
        supported = [deepcopy(x) for x in matches if x.get('value') not in (None, '', [], {})]
        unit = str(field.get('unit', ''))
        if field['type'] == 'number':
            compatible = []
            for finding in supported:
                try:
                    finding['value'], observed_unit = numeric_evidence_value(field, finding)
                    finding['unit'] = observed_unit
                    unit = unit or observed_unit
                    compatible.append(finding)
                except ValidationError as exc:
                    missing.append({'field_id': field['id'], 'source_id': finding.get('source_id', ''),
                                    'message': '; '.join(exc.messages)})
            supported = compatible
        answers = {json.dumps(x['value'], sort_keys=True) for x in supported}
        status = 'Reported' if value not in (None, '', [], {}) else 'Missing'
        if len(answers) == 1 and value in (None, '', [], {}) and field['type'] not in {'photo', 'inspection'}:
            value, status = supported[0]['value'], 'Needs review'
            from .template_service import validate_answer
            try:
                # Numeric AI values remain proposals only with recorded units;
                # source text is not a photograph-derived measurement.
                if type(value) in (int, float):
                    value = str(value)
                validate_answer(field, value)
                if isinstance(value, str) and value.strip().lower() in {'n/a', 'not applicable', 'compliant', 'passed', 'approved'}:
                    value = None
            except ValidationError:
                value = None
        if matches and field['type'] == 'photo':
            value, status = 'Evidence attached - verify subject', 'Needs review'
        def comparison(entry):
            from .survey_evidence import _normalised_value
            return _normalised_value(entry)
        answers = {str(comparison(x)) for x in supported}
        def same_reported(entry):
            if field['type'] == 'number':
                try:
                    return Decimal(str(entry['value'])) == Decimal(str(reported_value))
                except InvalidOperation:
                    return False
            return str(entry['value']) == str(reported_value)
        conflict = len(answers) > 1 or reported_value not in (None, '', [], {}) and any(not same_reported(x) for x in supported)
        if conflict:
            status = 'Needs review'
            conflicts.append({'field_id': field['id'], 'message': 'Submitted data or evidence contains conflicting values. An Engineer must resolve this item.'})
        sources = []
        for match in matches:
            source = {'source_id': match.get('source_id', ''), 'reference': match.get('reference', '')}
            if source not in sources:
                sources.append(source)
        if field.get('system') == 'site_id':
            status = 'Reported'
        proposals.append({'id': field['id'], 'section': section['title'], 'label': field['label'],
            'proposed_answer': value, 'value': value, 'status': status, 'sources': sources,
            'confidence': 'high' if supported and all(x.get('confidence') == 'high' for x in supported) and not conflict else 'low',
            'accepted': False, 'conflict': conflict,
            'unit': unit,
            'reason': 'Check the original evidence before acceptance.' if matches else 'Submitted data; verify it.' if status == 'Reported' else 'No supported answer was extracted.'})
    return {'checklist_items': proposals, 'findings': reconciliation.get('findings', []),
        'conflicts': conflicts, 'missing': missing,
        'suggested_items': reconciliation.get('suggested_items', []), 'drawing_records': []}


def reviewed_payload(revision):
    result = revision.processing_result
    if digest(result.payload) != result.digest:
        raise ValidationError('Saved processing output failed integrity verification.')
    payload = deepcopy(result.payload)
    by_id = {i['id']: i for i in payload['checklist_items']}
    for event in revision.processing_events.order_by('pk'):
        if event.action in {'accept', 'correct', 'reject'}:
            for ident, update in event.payload.get('items', {}).items():
                if ident in by_id:
                    by_id[ident].update(update)
        elif event.action == 'geometry':
            payload['drawing_records'] = event.payload['drawing_records']
        elif event.action == 'accept_additional':
            accepted = payload.setdefault('accepted_additional_items', [])
            for item in event.payload.get('items', []):
                if item not in accepted:
                    accepted.append(item)
        elif event.action == 'technical_reject':
            payload['review_cycle'] = event.pk
            for item in payload['checklist_items']:
                item['accepted'] = False
        elif event.action == 'record':
            for finding in payload.get('findings', []):
                change = event.payload.get('findings', {}).get(finding.get('finding_key'))
                if change:
                    finding.update(change)
                    if finding.get('field_hint') in by_id:
                        value = change['value']
                        unit = change.get('unit', '')
                        conflict = False
                        reason = event.reason
                        field = next(f for section in revision.snapshot['schema']['sections'] for f in section['fields'] if f['id'] == finding['field_hint'])
                        if field['type'] == 'number' and value not in (None, ''):
                            try:
                                value, unit = numeric_evidence_value(field, finding)
                            except ValidationError as exc:
                                # Older human events may contain incompatible units.
                                # Preserve their audit record and keep recovery usable.
                                value, conflict = None, True
                                finding['verification_status'] = 'needs_review'
                                reason = '; '.join(exc.messages)
                        by_id[finding['field_hint']].update(value=value, proposed_answer=value, unit=unit,
                            accepted=False, status='Needs review', conflict=conflict, reason=reason)
    return payload


def review_digest(payload):
    return digest({'items': payload['checklist_items'], 'findings': payload.get('findings', []), 'drawing_records': payload.get('drawing_records', []), 'additional': payload.get('accepted_additional_items', []), 'review_cycle': payload.get('review_cycle', 0)})


def drawing_branding(revision):
    branding = revision.snapshot.get('branding', {})
    result = {'project_id': revision.snapshot['project_id']}
    clients = branding.get('clients', [])
    # Only snapshotted assigned logos are used, never default client artwork.
    for index, client in enumerate(clients[:2]):
        if not isinstance(client, dict) or not client.get('logo'):
            continue
        try:
            result['client_logo' if index == 0 else 'partner_logo'] = default_storage.path(client['logo'])
        except (ValueError, NotImplementedError):
            pass
    if branding.get('company_logo'):
        try:
            result['company_logo'] = default_storage.path(branding['company_logo'])
        except (ValueError, NotImplementedError):
            pass
    return result


def render_drawing_set(revision, payload, released=False, actor=None):
    from .survey_drawings import build_geometry, render_outputs
    signature = review_digest(payload)
    existing = revision.drawing_sets.filter(review_digest=signature, released=released).first()
    if existing:
        return existing
    edition = (revision.drawing_sets.aggregate(n=Max('edition'))['n'] or 0) + 1
    snapshot = {**revision.snapshot, 'date': revision.created_at.date().isoformat(), 'drawing_records': payload.get('drawing_records', [])}
    mapped = {item['id'] for item in payload['checklist_items'] if item.get('accepted')}
    labels = {f['id']: f['label'] for section in revision.snapshot['schema']['sections'] for f in section['fields']}
    findings = [{**f, 'label': f.get('label') or labels.get(f.get('field_hint')) or f.get('component') or f.get('category', 'Evidence record')}
        for f in payload.get('findings', []) if f.get('field_hint') not in mapped]
    for item in payload['checklist_items']:
        if item.get('accepted'):
            findings.append({'field_hint': item['id'], 'component': item['label'], 'value': item['value'],
                'label': item['label'], 'field': item['id'],
                'unit': item.get('unit', ''),
                'status': item['status'], 'verification_status': 'confirmed' if item['status'] == 'Confirmed from evidence' else 'needs_review',
                'confidence': item['confidence'], 'sources': item['sources'], 'notes': item.get('reason', '')})
    geometry = build_geometry(snapshot, findings)
    output_dir = Path(settings.MEDIA_ROOT) / 'survey_processing' / str(revision.checklist_id) / str(revision.pk) / uuid.uuid4().hex
    checker = revision.processing_events.filter(action='technical_approve', payload__review_digest=signature).last()
    manifest = render_outputs(geometry, output_dir, revision=revision.number, branding=drawing_branding(revision),
        prepared_by=revision.submitted_by.get_full_name() or revision.submitted_by.get_username(),
        checked_by=checker.actor.get_full_name() or checker.actor.get_username() if checker else '',
        approved_by=(actor.get_full_name() or actor.get_username()) if released and actor else '', released=released)
    # Store JSON-safe manifest, no client can supply output file paths.
    manifest = json.loads(json.dumps(manifest, default=str))
    if manifest.get('geometry') and Path(manifest['geometry']).is_file():
        geometry = json.loads(Path(manifest['geometry']).read_text(encoding='utf-8'))
    files = [manifest.get('pdf'), manifest.get('bundle'), manifest.get('geometry')]
    for sheet in manifest.get('sheets', []):
        files.extend([sheet.get('dxf'), sheet.get('preview')])
    manifest['file_hashes'] = {str(path): hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in files if path and Path(path).is_file()}
    return SurveyDrawingSet.objects.create(revision=revision, edition=edition, released=released,
        review_digest=signature, geometry=geometry, manifest=manifest)


def process_next():
    from . import survey_evidence as evidence
    from .photo_service import verify_vision
    from .local_ai import InferenceBusy
    from .photo_queue import photo_inference_lease
    job = claim()
    if not job:
        return False
    try:
        worker_guard(job.revision)
        with photo_inference_lease() as check:
            details = verify_vision(job.model)
            check()
        identity = digest({'model': job.model, 'details': details, 'pipeline': job.pipeline_version})
        if job.model_digest and job.model_digest != identity:
            raise ValidationError('The pinned model changed. Submit a new revision after explicitly selecting the model.')
        progress(job, model_digest=identity)
        snapshot = job.revision.snapshot
        catalog = [{k: f[k] for k in ('id', 'label', 'type') if k in f}
            for section in snapshot['schema']['sections'] for f in section['fields']]
        small_catalog = catalog if len(catalog) <= 40 and len(json.dumps(catalog, ensure_ascii=False)) <= 12000 else []
        def records(items):
            return [{**x, 'path': default_storage.path(x['original'])} for x in items]
        count = 0
        for source in evidence.extract_sources(records(snapshot['photos']), records(snapshot['documents'])):
            source['field_catalog'] = small_catalog
            count += 1
            if count > 2000:
                raise ValidationError('This submission exceeds 2000 bounded evidence pages/images. Split its documents.')
            cached = job.revision.source_analyses.filter(source_id=source['source_id']).first()
            if cached:
                if digest(cached.payload) != cached.digest:
                    raise ValidationError('Saved source analysis failed integrity verification.')
            else:
                progress(job, total=max(job.total, count))
                with photo_inference_lease() as check:
                    analysed = evidence.analyse_source(source, job.model,
                        base_url=getattr(settings, 'PHOTO_OLLAMA_BASE_URL', settings.OLLAMA_BASE_URL))
                    check()
                if source.get('image_b64'):
                    import base64
                    from django.core.files.base import ContentFile
                    name = 'survey_processing/previews/' + str(job.revision_id) + '/' + digest(source['source_id']) + '.jpg'
                    if not default_storage.exists(name):
                        name = default_storage.save(name, ContentFile(base64.b64decode(source['image_b64'])))
                    analysed['preview_file'] = name
                with transaction.atomic():
                    progress(job)
                    SurveySourceAnalysis.objects.get_or_create(revision=job.revision, source_id=source['source_id'],
                        defaults={'payload': analysed, 'digest': digest(analysed)})
            progress(job, completed=count, total=max(job.total, count))
        progress(job, 'preparing_checklist', total=count)
        result = SurveyProcessingResult.objects.filter(revision=job.revision).first()
        if not result:
            analyses = []
            for saved in job.revision.source_analyses.exclude(source_id__startswith='mapping:').order_by('source_id'):
                if digest(saved.payload) != saved.digest:
                    raise ValidationError('Saved evidence analysis failed integrity verification.')
                analyses.append(saved.payload)
            if any(not f.get('field_hint') for a in analyses for f in a.get('findings', [])):
                from .survey_checklist_mapping import mapping_batches, bind_batch, binding_identity
                bindings = {}
                unassigned = set()
                for batch in mapping_batches(analyses, snapshot['schema']):
                    cached = job.revision.source_analyses.filter(source_id=batch['key']).first()
                    if cached:
                        if digest(cached.payload) != cached.digest or cached.payload.get('batch_identity') != batch['identity'] or cached.payload.get('identity') != binding_identity(batch, job.model):
                            raise ValidationError('The saved checklist mapping context changed; preserve this revision and submit a new one.')
                        mapped = cached.payload
                    else:
                        progress(job)
                        with photo_inference_lease() as check:
                            mapped = bind_batch(batch, job.model,
                                base_url=getattr(settings, 'PHOTO_OLLAMA_BASE_URL', settings.OLLAMA_BASE_URL))
                            check()
                        with transaction.atomic():
                            progress(job)
                            SurveySourceAnalysis.objects.create(revision=job.revision, source_id=batch['key'], payload=mapped, digest=digest(mapped))
                    for binding in mapped['bindings']:
                        bindings[binding['finding_key']] = binding
                    unassigned.update(mapped.get('unassigned', []))
                analyses = deepcopy(analyses)
                for analysed in analyses:
                    for finding in analysed.get('findings', []):
                        binding = bindings.get(finding.get('finding_key'))
                        if binding:
                            finding['field_hint'] = binding['field_id']
                            finding['mapping_reason'] = binding['reason']
                        elif finding.get('finding_key') in unassigned:
                            finding['mapping_unassigned'] = True
            payload = prepare_checklist(snapshot, evidence.reconcile_results(analyses))
            with transaction.atomic():
                progress(job)
                result, _ = SurveyProcessingResult.objects.get_or_create(revision=job.revision,
                    defaults={'payload': payload, 'digest': digest(payload)})
        progress(job, 'preparing_drawings')
        with transaction.atomic():
            progress(job)
            if digest(result.payload) != result.digest:
                raise ValidationError('Saved processing output failed integrity verification.')
            render_drawing_set(job.revision, result.payload)
        progress(job, 'ready_for_review', error='', lease_owner='', lease_until=None)
    except InferenceBusy:
        SurveyProcessingJob.objects.filter(pk=job.pk, lease_owner=job.lease_owner).update(status='queued', lease_owner='', lease_until=None)
        return False  # Let the independent worker back off while shared inference is busy.
    except Exception as exc:
        # Do not expose prompts, document contents, paths or raw model text.
        code = type(exc).__name__
        safe = 'Processing could not finish (' + code + '). Saved progress is preserved; check the local model, input files and worker log, then retry.'
        if isinstance(exc, ValidationError):
            safe = '; '.join(exc.messages)[:500]
        elif type(exc).__name__ in {'EvidenceError', 'MappingError'}:
            safe = str(exc)[:500]
        elif isinstance(exc, ValueError) and str(exc) in {
            'Selected model is not locally installed; cloud aliases are forbidden.',
            'Selected installed model does not report vision capability.', 'Remote models are forbidden.'}:
            safe = str(exc)
        elif isinstance(exc, (ConnectionError, TimeoutError)) or type(exc).__name__ == 'URLError':
            safe = 'The local Ollama service is offline or timed out. Start the configured local service, then retry; completed sources are preserved.'
        SurveyProcessingJob.objects.filter(pk=job.pk, lease_owner=job.lease_owner).update(status='failed', error=safe, lease_owner='', lease_until=None)
        logger.warning('Survey processing failed: job=%s revision=%s error_type=%s', job.pk, job.revision_id, code)
    return True


def release_gate(revision, payload):
    signature = review_digest(payload)
    endorsed = revision.processing_events.filter(action='engineer_complete', payload__review_digest=signature).last()
    checked = revision.processing_events.filter(action='technical_approve', payload__review_digest=signature).last()
    if not endorsed:
        return 'The Engineer must complete review of this exact package.'
    if not checked or checked.actor_id == endorsed.actor_id:
        return 'An independent assigned QA Engineer must approve this exact package.'
    c = Checklist.objects.get(pk=revision.checklist_id)
    checker = get_user_model().objects.select_related('profile').get(pk=checked.actor_id)
    expected_quality = c.review_policy.l2_reviewer_id if c.governance_mode == 'independent' and hasattr(c, 'review_policy') else c.quality_reviewer_id
    if role_for(checker) != Profile.Roles.QUALITY_ENGINEER or checker.pk != expected_quality or not can_access_project(checker, c.project_id):
        return 'The technical reviewer must still hold the assigned Quality Engineer project access.'
    if c.status != Checklist.Status.FINAL:
        return 'Complete the existing survey approval workflow before releasing drawings.'
    route = getattr(c, 'review_route_record', None)
    if route and route.stage != 'closed':
        return 'The existing QA / Team Lead / Client approval route must be closed.'
    if c.client_review_required and c.client_approval.get('decision') != 'approved':
        return 'The required Client approval must be recorded before release.'
    return ''


def review(request, checklist_id, revision_id, decision, ids=None, corrections=None, reason='', drawing_records=None):
    from .template_service import field_map, validate_answer
    from .template_views import require_field_editable
    if not isinstance(reason, str) or not isinstance(decision, str) or corrections is not None and not isinstance(corrections, dict):
        raise ValidationError('Provide a valid review decision, correction object and reason.')
    with transaction.atomic():
        Checklist.objects.select_for_update().get(pk=checklist_id)
        c, flags = access(request, checklist_id)
        revision = get_object_or_404(SurveyProcessingRevision.objects.select_for_update(), pk=revision_id, checklist=c)
        if revision.processing_job.status != 'ready_for_review' or not current(revision):
            raise ValidationError('Review requires a completed current revision. Submit changed survey inputs again.')
        payload = reviewed_payload(revision)
        signature = review_digest(payload)
        if decision == 'technical_reject':
            if not flags['can_technical_review'] or request.user.pk == revision.submitted_by_id:
                raise PermissionDenied('Only the independent assigned QA Engineer can return a package.')
            if not reason.strip():
                raise ValidationError('Explain why the package requires correction.')
            SurveyProcessingEvent.objects.create(revision=revision, actor=request.user, action=decision, reason=reason[:4000])
            return revision
        if decision in {'technical_approve', 'release'}:
            if decision == 'technical_approve':
                if not flags['can_technical_review'] or request.user.pk == revision.submitted_by_id:
                    raise PermissionDenied('An independent assigned QA Engineer must perform technical review.')
                if not revision.processing_events.filter(action='engineer_complete', payload__review_digest=signature).exists():
                    raise ValidationError('The Engineer must complete review first.')
                event_payload = {'review_digest': signature}
            else:
                if not flags['can_release'] or request.user.pk == revision.submitted_by_id:
                    raise PermissionDenied('Only an independent Team Lead may release approved outputs.')
                blocking = release_gate(revision, payload)
                if blocking:
                    raise ValidationError(blocking)
                checker = revision.processing_events.filter(action='technical_approve', payload__review_digest=signature).last()
                if checker.actor_id == request.user.pk:
                    raise PermissionDenied('The technical reviewer and release approver must be different users.')
                verify_originals(revision)
                render_drawing_set(revision, payload, released=True, actor=request.user)
                event_payload = {'review_digest': signature}
            if not revision.processing_events.filter(action=decision, payload__review_digest=signature).exists():
                SurveyProcessingEvent.objects.create(revision=revision, actor=request.user, action=decision, reason=reason[:4000], payload=event_payload)
            return revision
        if not flags['can_review']:
            raise PermissionDenied('Only the assigned Engineer can correct this editable package.')
        if decision == 'record':
            if not reason.strip() or not isinstance(ids, list) or not 1 <= len(ids) <= 50:
                raise ValidationError('Select extracted records and provide a correction reason.')
            known = {f.get('finding_key'): f for f in payload.get('findings', [])}
            updates = {}
            for ident in ids:
                if ident not in known or not isinstance((corrections or {}).get(ident), dict):
                    raise ValidationError('Choose an extracted record from this submission.')
                if known[ident].get('field_hint') in field_map(c):
                    require_field_editable(c, known[ident]['field_hint'])
                change = corrections[ident]
                value, unit = change.get('value'), change.get('unit', known[ident].get('unit', ''))
                if not isinstance(unit, str) or len(unit) > 40 or len(json.dumps(value, allow_nan=False)) > 8000:
                    raise ValidationError('The corrected value or measurement unit is invalid.')
                target = field_map(c).get(known[ident].get('field_hint'))
                if target and target['type'] == 'number' and value not in (None, ''):
                    numeric_evidence_value(target, {**known[ident], 'value': value, 'unit': unit})
                updates[ident] = {'value': value, 'unit': unit, 'verification_status': 'confirmed',
                    'measured': False, 'corrected_by': request.user.pk, 'correction_reason': reason[:4000]}
            SurveyProcessingEvent.objects.create(revision=revision, actor=request.user, action='record', reason=reason[:4000], payload={'findings': updates})
            return revision
        if decision == 'engineer_complete':
            from .template_views import field_is_locked
            if any(not item.get('accepted') and not field_is_locked(c, item['id']) for item in payload['checklist_items']):
                raise ValidationError('Review every checklist item, including explicit missing / not-applicable dispositions.')
            if (payload.get('conflicts') or payload.get('missing')) and not reason.strip():
                raise ValidationError('Record how outstanding evidence gaps and conflicts were reviewed before completing this package.')
            verify_originals(revision)
            render_drawing_set(revision, payload)
            apply_reviewed_checklist(c, revision, payload, request.user)
            SurveyProcessingEvent.objects.get_or_create(revision=revision, actor=request.user, action=decision,
                payload={'review_digest': signature}, defaults={'reason': reason[:4000]})
            return revision
        if decision == 'geometry':
            if not reason.strip() or not isinstance(drawing_records, list) or len(drawing_records) > 200:
                raise ValidationError('Provide a measurement verification reason and at most 200 drawing records.')
            allowed_sources = set(revision.source_analyses.exclude(source_id__startswith='mapping:').values_list('source_id', flat=True))
            for item in drawing_records:
                if not isinstance(item, dict) or item.get('unit') not in {'mm', 'cm', 'm'}:
                    raise ValidationError('Each measured drawing record needs explicit units.')
                if item.get('kind') not in {'equipment', 'line', 'boundary', 'dimension', 'connection'}:
                    raise ValidationError('Choose a supported measured drawing record type.')
                source_id = item.get('source_id') or next((s.get('source_id') for s in item.get('sources', []) if isinstance(s, dict)), None)
                if source_id not in allowed_sources or item.get('verified') is not True:
                    raise ValidationError('Confirm measurements against a source in this submission.')
                for key in ['x', 'y', 'width', 'height']:
                    if key in item and (type(item[key]) not in (int, float) or not math.isfinite(item[key]) or abs(item[key]) > 1000000):
                        raise ValidationError('Drawing coordinates must be finite measured values within supported bounds.')
                if item.get('kind') in {'line', 'boundary', 'dimension', 'connection'}:
                    points = item.get('points')
                    if not isinstance(points, list) or not 2 <= len(points) <= 128 or any(
                        not isinstance(point, list) or len(point) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1000000 for v in point) for point in points):
                        raise ValidationError('Measured drawing points must be finite numeric coordinate pairs.')
                if item.get('kind') == 'dimension' and (type(item.get('value')) not in (int, float) or not math.isfinite(item['value']) or not 0 < item['value'] <= 1000000):
                    raise ValidationError('A dimension needs a positive finite recorded value.')
                item.update(verification_status='confirmed', measurement_basis='site_measured', sources=[{'source_id': source_id}], verified_by=request.user.pk)
            payload['drawing_records'] = drawing_records
            render_drawing_set(revision, payload)
            SurveyProcessingEvent.objects.create(revision=revision, actor=request.user, action=decision, reason=reason[:4000], payload={'drawing_records': drawing_records})
            return revision
        if decision == 'accept_additional':
            if not reason.strip():
                raise ValidationError('Explain acceptance of additional checklist proposals.')
            proposals = payload.get('suggested_items', [])
            if not isinstance(ids, list) or not ids or any(type(i) is not int or not 0 <= i < len(proposals) for i in ids):
                raise ValidationError('Select a suggested item.')
            accepted = payload.get('accepted_additional_items', [])
            chosen = []
            for i in ids:
                if proposals[i] not in accepted and proposals[i] not in chosen:
                    chosen.append(proposals[i])
            if chosen:
                SurveyProcessingEvent.objects.create(revision=revision, actor=request.user, action=decision, reason=reason[:4000], payload={'items': chosen})
            return revision
        if decision not in {'accept', 'correct', 'reject'} or not isinstance(ids, list) or not 1 <= len(ids) <= 3000 or len(set(ids)) != len(ids):
            raise ValidationError('Choose checklist items and a supported review decision.')
        if decision in {'correct', 'reject'} and not reason.strip():
            raise ValidationError('A correction or rejection reason is required.')
        by_id = {i['id']: i for i in payload['checklist_items']}
        updates = {}
        for ident in ids:
            if ident not in by_id:
                raise ValidationError('Unknown checklist item.')
            item = by_id[ident]
            require_field_editable(c, ident)
            field = field_map(c)[ident]
            value = (corrections or {}).get(ident, item['value'])
            if item.get('conflict') and decision == 'accept':
                raise ValidationError('Resolve conflicting evidence with a reasoned correction.')
            if decision == 'reject':
                updates[ident] = {'accepted': True, 'status': 'Missing', 'value': None, 'reason': reason[:4000]}
            else:
                if field.get('system') and value != c.site_id:
                    raise ValidationError('The linked site ID must match the saved survey.')
                if value not in (None, '', [], {}) and field['type'] != 'photo':
                    validate_answer(field, value)
                status = 'Missing' if value in (None, '', [], {}) else 'Not applicable' if isinstance(value, str) and value.lower() in {'n/a', 'not applicable'} else 'Confirmed from evidence' if item['sources'] else 'Reported'
                if status in {'Missing', 'Not applicable'} and not reason.strip():
                    raise ValidationError('Provide a reason for missing information or non-applicability.')
                updates[ident] = {'accepted': True, 'status': status, 'value': value, 'proposed_answer': value, 'conflict': False, 'reason': reason[:4000]}
        # Decisions populate this generated revision, never silently overwrite the
        # source survey or invalidate its immutable submission. Export is explicit.
        SurveyProcessingEvent.objects.get_or_create(revision=revision, actor=request.user, action=decision, reason=reason[:4000], payload={'items': updates})
        return revision


def apply_reviewed_checklist(c, revision, payload, actor):
    """Explicit Engineer completion copies validated values and confirmed evidence.

    The input snapshot remains immutable. The append-only application receipt
    binds the exact resulting source digest, so later edits invalidate review.
    """
    from .template_service import field_map, validate_answer
    from .template_views import require_field_editable
    from .field_photo_service import schema_digest
    from .photo_models import PhotoPlacement, PhotoEvidence
    fields = field_map(c)
    answers = deepcopy(c.answer_data)
    custom = answers.setdefault('custom', {})
    changed = False
    sections = {f['id']: section['id'] for section in c.schema_snapshot['sections'] for f in section['fields']}
    for item in payload['checklist_items']:
        from .template_views import field_is_locked
        if field_is_locked(c, item['id']):
            continue
        if not item.get('accepted'):
            raise ValidationError('Every generated checklist item must have an Engineer disposition.')
        field = fields[item['id']]
        if item['status'] == 'Missing':
            continue  # Missing remains visible; required-field validation still applies.
        require_field_editable(c, item['id'])
        value = item['value']
        if not field.get('system') and field['type'] != 'photo' and value not in (None, '', [], {}):
            validate_answer(field, value)
            if custom.get(item['id']) != value:
                custom[item['id']] = value
                changed = True
        for source in item.get('sources', []):
            ident = source.get('source_id', '')
            if not ident.startswith('photo:'):
                continue
            try:
                photo_id = int(ident.split(':')[1])
            except ValueError:
                continue
            photo = PhotoEvidence.objects.filter(pk=photo_id, checklist=c).first()
            if not photo:
                raise ValidationError('A reviewed photo no longer belongs to this survey.')
            link, created = PhotoPlacement.objects.get_or_create(photo=photo, field_id=item['id'], schema_digest=schema_digest(c),
                defaults={'section_id': sections[item['id']], 'status': 'confirmed', 'confidence': item['confidence'],
                    'reason': 'Engineer confirmed in survey processing revision ' + str(revision.number),
                    'reviewed_by': actor, 'reviewed_at': timezone.now()})
            if not created and link.status == 'proposed':
                link.status, link.reviewed_by, link.reviewed_at = 'confirmed', actor, timezone.now()
                link.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
            # Existing manual/confirmed/rejected decisions are never overwritten.
    if changed:
        c.answer_data = answers
        c.save(update_fields=['answer_data', 'updated_at'])
    source_digest = digest(freeze_data(c))
    SurveyProcessingEvent.objects.get_or_create(revision=revision, actor=actor, action='applied',
        payload={'source_digest': source_digest, 'review_digest': review_digest(payload)})
