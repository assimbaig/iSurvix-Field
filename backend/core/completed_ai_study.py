"""One read-only completed-study presentation; never a review or release action."""
import math
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET
from . import category_intake as intake, survey_processing as pipeline
from .access import role_for
from .models import Profile
from .survey_processing_views import guarded


def text(value):
    if value is None or value == '' or value == [] or value == {}:
        return 'Not recorded'
    if isinstance(value,dict):return '; '.join(str(k)+': '+text(v) for k,v in value.items())[:4000]
    if isinstance(value,list):return '; '.join(text(v) for v in value)[:4000]
    return str(value)[:4000]


def observation_rows(finding):
    def first(*keys):
        return next((finding[k] for k in keys if finding.get(k) not in (None,'',[],{})),None)
    value=first('value')
    measured=text(value)+((' '+str(finding['unit'])) if value is not None and finding.get('unit') else '')
    defect=first('defects','defect','issues','visible_defects')
    if defect is None and finding.get('category')=='defect':
        defect=first('notes','evidence_quote','value')
    return [('Product / type',text(first('component','product_type','equipment_type','label','category'))),
        ('Manufacturer',text(first('manufacturer'))),('Model',text(first('model'))),
        ('Defect / issue',text(defect)),
        ('Extracted value',measured),
        *([('Recorded unit',text(finding['unit']))] if value is None and finding.get('unit') else []),
        ('Description',text(first('notes','description'))),
        ('Visible source',text(first('evidence_quote'))),
        ('Matching reason',text(first('mapping_reason','reason'))),
        ('Uncertainty',text(first('uncertainty'))),('Source confidence',text(first('confidence'))),
        ('Evidence basis',text(first('basis'))),('Checklist hint',text(first('field_hint')))]


def context_rows(checklist,photo):
    metadata=photo.get('metadata') if isinstance(photo.get('metadata'),dict) else {}
    gps=metadata.get('gps')
    coordinates=None
    if isinstance(gps,dict):
        lat,lon=gps.get('latitude'),gps.get('longitude')
        if (type(lat) in (int,float) and type(lon) in (int,float) and
            math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):
            coordinates=str(lat)+', '+str(lon)
    return [('Site ID',checklist.site_id),('Capture date & time',text(metadata.get('captured_at'))),
        ('Coordinates',text(coordinates)),('Uploaded category',text(photo.get('group'))),
        ('Photo ID',str(photo['id'])),('Original filename',text(photo.get('filename')))]


@login_required
@require_GET
@guarded
def workspace(request,checklist_id):
    c,_=intake.access(request,checklist_id)
    if not intake.enabled(c):raise Http404()
    revisions=c.processing_revisions.select_related('processing_job').order_by('-number')
    selected=request.GET.get('revision_id')
    revision=get_object_or_404(revisions,pk=selected) if selected and selected.isdecimal() else revisions.first()
    if selected and not selected.isdecimal():raise Http404()
    client=role_for(request.user)==Profile.Roles.CLIENT
    # Existing clients receive released, current and explicitly reviewed content
    # only. Giving the same presentation does not expose private QA proposals.
    payload=None
    if client:
        if not revision or not pipeline.current(revision):raise Http404()
        payload=intake.reviewed_payload(revision)
        if not intake.completion_event(revision) or not revision.drawing_sets.filter(
            released=True,review_digest=pipeline.review_digest(payload)).exists():raise Http404()
    ready=bool(revision and revision.processing_job.status=='ready_for_review')
    photos=revision.snapshot.get('photos',[]) if revision else []
    page=Paginator(photos,1).get_page(request.GET.get('photo',1))
    photo=next(iter(page.object_list),None)
    findings=[]
    if ready and photo:
        if client:
            source='photo:'+str(photo['id'])
            for item in payload.get('checklist_items',[]):
                if item.get('accepted') and any(s.get('source_id')==source for s in item.get('sources',[])):
                    findings.append({'component':item.get('label'),'value':item.get('value'),
                        'unit':item.get('unit'),'notes':'Released QA-reviewed information.'})
        else:
            record=revision.source_analyses.filter(source_id='photo:'+str(photo['id'])).first()
            if record:
                if pipeline.digest(record.payload)!=record.digest:
                    raise ValidationError('Saved source analysis failed integrity verification.')
                findings=[f for f in record.payload.get('findings',[]) if isinstance(f,dict)]
    sections=[{'title':text(finding.get('component') or finding.get('product_type') or
        finding.get('equipment_type') or 'Observation'),
        'category':text(finding.get('category')) if finding.get('category') else '',
        'rows':observation_rows(finding)} for finding in findings]
    response=render(request,'dashboards/completed_ai_study.html',{'checklist':c,'revision':revision,
        'study_ready':ready,'photo':photo,'photo_page':page,'study_sections':sections,
        'study_context':context_rows(c,photo) if photo else [],
        'study_client':client})
    response['Cache-Control']='private, no-store'
    response['X-Content-Type-Options']='nosniff'
    response['X-Robots-Tag']='noindex, nofollow'
    return response
