"""Versioned, actor-independent local evidence processing. No approval writes."""
import base64
import hashlib
import json
import os
import time
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from django.core.exceptions import ValidationError
from .evidence_learning import digest, current_release, find_analysis, get_or_create_analysis, release_references

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / '.local' / 'models' / 'embeddings'
SEMANTIC_MODEL = 'BAAI/bge-small-en-v1.5'
PROMPT_VERSION = 'subject-check-v1'

def model_fingerprint(model):
    from .photo_service import ollama
    for item in ollama('/api/tags').get('models', []):
        if item.get('name') == model and not item.get('remote_model') and not item.get('remote_host'):
            value = item.get('digest', '').removeprefix('sha256:')
            if len(value) == 64 and all(c in '0123456789abcdef' for c in value):
                return value
    raise ValidationError('The local model fingerprint could not be verified. Check the installed model.')

_model_checks={}
def display_model_fingerprint(model):
    previous=_model_checks.get(model)
    if previous and time.monotonic()-previous[0]<15:return previous[1]
    result=model_fingerprint(model)
    _model_checks[model]=(time.monotonic(),result)
    return result

@lru_cache(maxsize=1)
def tool_fingerprint():
    from . import local_evidence_tools, evidence_rules
    packages = {name: version(name) for name in ['rapidocr-onnxruntime', 'onnxruntime', 'fastembed']}
    files = {}
    for base in [CACHE, Path(__import__('rapidocr_onnxruntime').__file__).parent / 'models']:
        for path in sorted(base.rglob('*')):
            if path.is_file() and path.suffix in {'.onnx', '.json', '.txt'}:
                files[str(path.relative_to(base))] = hashlib.sha256(path.read_bytes()).hexdigest()
    from . import photo_metadata
    return digest({'packages': packages, 'weights': files, 'tools': local_evidence_tools.TOOL_VERSION,
                   'pipeline_source': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   'observation_source': hashlib.sha256(Path(photo_metadata.__file__).read_bytes()).hexdigest(),
                   'source': hashlib.sha256(Path(local_evidence_tools.__file__).read_bytes()).hexdigest(),
                   'rules_source': hashlib.sha256(Path(evidence_rules.__file__).read_bytes()).hexdigest()})

@lru_cache(maxsize=1)
def embedding_engine():
    CACHE.mkdir(parents=True, exist_ok=True)
    os.environ['HF_HOME'] = str(CACHE / 'huggingface')
    os.environ['HF_HUB_CACHE'] = str(CACHE / 'huggingface' / 'hub')
    os.environ['FASTEMBED_CACHE_PATH'] = str(CACHE)
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=SEMANTIC_MODEL, cache_dir=str(CACHE), threads=2,
                         providers=['CPUExecutionProvider'], local_files_only=True)

_embedding_vectors = {}

def embed(texts):
    # A site's checklist is constant across hundreds of photos. Encode each
    # distinct text once per worker, retaining batching and bounded memory.
    texts = list(texts)
    current = {text:_embedding_vectors[text] for text in texts if text in _embedding_vectors}
    missing = list(dict.fromkeys(text for text in texts if text not in _embedding_vectors))
    if missing:
        vectors = [vector.tolist() for vector in embedding_engine().embed(missing)]
        if len(vectors) != len(missing):
            raise ValueError('The local embedding model returned an incomplete batch.')
        if len(_embedding_vectors) + len(missing) > 4096:
            _embedding_vectors.clear()
        _embedding_vectors.update(zip(missing, vectors))
        current.update(zip(missing, vectors))
    return [current[text][:] for text in texts]


def observation_identity(photo, context):
    from .photo_metadata import METADATA_VERSION, METADATA_SYSTEM, METADATA_SCHEMA
    return digest({'photo':photo.sha256,'model':context['model_digest'],
                   'prompt':METADATA_VERSION,'instructions':METADATA_SYSTEM,'schema':METADATA_SCHEMA})


