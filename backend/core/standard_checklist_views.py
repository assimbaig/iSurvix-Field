"""Shared standard library; scoped Admin copies remain ordinary editable drafts."""
import json
from copy import deepcopy
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render,redirect
from django.views.decorators.http import require_GET,require_http_methods
from django.views.decorators.cache import never_cache
from .standard_checklist_service import catalog_for,entry_for,selection_payload
from .standard_checklists import build_standard
from .template_service import validate_definition
from .access import is_super_admin
from .governance_views import lock_governance,audit,guarded_write
from .models import ChecklistTemplate

def page(request,error='',status=200):
    standards=catalog_for(request.user)
    selected_key=request.POST.get('key',request.GET.get('key',''))
    selected=next((s for s in standards if s['key']==selected_key),standards[0] if standards else None)
    submitted=request.method=='POST'
    form_name=request.POST.get('name','') if submitted else ''
    form_rooms=request.POST.get('rooms','[]') if submitted else '[]'
    form_stages=request.POST.getlist('stages') if submitted else [stage['id'] for stage in (selected or {}).get('stages',[])]
    return render(request,'dashboards/standard_checklists.html',{
        'standards':standards,'can_create':not is_super_admin(request.user),
        'selected_key':selected['key'] if selected else '', 'selected_standard':selected,
        'form_name':form_name,'form_rooms':form_rooms,'form_stages':form_stages,'form_submitted':submitted,
        'form_state':{'submitted':submitted,'name':form_name,'rooms':form_rooms,'stages':form_stages},
        'active_view':'standard_checklists','error':error,
        'wizard_mode':request.POST.get('wizard')=='1' or request.GET.get('wizard')=='1'},status=status)

@require_http_methods(['GET','POST'])
@never_cache
@guarded_write
def library(request):
    catalog_for(request.user)
    if request.method=='GET':return page(request)
    if is_super_admin(request.user):
        raise PermissionDenied('Super Admin administers the shared catalog. Project Admins create and publish project checklist drafts.')
    stored=[]
    try:
        try:size=int(request.META.get('CONTENT_LENGTH') or 0)
        except (TypeError,ValueError):raise ValidationError('Invalid checklist request length.')
        if size>64000:raise ValidationError('The checklist request is too large.')
        if request.content_type=='application/json' and len(request.body)>64000:
            raise ValidationError('The checklist request is too large.')
        data=json.loads(request.body) if request.content_type=='application/json' else request.POST
        if not isinstance(data,dict) and not hasattr(data,'getlist'):raise ValidationError('Provide a checklist selection.')
        key=data.get('key');entry=entry_for(request.user,key)
        name=data.get('name',entry['name'])
        if not isinstance(name,str) or not name.strip() or len(name.strip())>160:
            raise ValidationError('Provide a checklist name of at most 160 characters.')
        stages,rooms=selection_payload(data)
        if key=='construction_inspection_all' and stages is None:stages=[]
        definition=build_standard(key,stages=stages,rooms=rooms)
        if key!='telecom_survey_default':definition['title']=name.strip()
        validate_definition(definition)
        with transaction.atomic():
            lock_governance(request.user);entry_for(request.user,key)
            draft=ChecklistTemplate(name=name.strip(),definition=deepcopy(definition),created_by=request.user,
                client_left_name='Nokia' if key=='telecom_survey_default' else '',
                client_right_name='TAWAL' if key=='telecom_survey_default' else '')
            if key=='telecom_survey_default':
                for slot,filename in [('left','nokia.png'),('right','tawal.png')]:
                    asset=Path(settings.BASE_DIR)/'static/core/img'/filename
                    if asset.is_file():
                        field=getattr(draft,f'client_{slot}_logo')
                        field.save(filename,ContentFile(asset.read_bytes()),save=False);stored.append(field)
            draft.save()
            audit(request.user,'standard_checklist_draft_created',getattr(request.user.profile,'project',None),
                template_id=draft.pk,standard_key=key,standard_version=1,
                room_count=len(rooms),section_count=len(definition['sections']))
        return redirect('checklist_wizard_edit' if data.get('wizard')=='1' or request.GET.get('wizard')=='1' else 'checklist_template_edit',template_id=draft.pk)
    except (ValidationError,ValueError,TypeError) as error:
        for field in stored:field.delete(save=False)
        message='; '.join(error.messages) if isinstance(error,ValidationError) else str(error)
        if request.content_type=='application/json':return JsonResponse({'error':message},status=400)
        return page(request,error=message,status=400)

@require_GET
@never_cache
def preview(request):
    try:
        key=request.GET.get('key','');entry=entry_for(request.user,key)
        stages=request.GET.getlist('stages') if 'stages' in request.GET else None
        rooms=[]
        if 'rooms' in request.GET:
            _,rooms=selection_payload({'rooms':request.GET['rooms']})
        definition=build_standard(key,stages=stages,rooms=rooms)
        validate_definition(definition)
        return JsonResponse({'standard':entry,'definition':definition})
    except (ValidationError,ValueError,TypeError) as error:
        message='; '.join(error.messages) if isinstance(error,ValidationError) else str(error)
        return JsonResponse({'error':message},status=400)
