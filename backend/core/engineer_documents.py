"""Versioned, immutable supporting documents for category-based site capture.

Document rows and original bytes are never removed on correction. Current-source
membership and Engineer classification live in intake metadata; old submissions
continue to reference their original immutable document records.
"""
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlencode
import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse

from .access import role_for
from .models import Checklist, Profile
from .survey_processing_models import SurveyDocument
from .survey_evidence import MAX_DOCUMENT_BYTES, validate_document


KEY='capture_documents'
VERSION=1
MAX_DOCUMENTS=50
MAX_BATCH=5
KINDS=[{'value':'hand_sketch','label':'Hand sketch'},{'value':'report','label':'Report'}]
LABELS={kind['value']:kind['label'] for kind in KINDS}


def configuration(c):
    value=(c.intake_metadata or {}).get(KEY,{})
    return value if isinstance(value,dict) and value.get('version')==VERSION else None


def limits():
    return {'max_batch':MAX_BATCH,'max_bytes':MAX_DOCUMENT_BYTES,'max_documents':MAX_DOCUMENTS,
            'accept':'.pdf,.xlsx,.jpg,.jpeg,.png,.webp','kinds':deepcopy(KINDS)}


def snapshot(c, records):
    config=configuration(c)
    if config is None:
        return records
    excluded=set(config.get('excluded',[]))
    kinds=config.get('kinds',{})
    return [{**record,'kind':kinds.get(str(record['id']),'unspecified')}
            for record in records if record['id'] not in excluded]


def retained_item_sources(revision,payload,field_id):
    """Saving photo selections must not erase a supporting report/sketch link.

    This does not add a document matcher. Only already proposed/saved sources
    from documents in this exact submission may survive a photo-only edit.
    """
    allowed={document['id'] for document in revision.snapshot.get('documents',[])}
    item=next((item for item in payload['checklist_items'] if item['id']==field_id),{})
    result=[]
    for source in item.get('sources',[]):
        parts=str(source.get('source_id','')).split(':')
        if len(parts)>=2 and parts[0]=='document' and parts[1].isdigit() and int(parts[1]) in allowed:
            if source not in result:result.append(deepcopy(source))
    return result


def rows(snapshot,c,*,revision=None,include_analysis=False):
    """Safe source DTO: Engineer gets source files, never model observations."""
    analyses={}
    if include_analysis and revision:
        from .survey_processing import digest
        for analysis in revision.source_analyses.filter(source_id__startswith='document:').order_by('pk'):
            if digest(analysis.payload)!=analysis.digest:
                raise ValidationError('Saved document analysis integrity verification failed.')
            parts=analysis.source_id.split(':')
            if len(parts)<2 or not parts[1].isdigit():
                continue
            analyses.setdefault(int(parts[1]),[]).append({
                'source_id':analysis.source_id,'reference':analysis.payload.get('reference',''),
                'findings':deepcopy(analysis.payload.get('findings',[])),
                'missing':deepcopy(analysis.payload.get('missing',[])),
                'conflicts':deepcopy(analysis.payload.get('conflicts',[])),
                'preview_url':reverse('survey_processing_source',args=[c.pk,analysis.pk])
                    if analysis.payload.get('preview_file') else ''})
    result=[]
    for document in snapshot.get('documents',[]):
        query={'revision_id':revision.pk} if revision else {}
        base=reverse('photo_capture_document',args=[c.pk,document['id']])
        original=base+('?' + urlencode(query) if query else '')
        is_image=document['content_type'] in {'image/jpeg','image/png','image/webp'}
        can_preview=is_image or document['content_type']=='application/pdf'
        kind=document.get('kind','unspecified')
        value={'id':document['id'],'filename':document['filename'],'kind':kind,
            'kind_label':LABELS.get(kind,'Supporting document'),'content_type':document['content_type'],
            'size':document['size'],'original_url':original,'is_image':is_image,'can_preview':can_preview,
            'preview_url':base+'?'+urlencode({**query,'preview':1}) if can_preview else ''}
        if document['content_type']=='application/pdf':
            value['raster_preview_url']=base+'?'+urlencode({**query,'preview':1,'raster':1,'page':1})
        if include_analysis:
            value['analyses']=analyses.get(document['id'],[])
        result.append(value)
    return result


def _save_configuration(c,kinds,excluded):
    c.intake_metadata={**(c.intake_metadata or {}),KEY:{'version':VERSION,'kinds':kinds,'excluded':excluded}}
    c.save(update_fields=['intake_metadata','updated_at'])


def _id(value):
    if type(value) is not int or value<=0:
        raise ValidationError('Choose a saved supporting document.')
    return value