def prepare_observation(photo, model, context, check, progress=None, *, raw=None):
    """Stage one commits reusable vision output before OCR or matching can fail."""
    from .photo_models import PhotoObservation
    from .photo_metadata import extract_metadata, validate_metadata, metadata_signature
    if raw is None:
        with photo.original.open('rb') as source:
            raw = source.read()
    if hashlib.sha256(raw).hexdigest() != photo.sha256:
        raise ValidationError('The original photo fingerprint changed. Analysis was stopped.')
    check()
    key = observation_identity(photo, context)
    record = PhotoObservation.objects.filter(photo=photo,cache_key=digest([photo.pk,key])).first()
    if record is not None:
        if record.model_digest != context['model_digest'] or digest(record.payload) != record.payload_digest:
            raise ValidationError('Saved photo analysis integrity could not be verified.')
        observation = validate_metadata(record.payload)
    else:
        if model_fingerprint(model)!=context['model_digest'] or tool_fingerprint()!=context['tool_fingerprint']:
            raise ValidationError('The pinned local analysis tools changed. Apply current AI rules explicitly.')
        observation = None
        for prior in photo.evidence_analyses.order_by('-pk'):
            if prior.payload.get('observation_key') == key:
                if digest(prior.payload) != prior.payload_digest:
                    raise ValidationError('Saved evidence integrity could not be verified.')
                observation = validate_metadata(prior.payload['observations'])
                break
        if observation is None:
            if photo.analysis_metadata:
                legacy={'rules_version':'legacy-observation-v1','model_version':model,'tool_version':'legacy-unrecorded',
                        'prompt_version':'legacy-unrecorded','legacy_signature':photo.analysis_signature,
                        'legacy_observation_digest':digest(photo.analysis_metadata)}
                get_or_create_analysis(photo.checklist,photo,{'observations':photo.analysis_metadata,
                    'legacy_signature':photo.analysis_signature,'versions':legacy,'assessments':[],
                    'notice':'Preserved historical observation. Original model-file fingerprint was not recorded.'},legacy)
            photo.analysis_signature=''
            observation=extract_metadata(photo,model,lease_check=check,progress_callback=progress,image_source=raw)
        check()
        record,_=PhotoObservation.objects.get_or_create(cache_key=digest([photo.pk,key]),defaults={
            'photo':photo,'model_digest':context['model_digest'],'payload':observation,'payload_digest':digest(observation)})
        if digest(record.payload) != record.payload_digest:
            raise ValidationError('Saved photo analysis integrity could not be verified.')
        observation=validate_metadata(record.payload)
    check()
    # Refresh the UI cache from the versioned result; this never creates a link.
    photo.analysis_metadata=observation
    photo.analysis_signature=metadata_signature(photo,model)
    photo.save(update_fields=['analysis_metadata','analysis_signature'])
    if progress:
        progress('extracting_metadata',True)
    return observation

def latest_context(checklist):
    for job in checklist.photo_jobs.order_by('-pk'):
        if job.schema == checklist.schema_snapshot and job.progress.get('evidence_context'):
            return job.progress['evidence_context']
    return None

def processing_context(checklist, model, adopt=False):
    from .evidence_rules import RULE_VERSION
    previous = latest_context(checklist)
    fingerprint = model_fingerprint(model)
    tools = tool_fingerprint()
    if previous and not adopt:
        if previous.get('model_digest') != fingerprint or previous.get('tool_fingerprint') != tools:
            raise ValidationError('Saved AI rules or the local model changed. Explicitly apply current AI rules to create a new analysis version.')
        return previous
    release = current_release(checklist.project_id)
    return {'rules_version': RULE_VERSION, 'model_version': model,
            'model_digest': fingerprint, 'tool_version': 'local-tools-v1', 'tool_fingerprint': tools,
            'prompt_version': PROMPT_VERSION, 'semantic_model': SEMANTIC_MODEL,
            'release_id': release.pk if release else None, 'release_version': release.version if release else 0,
            'release_digest': release.digest if release else digest([])}

