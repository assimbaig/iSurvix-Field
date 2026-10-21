"""Checklist Wizard: reviewable drafts, immutable import previews and real XLSX."""
from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods,require_GET
from . import checklist_wizard_service as service
from .access import is_super_admin
from .checklist_workbook import WorkbookValidationError
from .models import ChecklistTemplate
from .template_views import template_scope
from .governance_views import guarded_write


def context(request,**extra):
    allowed=service.guard(request.user)
    can_create=not is_super_admin(request.user)
    sources=[{'id':source.pk,'name':source.name,'version':source.version,'published':source.published,
              'owned':source.created_by_id==request.user.pk,'disabled':source.disabled} for source in template_scope(request.user).order_by('-created_at')]
    return {'can_create':can_create,'sources':sources,'wizard_step':1,'active_view':'checklists',
        'allowed_industries':[{'code':code,'name':code.title()} for code in sorted(allowed)],
        'workflow_choices':[{'id':code,'label':code.replace('_',' ').title()} for code,industry in service.WORKFLOWS.items() if industry in allowed],**extra}


@login_required
@never_cache
@require_http_methods(['GET','POST'])
@guarded_write
def wizard(request):
    service.guard(request.user)
    extra={};status=200
    target_id=request.POST.get('append_target') or request.GET.get('target')
    if target_id:
        from .checklist_lifecycle import require_editable
        if not target_id.isascii() or not target_id.isdigit() or len(target_id)>19:raise Http404()
        target=get_object_or_404(template_scope(request.user),pk=target_id)
        try:require_editable(request.user,target)
        except ValidationError as error:return HttpResponse('; '.join(error.messages),status=409)
        extra['append_target']=target
    if request.method=='GET' and len(request.GET.get('copy',''))<=19 and request.GET.get('copy','').isascii() and request.GET.get('copy','').isdigit():
        source=get_object_or_404(template_scope(request.user),pk=request.GET['copy'])
        extra.update(copy_source=source.pk,form_name=(source.name+' copy')[:160])
    if request.method=='POST':
        service.guard(request.user,True)
        try:
            action=request.POST.get('action')
            if action in {'recommend_sections','recommend_points','create_recommended'}:
                from .checklist_recommendations import recommend,selected_sections,create_recommended
                name=service.valid_name(request.POST.get('name'))
                industry=request.POST.get('industry');workflow=request.POST.get('workflow_type')
                catalog=recommend(request.user,industry,workflow)
                selected=request.POST.getlist('sections');custom=request.POST.get('custom_sections','')
                extra={'recommendations':catalog,'form_name':name,'recommend_step':'sections',
                       'recommend_industry':industry,'recommend_workflow':workflow,'custom_sections':custom,
                       'selected_sections':selected,'sections_reviewed':bool(request.POST.get('catalog_digest')),
                       'chosen_points':request.POST.getlist('points'),'points_reviewed':action=='create_recommended'}
                try:
                    import json
                    entered=json.loads(request.POST.get('custom_items','[]'))
                    extra['entered_points']=entered if isinstance(entered,list) and len(entered)<=3000 else []
                except (ValueError,TypeError):extra['entered_points']=[]
                if action!='recommend_sections':
                    if request.POST.get('catalog_digest')!=catalog['digest']:
                        raise ValidationError('Recommendations changed. Review the sections again.')
                    extra['accepted_sections']=selected_sections(catalog,selected,custom)
                    extra['selected_sections']=selected;extra['recommend_step']='points'
                if action=='create_recommended':
                    template=create_recommended(request.user,name,industry,workflow,catalog['digest'],selected,custom,
                        request.POST.getlist('points'),request.POST.get('custom_items','[]'))
                    return redirect('checklist_wizard_edit',template_id=template.pk)
                return render(request,'dashboards/checklist_recommendations.html',context(request,**extra))
            if action=='create_blank':
                template=service.create_blank(request.user,request.POST.get('name'),request.POST.get('industry'),request.POST.get('workflow_type'))
                return redirect('checklist_wizard_edit',template_id=template.pk)
            if action in {'edit','replicate'}:
                source_id=request.POST.get('source_id','')
                if len(source_id)>19 or not source_id.isascii() or not source_id.isdigit():raise ValidationError('Choose a checklist source.')
                if action=='replicate':template=service.replicate(request.user,int(source_id),request.POST.get('name'))
                else:
                    template=get_object_or_404(template_scope(request.user),pk=int(source_id))
                    service.source_identity(template,request.user)
                    if template.published or template.disabled or template.checklists.exists():
                        raise ValidationError('Only your unpublished drafts can be modified. Replicate this source first.')
                return redirect('checklist_wizard_edit',template_id=template.pk)
            if action=='preview_import':
                batch=service.preview_import(request.user,request.FILES.get('workbook'),target_id)
                extra={**extra,'import_batch':batch,'import_preview':service.preview_context(batch)}
            elif action=='commit_import':
                batch=service.commit_import(request.user,request.POST.get('import_id'),request.POST.get('expected_digest'))
                if batch.payload.get('append_target'):
                    messages.success(request,'Reviewed points added to the draft. Existing checkpoints were retained.')
                    return redirect('checklist_wizard_edit',template_id=batch.payload['append_target']['id'])
                messages.success(request,'Reviewed workbook created as separate drafts. Open each draft to review and publish.')
                from django.urls import reverse
                return redirect(reverse('checklist_wizard')+'?import_id='+str(batch.pk)+'&complete=1')
            else:raise ValidationError('Choose a supported Wizard action.')
        except WorkbookValidationError as error:
            extra={**extra,'import_errors':error.errors};status=400
        except ValidationError as error:
            extra={**extra,'error':'; '.join(error.messages)};status=400
    elif request.GET.get('import_id'):
        batch=service.get_batch(request.user,request.GET['import_id'])
        extra={'import_batch':batch,'import_preview':service.preview_context(batch)}
    return render(request,'dashboards/checklist_recommendations.html' if extra.get('recommendations') else 'dashboards/checklist_wizard.html',context(request,**extra),status=status)