def upload(request,checklist_id):
    from . import category_intake as capture,survey_upload_sessions as uploads
    from .governance_views import audit
    capture.access(request,checklist_id,edit=True)
    kind=request.POST.get('kind')
    if kind not in LABELS:
        raise ValidationError('Choose Hand sketch or Report before uploading supporting documents.')
    files=request.FILES.getlist('files')
    if not 1<=len(files)<=MAX_BATCH:
        raise ValidationError('Upload between one and five supporting documents per batch.')
    prepared=[validate_document(file) for file in files]
    stored=[];saved=[]
    try:
        with uploads.upload_batch(request,checklist_id,request.POST.get('processing_upload_token')) as session,transaction.atomic():
            Checklist.objects.select_for_update().get(pk=checklist_id)
            c,_=capture.access(request,checklist_id,edit=True)
            uploads.require_batch_open(c,session.token)
            capture._same_source(c,request.POST.get('expected_digest'))
            existing={doc.sha256:doc for doc in c.survey_documents.all()}
            if len(existing)+len({item['sha256'] for item in prepared}-set(existing))>MAX_DOCUMENTS:
                raise ValidationError('Use at most 50 supporting documents per survey, including retained originals.')
            config=configuration(c) or {'kinds':{},'excluded':[]}
            kinds=deepcopy(config.get('kinds',{}));excluded=set(config.get('excluded',[]))
            for item in prepared:
                doc=existing.get(item['sha256']);duplicate=doc is not None
                if doc is None:
                    doc=SurveyDocument(checklist=c,uploaded_by=request.user,filename=item['filename'],
                        sha256=item['sha256'],content_type=item['content_type'],size=item['size'])
                    doc.original.save(uuid.uuid4().hex+Path(item['filename']).suffix.lower(),ContentFile(item['raw']),save=False)
                    stored.append(doc.original)
                    doc.save();existing[item['sha256']]=doc
                restored=doc.pk in excluded
                changed=not duplicate or restored or kinds.get(str(doc.pk))!=kind
                excluded.discard(doc.pk);kinds[str(doc.pk)]=kind
                saved.append({'id':doc.pk,'duplicate':duplicate,'restored':restored})
                if changed:
                    audit(request.user,'capture_document_uploaded',c.project,checklist_id=c.pk,
                        document_id=doc.pk,kind=kind,restored=restored,sha256=doc.sha256)
            _save_configuration(c,kinds,sorted(excluded))
    except Exception:
        # Only newly allocated files from this rolled-back request are removed.
        # Existing and historical originals are never touched.
        for file in stored:
            file.delete(save=False)
        raise
    current=capture.state(request,checklist_id)
    by_id={doc['id']:doc for doc in current['documents']}
    return {'documents':[{**by_id[row['id']],**row} for row in saved],'state':current}


@transaction.atomic
def remove(request,checklist_id,data):
    from . import category_intake as capture
    from .governance_views import audit
    Checklist.objects.select_for_update().get(pk=checklist_id)
    c,_=capture.access(request,checklist_id,edit=True)
    doc=get_object_or_404(c.survey_documents,pk=_id(data.get('document_id')))
    config=configuration(c) or {'kinds':{},'excluded':[]}
    excluded=list(config.get('excluded',[]))
    if doc.pk not in excluded:
        capture._same_source(c,data.get('expected_digest'))
        excluded.append(doc.pk)
        _save_configuration(c,deepcopy(config.get('kinds',{})),excluded)
        audit(request.user,'capture_document_removed',c.project,checklist_id=c.pk,document_id=doc.pk)
    return capture.state(request,checklist_id)


def _pdf_raster(doc,page):
    """Bounded image derivative; never rewrite or browser-execute the original."""
    import hashlib
    import math
    import pymupdf
    with doc.original.open('rb') as original:
        raw=original.read(MAX_DOCUMENT_BYTES+1)
    if len(raw)>MAX_DOCUMENT_BYTES or hashlib.sha256(raw).hexdigest()!=doc.sha256:
        raise ValidationError('The PDF source bytes no longer match the saved original. Preview was not served.')
    try:
        with pymupdf.open(stream=raw,filetype='pdf') as pdf:
            if pdf.needs_pass:raise ValueError('Encrypted PDF')
            count=len(pdf)
            if not 1<=page<=count:raise Http404()
            name=f'survey_processing/document_previews/{doc.pk}/{doc.sha256}-page{page}-v1.png'
            if not default_storage.exists(name):
                selected=pdf[page-1];extent=max(selected.rect.width,selected.rect.height)
                if not math.isfinite(extent) or extent<=0:raise ValueError('Invalid page dimensions')
                scale=min(2.0,1598/extent)
                image=selected.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False).tobytes('png')
                default_storage.save(name,ContentFile(image))
    except Http404:
        raise
    except Exception as exc:
        raise ValidationError('The PDF preview could not be rendered. Its original is retained for authorized download.') from exc
    return default_storage.open(name,'rb'),count


def delivery(request,checklist_id,document_id):
    """An exact current source or a source frozen in an authorised revision."""
    from . import category_intake as capture
    c,_=capture.access(request,checklist_id)
    if role_for(request.user)==Profile.Roles.CLIENT:
        raise Http404()
    selected=request.GET.get('revision_id')
    if selected is not None:
        if not selected.isdigit():raise Http404()
        revision=get_object_or_404(c.processing_revisions,pk=int(selected))
        source=revision.snapshot
    else:
        source=capture.source_snapshot(c)
    record=next((doc for doc in source.get('documents',[]) if doc['id']==document_id),None)
    if record is None:raise Http404()
    doc=get_object_or_404(SurveyDocument,pk=document_id,checklist=c)
    if doc.sha256!=record['sha256'] or doc.original.name!=record['original']:
        raise ValidationError('The saved supporting document does not match its submitted source.')
    inline=request.GET.get('preview')=='1' and doc.content_type in {'image/jpeg','image/png','image/webp','application/pdf'}
    if request.GET.get('raster')=='1':
        if not inline or doc.content_type!='application/pdf':raise Http404()
        number=request.GET.get('page','1')
        if not number.isascii() or not number.isdigit() or len(number)>6:raise Http404()
        page=int(number)
        stream,count=_pdf_raster(doc,page)
        response=FileResponse(stream,content_type='image/png',filename=f'{doc.filename}.page-{page}.png')
        response['X-Document-Preview-Page']=str(page)
        response['X-Document-Preview-Pages']=str(count)
    else:
        response=FileResponse(doc.original.open('rb'),content_type=doc.content_type,
            as_attachment=not inline,filename=doc.filename)
    response['Cache-Control']='private, no-store'
    response['X-Content-Type-Options']='nosniff'
    response['X-Robots-Tag']='noindex, nofollow'
    if inline:response['Content-Security-Policy']="sandbox; default-src 'none'"
    return response