def saved_state(checklist, can_apply=False, learning_url=''):
    from .field_photo_service import schema_digest
    from django.db.models import F
    from .evidence_learning import analysis_key
    pinned=latest_context(checklist) or {}
    records=[]; seen=set()
    for record in checklist.evidence_analyses.filter(photo__isnull=False,photo_sha256=F('photo__sha256'),schema_digest=schema_digest(checklist)).select_related('photo').order_by('-pk'):
        if record.photo_id in seen: continue
        if digest(record.payload)!=record.payload_digest:
            raise ValidationError('Saved evidence integrity could not be verified. Preserve the record and request recovery.')
        seen.add(record.photo_id)
        records.append({'id':record.pk,'photo_id':record.photo_id,'created_at':record.created_at.isoformat(),
                        'current':bool(pinned) and record.cache_key==analysis_key(checklist,record.photo,pinned),
                        'versions':{'rules':record.rules_version,'model':record.model_version,'tools':record.tool_version,
                                    'prompt':record.prompt_version,'release':record.payload.get('versions',{}).get('release_version',0)},
                        'payload':record.payload,'digest':record.payload_digest})
    release=current_release(checklist.project_id)
    changed=not pinned or any(not r['current'] for r in records) or len(records)<checklist.photo_evidence.count() or pinned.get('rules_version')!='subject-first-v1' or pinned.get('prompt_version')!=PROMPT_VERSION
    try:
        changed=changed or pinned.get('tool_fingerprint')!=tool_fingerprint()
        if pinned:
            changed=changed or pinned.get('model_digest')!=display_model_fingerprint(pinned['model_version'])
    except (ImportError, OSError, ValueError, ValidationError):
        changed=True
    return {'records':records,'pinned_context':pinned,
            'current_release':{'id':release.pk,'version':release.version} if release else None,
            'update_available':changed or (release.version if release else 0)>pinned.get('release_version',0),
            'can_apply':bool(can_apply),'learning_url':learning_url}

def targeted_vision(photo, model, request, check):
    from .photo_service import ollama, verify_vision
    from .evidence_rules import validate_targeted_assessments
    verify_vision(model);check()
    ids=[field['id'] for field in request['fields']]
    schema={'type':'object','additionalProperties':False,'required':['assessments'],'properties':{'assessments':{
        'type':'array','maxItems':len(ids),'items':{'type':'object','additionalProperties':False,
        'required':['field_id','outcome','reason','visible_evidence','missing_evidence'], 'properties':{
        'field_id':{'type':'string','enum':ids},'outcome':{'type':'string','enum':['supported','insufficient','contradictory']},
        'reason':{'type':'string','minLength':20,'maxLength':320},
        'visible_evidence':{'type':'string','maxLength':320},
        'missing_evidence':{'type':'array','maxItems':3,'items':{'type':'string','maxLength':160}}}}}}}
    from PIL import Image
    from io import BytesIO
    with photo.original.open('rb') as source:raw=source.read()
    if hashlib.sha256(raw).hexdigest()!=photo.sha256:raise ValidationError('Original photo fingerprint changed.')
    picture=Image.open(BytesIO(raw)).convert('RGB');picture.thumbnail((1024,1024))
    buffer=BytesIO();picture.save(buffer,format='JPEG',quality=85)
    image=base64.b64encode(buffer.getvalue()).decode('ascii')
    result=ollama('/api/chat',{'model':model,'stream':False,'think':False,'format':schema,
        'messages':[{'role':'system','content':request['system']+' Keep each explanation to one short sentence. A supported result requires a concrete visible_evidence sentence of at least 20 characters. If that cannot be provided, return insufficient. Use at most three short missing-evidence entries.'},{'role':'user','content':json.dumps({k:v for k,v in request.items() if k!='system'}),'images':[image]}],
        'options':{'temperature':0,'seed':42,'num_ctx':4096,'num_predict':768}})
    check()
    if result.get('done_reason')=='length': raise ValueError('Targeted evidence output exceeded its bound.')
    value=json.loads(result['message']['content'])
    # A model's ungrounded "supported" claim is never evidence. Downgrade only
    # that claim to insufficient, then run the unchanged strict validator over
    # the entire response. Unknown fields, injected answers and malformed data
    # still fail; one uncertain subject need not stop hundreds of other photos.
    withhold_ungrounded_claims(value)
    validate_targeted_assessments(value,set(ids))
    return value


def withhold_ungrounded_claims(value):
    if not isinstance(value,dict) or not isinstance(value.get('assessments'),list):
        return
    for item in value['assessments']:
        if (isinstance(item,dict) and set(item)=={'field_id','outcome','reason','visible_evidence','missing_evidence'}
                and item.get('outcome')=='supported'
                and isinstance(item.get('reason'),str) and item['reason'].strip() and len(item['reason'])<=1600
                and isinstance(item.get('visible_evidence'),str)
                and len(item['visible_evidence'].strip())<20
                and isinstance(item.get('missing_evidence'),list)
                and len(item['missing_evidence'])<6
                and all(isinstance(text,str) and text.strip() and len(text)<=200 for text in item['missing_evidence'])):
            item.update(outcome='insufficient',reason='AI support claim withheld because no concrete visible description was provided.',
                        visible_evidence='',missing_evidence=[*item['missing_evidence'],'Clear, specific photographic evidence of this checklist subject.'])