@login_required
@never_cache
@require_http_methods(['GET','POST'])
@guarded_write
def edit(request,template_id):
    service.guard(request.user,True)
    template=get_object_or_404(template_scope(request.user),pk=template_id)
    service.source_identity(template,request.user)
    from .template_views import template_builder
    return template_builder(request,template_id=template_id,wizard_mode=True)


def workbook_response(raw,filename):
    response=HttpResponse(raw,content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition']='attachment; filename="'+filename+'"'
    response['Cache-Control']='private, no-store'
    response['X-Content-Type-Options']='nosniff'
    return response


@login_required
@never_cache
@require_GET
def workbook(request):
    allowed=service.guard(request.user)
    industry=request.GET.get('industry') or ('telecom' if 'telecom' in allowed else sorted(allowed)[0])
    if industry not in allowed:raise PermissionDenied('This workbook is outside your assigned industry.')
    if request.GET.get('format')=='simple':
        path=Path(settings.BASE_DIR)/'static/core/templates/iSurvix_Checklist_One_Page.xlsx'
        if not path.is_file():raise Http404('The one-page sample is unavailable.')
        raw=path.read_bytes()
        if industry=='construction':
            # Runtime industry adaptation of the authored sample, not a new format.
            from io import BytesIO
            from openpyxl import load_workbook
            book=load_workbook(BytesIO(raw));sheet=book['Checklist']
            sheet['E2']='construction';sheet['H2']='construction_inspection'
            buffer=BytesIO();book.save(buffer);raw=buffer.getvalue()
        return workbook_response(raw,'iSurvix_Checklist_One_Page.xlsx')
    path=Path(settings.BASE_DIR)/'static/core/templates/iSurvix_Checklist_Wizard_Template.xlsx'
    if industry=='telecom' and path.is_file():raw=path.read_bytes()
    else:
        from .checklist_workbook import export_workbook
        raw=export_workbook(service.example_records(industry))
    return workbook_response(raw,'iSurvix_Checklist_Wizard_'+industry+'.xlsx')


@login_required
@never_cache
@require_GET
def export(request,template_id):
    service.guard(request.user,True)
    template=get_object_or_404(template_scope(request.user),pk=template_id)
    identity=service.source_identity(template,request.user)
    from .checklist_workbook import export_workbook
    try:raw=export_workbook([{'key':f'checklist_{template.pk}','name':template.name,**identity,'definition':template.definition}])
    except WorkbookValidationError as error:
        return HttpResponse(str(error),status=422,content_type='text/plain')
    return workbook_response(raw,f'iSurvix_Checklist_{template.pk}_v{template.version}.xlsx')


@login_required
@never_cache
@require_http_methods(['GET','POST'])
@guarded_write
def library(request):
    service.guard(request.user,True)
    from .checklist_lifecycle import table_rows,lifecycle
    from django.db import transaction
    from django.core.paginator import Paginator
    if request.method=='POST':
        try:
            selected=request.POST.getlist('selected')
            if not 1<=len(selected)<=100 or any(not key.isascii() or not key.isdigit() or len(key)>19 for key in selected):
                raise ValidationError('Select between 1 and 100 checklists.')
            if request.POST.get('action')=='delete' and request.POST.get('confirm_delete')!='yes':
                raise ValidationError('Confirm the selected draft deletions before continuing.')
            with transaction.atomic():
                for key in set(selected):
                    lifecycle(request.user,int(key),request.POST.get('action'),request.POST.get('token_'+key))
            messages.success(request,'Checklist action completed for '+str(len(set(selected)))+' selected record(s).')
            return redirect(request.get_full_path())
        except ValidationError as error:
            messages.error(request,'; '.join(error.messages))
    rows=table_rows(request.user)
    counts={state:sum(row['state']==state for row in rows) for state in ['Draft','Published','Disabled']}
    q=request.GET.get('q','').strip()[:160];state=request.GET.get('state','')
    filtered=[row for row in rows if (not q or q.casefold() in row['name'].casefold()) and (not state or row['state']==state)]
    page=Paginator(filtered,25).get_page(request.GET.get('page'))
    return render(request,'dashboards/checklist_library.html',{'rows':page,'page':page,'counts':counts,'total':len(rows),'search':q,'filter_state':state,'active_view':'checklists'})
