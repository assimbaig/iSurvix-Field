"""Admin item picker: source snapshots stay immutable, selections become new drafts."""
import re
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .models import ChecklistTemplate
from .template_service import default_definition
from .template_views import is_template_admin,template_scope
from .checklist_selection import subset_definition
from .governance_views import audit,guarded_write,lock_governance


def selection_source(user,value,lock=False):
    if value in ('','original','master'):
        return default_definition(),None,'','Full original FDED checklist'
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{1,18}',value):
        raise ValidationError('Choose the original checklist or an available saved source.')
    sources=template_scope(user)
    if lock:
        sources=sources.select_for_update()
    source=get_object_or_404(sources,pk=int(value))
    return source.definition,source,str(source.pk),f'{source.name} - v{source.version}'


def selection_response(request,definition,source_id,source_name,name='',selected=None,error='',status=200):
    return render(request,'dashboards/checklist_selection.html',{
        'selection_catalog':definition['sections'],'source_name':source_name,'source_id':source_id,
        'sources':template_scope(request.user).order_by('name','-version','pk'),
        'selection_name':name,'selected_field_ids':selected or [],'error':error,
        'selection_total_count':sum(len(section['fields']) for section in definition['sections'])},status=status)


@require_http_methods(['GET','POST'])
@never_cache
@guarded_write
def select_checklist(request):
    if not is_template_admin(request):
        return HttpResponse('Project administration access is required.',status=403)
    value=request.POST.get('source','') if request.method=='POST' else request.GET.get('source','')
    name=request.POST.get('name','') if request.method=='POST' else ''
    selected=request.POST.getlist('field_ids') if request.method=='POST' else []
    stored=[]
    definition=default_definition()
    source_id=''
    source_name='Full original FDED checklist'
    try:
        if request.method=='GET':
            definition,source,source_id,source_name=selection_source(request.user,value)
            return selection_response(request,definition,source_id,source_name)
        with transaction.atomic():
            lock_governance(request.user)
            if not is_template_admin(request):
                return HttpResponse('Project administration access is required.',status=403)
            definition,source,source_id,source_name=selection_source(request.user,value,lock=True)
            chosen=subset_definition(definition,selected,name)
            attrs={'name':name.strip(),'definition':chosen,'published':False,'version':1,'created_by':request.user}
            if source:
                for slot in ('left','right'):
                    attrs[f'client_{slot}_name']=getattr(source,f'client_{slot}_name')
                    attrs[f'client_{slot}_logo']=getattr(source,f'client_{slot}_logo').name
            draft=ChecklistTemplate(**attrs)
            if source is None:
                for slot,filename in [('left','nokia.png'),('right','tawal.png')]:
                    asset=Path(settings.BASE_DIR)/'static'/'core'/'img'/filename
                    if asset.is_file():
                        field=getattr(draft,f'client_{slot}_logo')
                        field.save(filename,ContentFile(asset.read_bytes()),save=False)
                        stored.append(field)
            draft.save()
            profile=getattr(request.user,'profile',None)
            ordered_ids=[field['id'] for section in chosen['sections'] for field in section['fields']]
            audit(request.user,'template_subset_created',getattr(profile,'project',None),template_id=draft.pk,source_id=source.pk if source else 'original',source_name=source_name,selected_field_ids=ordered_ids,field_count=len(ordered_ids),section_count=len(chosen['sections']))
            return redirect('checklist_template_edit',template_id=draft.pk)
    except Exception as exc:
        # Only files created for the built-in branding are ours to remove.
        # Saved source branding remains referenced and is never altered/deleted.
        for field in stored:
            field.delete(save=False)
        if isinstance(exc,ValidationError):
            return selection_response(request,definition,source_id,source_name,name,selected,'; '.join(exc.messages),status=400)
        raise