def reviewed_examples(observation, references, checklist, schema):
    """Retrieve peer-reviewed examples as hints, never transferable approvals."""
    from .field_photo_service import schema_digest
    candidates=[r for r in references if r.get('project_id')==checklist.project_id
                and r.get('company_id')==checklist.project.company_id
                and r.get('schema_digest')==schema_digest(checklist) and r.get('caption')]
    if not candidates:return []
    # Publication and source scope gate the corpus before semantic retrieval.
    candidates=candidates[-100:]
    vectors=embed([observation['caption']]+[str(r['caption'])[:400] for r in candidates])
    import math
    def cosine(a,b):
        n=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
        return sum(x*y for x,y in zip(a,b))/n if n else 0
    ranked=sorted([(cosine(vectors[0],v),r) for v,r in zip(vectors[1:],candidates)],key=lambda pair:-pair[0])
    return [{'field_id':r['field_id'],'caption':r['caption'],'polarity':r['polarity'],
             'correction_id':r['correction_id'],'advisory_only':True} for score,r in ranked[:3] if score>=0.7]

def analyze(photo, schema, model, context, check, progress):
    from .photo_metadata import assessments_to_drafts
    from .local_evidence_tools import extract_local_tools, semantic_similarities
    from .evidence_rules import evaluate_evidence, verify_shortlist, apply_release_references
    from .evidence_models import EvidenceRuleRelease
    from .field_photo_service import schema_digest
    checklist=photo.checklist
    with photo.original.open('rb') as source:raw=source.read()
    if hashlib.sha256(raw).hexdigest()!=photo.sha256:
        raise ValidationError('The original photo fingerprint changed. Analysis was stopped.')
    existing=find_analysis(checklist,photo,context)
    if existing:
        if progress:progress('matching_checklist',True)
        return existing.payload['drafts']
    if model_fingerprint(model)!=context['model_digest'] or tool_fingerprint()!=context['tool_fingerprint']:
        raise ValidationError('The pinned local analysis tools changed. Apply current AI rules explicitly.')
    observation_key=observation_identity(photo,context)
    observation=prepare_observation(photo,model,context,check,progress,raw=raw)
    check()
    tools=extract_local_tools(raw,source_metadata=photo.metadata)
    if tools.get('errors'):
        raise ValidationError('Local text or QR analysis did not complete. Retry the photo job; no incomplete assessment was saved.')
    fields=[f for s in schema.get('sections',[]) for f in s.get('fields',[])]
    if progress:progress('matching_checklist',False)
    scores={}
    for start in range(0,len(fields),500):
        scores.update(semantic_similarities(observation,fields[start:start+500],embed))
    assessments=evaluate_evidence(observation,schema,tools,scores)
    release=EvidenceRuleRelease.objects.get(pk=context['release_id'],project_id=checklist.project_id) if context.get('release_id') else None
    if release and release.digest!=context.get('release_digest'):
        raise ValidationError('The pinned correction release fingerprint changed. Analysis was stopped.')
    references=release_references(release)
    examples=reviewed_examples(observation,references,checklist,schema)
    def verify(request):
        request={**request,'reviewed_examples':examples,
                 'example_instruction':'Reviewed examples are advisory retrieval hints, not evidence for this image. Verify only what is actually visible in the current image. Never transfer a result or an approval.'}
        return targeted_vision(photo,model,request,check)
    verified=verify_shortlist(observation,assessments,schema,verify)
    verification={item['field_id']:item for item in verified}
    for item in assessments:
        result=verification.get(item['field_id'])
        if result and not item.get('hard_blocked'):
            item.update(outcome=result['outcome'],targeted_verification=result)
            item['reasons']=[*item['reasons'],result['reason']]
            item['missing_evidence']=result['missing_evidence']
    assessments=apply_release_references(assessments,references,{'project_id':checklist.project_id,
        'company_id':checklist.project.company_id,'site_id':checklist.site_id,'photo_sha256':photo.sha256,'schema_digest':schema_digest(checklist)})
    drafts=assessments_to_drafts(observation,schema,assessments,photo.group)
    from .photo_service import validate_drafts
    validate_drafts({'drafts':drafts},fields);check()
    record,reused=get_or_create_analysis(checklist,photo,{'assessments':assessments,'tools':tools,'observations':observation,
        'observation_key':observation_key,'reviewed_example_ids':[r['correction_id'] for r in examples],
        'drafts':drafts,'versions':context},context)
    return record.payload['drafts']
