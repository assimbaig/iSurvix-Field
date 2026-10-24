"""Source-bound reuse and duplicate annotations; originals are never removed."""
import base64
import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db.models import Max
from PIL import ImageStat

VERSION = 'identical-model-input-1'


def visual_fingerprint(image):
    rgb = image.convert('RGB')
    small = rgb.resize((9, 8)).convert('L')
    values = list(small.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | int(values[row * 9 + col] > values[row * 9 + col + 1])
    dimensions = json.dumps(rgb.size).encode()
    stat = ImageStat.Stat(rgb.resize((32, 32)))
    return {'pixels_sha256': hashlib.sha256(dimensions + rgb.tobytes()).hexdigest(),
            'dhash': f'{bits:016x}', 'size': list(rgb.size),
            'variance': round(sum(stat.var) / 3, 3), 'colour': [round(x, 2) for x in stat.mean]}


def analysis_identity(source, model_digest):
    from .survey_processing import digest
    from .survey_evidence import (SYSTEM_PROMPT, observation_response_schema, EXTRACTION_VERSION,
                                  INFERENCE_OPTIONS, TOKEN_BOUNDS)
    image = source.get('image_b64', '')
    return digest({'version': VERSION, 'model': model_digest, 'extraction': EXTRACTION_VERSION,
        'options': INFERENCE_OPTIONS, 'token_bounds': TOKEN_BOUNDS,
        'prompt': SYSTEM_PROMPT, 'schema': observation_response_schema(source.get('field_catalog') or []),
        'image': hashlib.sha256(base64.b64decode(image, validate=True)).hexdigest() if image else '',
        'text': source.get('text', ''), 'metadata': source.get('metadata') or {},
        'schema_digest': source.get('schema_digest', ''), 'template_id': source.get('template_id'),
        'reference': source.get('reference', ''), 'catalog': source.get('field_catalog') or [],
        'source_type': source.get('source_type', '')})


class ObservationReuse:
    """Raw observations only, same task/model; no human answers or decisions."""
    def __init__(self, revision, model_digest):
        self.revision, self.model_digest, self.index = revision, model_digest, None
        self.pending_visuals = {}
        self.known_visuals = set()
        for event in revision.processing_events.filter(action='source_fingerprints'):
            self.known_visuals.update(event.payload.get('photos', {}))

    def _load(self):
        if self.index is not None:
            return
        from .survey_processing_models import SurveyProcessingRevision, SurveySourceAnalysis
        revisions = SurveyProcessingRevision.objects.filter(checklist_id=self.revision.checklist_id,
            processing_job__model_digest=self.model_digest).order_by('-number').values_list('pk', flat=True)[:20]
        self.index = {}
        for row in SurveySourceAnalysis.objects.filter(revision_id__in=revisions).exclude(
                source_id__startswith='mapping:').order_by('-pk').values(
                    'pk', 'revision_id', 'revision__number', 'source_id', 'payload__acceleration__identity'):
            key = row['payload__acceleration__identity']
            if key and key not in self.index:
                self.index[key] = row

    def lookup(self, source):
        from .survey_processing import digest
        from .survey_processing_models import SurveySourceAnalysis
        self._load()
        candidate = self.index.get(analysis_identity(source, self.model_digest))
        if candidate is None:
            return None
        row = (candidate if hasattr(candidate, 'payload') else
               SurveySourceAnalysis.objects.get(pk=candidate['pk'], revision__checklist_id=self.revision.checklist_id))
        if digest(row.payload) != row.digest:
            raise ValidationError('Saved reusable evidence analysis failed integrity verification.')
        payload = deepcopy(row.payload)
        previous = payload.get('source_id', row.source_id)
        payload.update(source_id=source['source_id'], source_type=source.get('source_type', ''),
                       reference=source.get('reference', ''), sha256=source.get('sha256', ''),
                       verification_status='needs_review')
        payload.pop('accepted', None)
        payload['performance'] = {'requests': 0, 'native': [], 'cache_hit': True}
        for index, finding in enumerate(payload.get('findings', [])):
            old_key = str(finding.get('finding_key', ''))
            finding.update(source_id=source['source_id'], reference=source.get('reference', ''),
                verification_status='needs_review', measured=False,
                finding_key=source['source_id'] + old_key[len(previous):] if old_key.startswith(previous)
                    else f"{source['source_id']}:finding:{index}")
            finding.pop('accepted', None)
        number = candidate.revision_number if hasattr(candidate, 'payload') else candidate['revision__number']
        return self.stamp(source, payload, reused_from={'revision_id': row.revision_id,
            'revision_number': number, 'source_id': row.source_id})

    def stamp(self, source, payload, *, reused_from=None):
        result = deepcopy(payload)
        result['acceleration'] = {'version': VERSION, 'identity': analysis_identity(source, self.model_digest),
            'visual': deepcopy(source.get('visual_fingerprint') or {}), 'reused_from': reused_from}
        return result

    def remember(self, source, payload):
        from .survey_processing import digest
        self._load()
        key = analysis_identity(source, self.model_digest)
        self.index.setdefault(key, SimpleNamespace(payload=deepcopy(payload), digest=digest(payload),
            source_id=source['source_id'], revision_id=self.revision.pk, revision_number=self.revision.number))

    def remember_legacy_visual(self, source, payload):
        parts = source['source_id'].split(':')
        visual = source.get('visual_fingerprint')
        if (len(parts) == 2 and parts[0] == 'photo' and parts[1].isdigit() and visual
                and parts[1] not in self.known_visuals
                and not (payload.get('acceleration') or {}).get('visual')):
            self.pending_visuals[parts[1]] = {'sha256': source['sha256'], 'visual': deepcopy(visual)}

    def flush_visuals(self):
        if not self.pending_visuals:
            return
        from .survey_processing import digest
        from .survey_processing_models import SurveyProcessingEvent
        photos = deepcopy(self.pending_visuals)
        identity = digest({'revision': self.revision.digest, 'photos': photos})
        if not self.revision.processing_events.filter(action='source_fingerprints', payload__identity=identity).exists():
            SurveyProcessingEvent.objects.create(revision=self.revision, actor_id=self.revision.submitted_by_id,
                action='source_fingerprints', payload={'photos': photos, 'identity': identity})
        self.known_visuals.update(photos)
        self.pending_visuals.clear()


def _near(a, b):
    try:
        if min(a['variance'], b['variance']) < 25:
            return False
        if abs(a['size'][0] / a['size'][1] - b['size'][0] / b['size'][1]) > .03:
            return False
        return ((int(a['dhash'], 16) ^ int(b['dhash'], 16)).bit_count() <= 3
                and max(abs(x - y) for x, y in zip(a['colour'], b['colour'])) <= 20)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return False


def photo_duplicates(revision):
    from .survey_processing import digest
    rows = revision.source_analyses.filter(source_id__startswith='photo:')
    last = rows.aggregate(last=Max('pk'))['last']
    indexed = revision.processing_events.filter(action='source_fingerprints')
    last_index = indexed.aggregate(last=Max('pk'))['last']
    key = f'qa-photo-duplicates:{revision.pk}:{revision.digest}:{last}:{last_index}'
    cached = cache.get(key)
    if cached is not None:
        return deepcopy(cached)
    result, seen, records = {}, [], {}
    allowed = {str(photo['id']): photo['sha256'] for photo in revision.snapshot.get('photos', [])}
    for event in indexed.order_by('pk'):
        photos = event.payload.get('photos', {})
        if digest({'revision': revision.digest, 'photos': photos}) != event.payload.get('identity'):
            raise ValidationError('Saved source fingerprint index failed integrity verification.')
        for ident, data in photos.items():
            if ident in allowed and data.get('sha256') == allowed[ident]:
                records[int(ident)] = (data.get('visual') or {}, None)
    for row in rows.order_by('pk'):
        parts = row.source_id.split(':')
        if len(parts) != 2 or not parts[1].isdigit():
            continue
        acceleration = row.payload.get('acceleration', {})
        if not acceleration:
            continue
        if digest(row.payload) != row.digest:
            raise ValidationError('Saved duplicate annotations failed integrity verification.')
        ident = int(parts[1])
        if str(ident) in allowed:
            records[ident] = (acceleration.get('visual') or {}, acceleration.get('reused_from'))
    numbers = dict(revision.checklist.processing_revisions.values_list('pk', 'number'))
    for ident, (visual, reused_from) in sorted(records.items()):
        if reused_from:
            reused_from = {**reused_from, 'revision_number': numbers.get(reused_from.get('revision_id'))}
        duplicate = None
        for previous, fingerprint in seen:
            if visual.get('pixels_sha256') and visual['pixels_sha256'] == fingerprint.get('pixels_sha256'):
                duplicate = {'kind': 'exact', 'photo_id': previous,
                    'reason': 'Decoded source pixels are identical. Originals and evidence links are retained.'}
                break
        if duplicate is None and visual:
            previous = next((pid for pid, fp in seen if _near(visual, fp)), None)
            if previous is not None:
                duplicate = {'kind': 'possible', 'photo_id': previous,
                    'reason': 'Similar image fingerprint. Compare originals; no evidence or analysis is skipped for similarity.'}
        result[ident] = {'duplicate': duplicate, 'analysis_reused': reused_from}
        if visual:
            seen.append((ident, visual))
    cache.set(key, result, timeout=60)
    return result
