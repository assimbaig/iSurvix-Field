"""Batched image/text retrieval. Similarity is never proof or an approval."""
import hashlib
import json
import math
import os
import time
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from django.db import transaction
from PIL import Image,ImageOps
from .evidence_learning import digest
from .photo_models import PhotoEvidence,PhotoJob,PhotoSearchVector,PhotoSearchResult

ROOT=Path(__file__).resolve().parents[2]
MODELS=ROOT/'.local/models/photo-search'
STATE=ROOT/'.local/photo-search-worker'
VERSION='clip-retrieval-v1'
EXPECTED={'vision':'c68d3d9a200ddd2a8c8a5510b576d4c94d1ae383bf8b36dd8c084f94e1fb4d63',
          'text':'4dbe762b11e36488304471e439cde89da053ad7acaddbf9e096745d142ec8d8b'}

@lru_cache(maxsize=1)
def manifest():
    value=json.loads((MODELS/'manifest.json').read_text())
    if any(value[kind].get('model_sha256')!=sha for kind,sha in EXPECTED.items()):
        raise ValidationError('The pinned image-search model manifest changed.')
    return value

@lru_cache(maxsize=1)
def model_identity():
    from importlib.metadata import version
    configs={kind:{name:hashlib.sha256((MODELS/kind/name).read_bytes()).hexdigest()
                   for name in spec['files'] if name!='model.onnx'} for kind,spec in manifest().items()}
    return digest({'models':manifest(),'policy':VERSION,'source':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   'configuration_files':configs,'fastembed':version('fastembed'),'onnxruntime':version('onnxruntime')})

@lru_cache(maxsize=1)
def encoders():
    # Verify actual local vision weights before any project image is analyzed.
    manifest()
    for kind,sha in EXPECTED.items():
        with (MODELS/kind/'model.onnx').open('rb') as source:
            if hashlib.file_digest(source,'sha256').hexdigest()!=sha:
                raise ValidationError('A local image-search model fingerprint changed.')
    config=json.loads((MODELS/'vision/config.json').read_text())
    if config.get('model_type')!='clip_vision_model':raise ValidationError('A local vision encoder is required.')
    os.environ['HF_HOME']=str(MODELS/'hub')
    os.environ['FASTEMBED_CACHE_PATH']=str(MODELS)
    from fastembed import ImageEmbedding,TextEmbedding
    common={'cache_dir':str(MODELS),'threads':2,'providers':['CPUExecutionProvider'],'local_files_only':True}
    vision=ImageEmbedding('Qdrant/clip-ViT-B-32-vision',specific_model_path=str(MODELS/'vision'),**common)
    text=TextEmbedding('Qdrant/clip-ViT-B-32-text',specific_model_path=str(MODELS/'text'),**common)
    return vision,text

def normalize(vector):
    if hasattr(vector,'tolist'):vector=vector.tolist()
    if not isinstance(vector,list) or len(vector)!=512 or any(type(v) not in {float,int} or not math.isfinite(v) for v in vector):
        raise ValidationError('Invalid image-search vector.')
    norm=math.sqrt(sum(v*v for v in vector))
    if norm<1e-8:raise ValidationError('Empty image-search vector.')
    return [float(v/norm) for v in vector]

def catalog(checklist):
    return [{'id':f['id'],'label':f['label'],'section':s.get('title',''),
             'text':('A site photograph showing '+s.get('title','')+': '+f['label'])[:300]}
            for s in checklist.schema_snapshot.get('sections',[]) for f in s.get('fields',[])
            if not f.get('system') and f.get('type') not in {'number','date','table'}
            and (f.get('type') in {'photo','inspection'} or f.get('photo_required') is True)]

_catalog_vectors={}
def encoded_catalog(checklist,identity):
    fields=catalog(checklist)
    key=digest([identity,fields])
    if key not in _catalog_vectors:
        _,text=encoders()
        vectors=[normalize(v) for v in text.embed([f['text'] for f in fields],batch_size=32)] if fields else []
        if len(vectors)!=len(fields):raise ValidationError('Incomplete checklist embeddings.')
        if len(_catalog_vectors)>=16:_catalog_vectors.clear()
        _catalog_vectors[key]=vectors
    return fields,_catalog_vectors[key]

def vector_key(photo,identity):return digest([photo.pk,photo.sha256,identity])
def result_key(photo,checklist,identity):return digest([vector_key(photo,identity),checklist.project_id,checklist.site_id,checklist.schema_snapshot])

def candidates(vector,fields,vectors):
    scores=sorted([(sum(a*b for a,b in zip(vector,other)),field) for field,other in zip(fields,vectors)],key=lambda pair:(-pair[0],pair[1]['id']))
    return [{'field_id':field['id'],'similarity':round(score,6),'status':'unverified',
             'notice':'Visual similarity only; inspect the original and checklist before linking.'}
            for score,field in scores[:3] if score>=0.20]

def authorized(job):
    from .template_views import survey_access
    if not job.requested_by_id:raise ValidationError('The requester is no longer available.')
    job.requested_by.refresh_from_db()
    if not job.requested_by.is_active:raise ValidationError('The requester no longer has access.')
    checklist=survey_access(SimpleNamespace(user=job.requested_by),job.checklist_id,edit=True)['checklist']
    if checklist.schema_snapshot!=job.schema:raise ValidationError('The checklist changed before fast matching.')
    return checklist

def process_batch(job,photos,check):
    from .field_photo_service import schema_digest
    started=time.perf_counter()
    checklist=authorized(job);identity=model_identity()
    fields,text_vectors=encoded_catalog(checklist,identity)
    encoded={};pending=[];images=[]
    records={r.cache_key:r for r in PhotoSearchVector.objects.filter(cache_key__in=[vector_key(p,identity) for p in photos])}
    for photo in photos:
        check()
        if photo.checklist_id!=checklist.pk:raise ValidationError('Photo belongs to another checklist.')
        with photo.original.open('rb') as source:raw=source.read()
        if hashlib.sha256(raw).hexdigest()!=photo.sha256:raise ValidationError('Original photo fingerprint changed.')
        record=records.get(vector_key(photo,identity))
        if record:
            if record.model_digest!=identity or digest(record.vector)!=record.payload_digest:raise ValidationError('Saved image vector integrity failed.')
            encoded[photo.pk]=normalize(record.vector)
        else:
            image=Image.open(BytesIO(raw));image.draft('RGB',(256,256))
            images.append(ImageOps.exif_transpose(image).convert('RGB'));pending.append(photo)
    if pending:
        vision,_=encoders();vectors=list(vision.embed(images,batch_size=32))
        if len(vectors)!=len(pending):raise ValidationError('Incomplete image embeddings.')
        for photo,vector in zip(pending,vectors):encoded[photo.pk]=normalize(vector)
    check();authorized(job)
    elapsed=time.perf_counter()-started
    payloads=[]
    for photo in photos:
        payload={'candidates':candidates(encoded[photo.pk],fields,text_vectors),'stage':'fast_suggestions',
                 'verification_complete':False,'approval':None,'version':VERSION,'source_sha256':photo.sha256,
                 'batch_photos':len(photos),'batch_compute_seconds':round(elapsed,6),'cached_vector':photo.pk not in {p.pk for p in pending}}
        payloads.append((photo,payload))
    with transaction.atomic():
        from .governance_views import lock_governance
        lock_governance(job.requested_by);authorized(job);check()
        for photo in photos:
            fresh=PhotoEvidence.objects.get(pk=photo.pk)
            if fresh.sha256!=photo.sha256:raise ValidationError('Photo fingerprint changed during fast matching.')
        PhotoSearchVector.objects.bulk_create([PhotoSearchVector(photo=p,cache_key=vector_key(p,identity),model_digest=identity,vector=encoded[p.pk],payload_digest=digest(encoded[p.pk])) for p in pending])
        PhotoSearchResult.objects.bulk_create([PhotoSearchResult(photo=p,cache_key=result_key(p,checklist,identity),model_digest=identity,schema_digest=schema_digest(checklist),payload=value,payload_digest=digest(value)) for p,value in payloads])
    return {'photos':len(photos),'seconds':round(time.perf_counter()-started,4),'photos_per_second':round(len(photos)/(time.perf_counter()-started),3)}

def worker_state(checklist_id,**value):
    STATE.mkdir(parents=True,exist_ok=True)
    target=STATE/(str(checklist_id)+'.json');temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps(value));temporary.replace(target)

def process_next():
    from .photo_queue import inference_lease
    if not (MODELS/'manifest.json').exists():return False
    identity=model_identity()
    # All model inference remains outside database transactions and web requests.
    for job in PhotoJob.objects.filter(status__in=['queued','running','completed','failed']).select_related('checklist','requested_by').order_by('-pk'):
        try:checklist=authorized(job)
        except (ValidationError,PermissionError):continue
        except Exception as error:
            from django.core.exceptions import PermissionDenied
            from django.http import Http404
            if isinstance(error,(PermissionDenied,Http404)):continue
            raise
        if job.schema!=checklist.schema_snapshot:continue
        # Retrieval belongs to the editable site workspace, independently of a
        # detailed job's remaining-photo subset after checkpoint recovery.
        photos=list(checklist.photo_evidence.order_by('pk'))
        keys={result_key(p,checklist,identity):p for p in photos}
        existing=set(PhotoSearchResult.objects.filter(cache_key__in=keys).values_list('cache_key',flat=True))
        pending=[p for key,p in keys.items() if key not in existing][:32]
        if not pending:continue
        with inference_lease('photo-search') as check:
            try:
                worker_state(checklist.pk,status='running',error='')
                metrics=process_batch(job,pending,check)
                worker_state(checklist.pk,status='ready',error='',**metrics)
                return True
            except Exception:
                worker_state(checklist.pk,status='error',error='Fast AI Analysis could not finish this batch. The worker retries automatically; detailed verification and saved evidence are preserved.')
                raise
    return False

def state(checklist,photos,page=1):
    from .field_photo_service import schema_digest
    identity=model_identity()
    keys=[result_key(p,checklist,identity) for p in photos]
    results=list(PhotoSearchResult.objects.filter(cache_key__in=keys,model_digest=identity,schema_digest=schema_digest(checklist)).order_by('photo_id'))
    for record in results:
        if digest(record.payload)!=record.payload_digest:raise ValidationError('Fast AI Analysis integrity failed.')
    pages=max(1,math.ceil(len(results)/2));page=max(1,min(page,pages))
    runtime={}
    try:runtime=json.loads((STATE/(str(checklist.pk)+'.json')).read_text())
    except (FileNotFoundError,ValueError):pass
    return {'enabled':True,'ready':len(results),'total':len(photos),'page':page,'pages':pages,
            'verification_complete':False,'runtime':runtime,'model':VERSION,
            'results':[{'id':r.pk,'photo_id':r.photo_id,'candidates':r.payload['candidates']} for r in results[(page-1)*2:page*2]]}
