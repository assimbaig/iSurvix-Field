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
              'owned':source.created_by_id==request.user.pk} for source in template_scope(request.user).order_by('-created_at')]
    return {'can_create':can_create,'sources':sources,'wizard_step':1,
        'allowed_industries':[{'code':code,'name':code.title()} for code in sorted(allowed)],
        'workflow_choices':[{'id':code,'label':code.replace('_',' ').title()} for code,industry in service.WORKFLOWS.items() if industry in allowed],**extra}


@login_required
@never_cache
@require_http_methods(['GET','POST'])
@guarded_write
def wizard(request):
    service.guard(request.user)
    extra={};status=200
    if request.method=='POST':
        service.guard(request.user,True)
        try:
            action=request.POST.get('action')
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
                    if template.published or template.created_by_id!=request.user.pk:
                        raise ValidationError('Only your unpublished drafts can be modified. Replicate this source first.')
                return redirect('checklist_wizard_edit',template_id=template.pk)
            if action=='preview_import':
                batch=service.preview_import(request.user,request.FILES.get('workbook'))
                extra={'import_batch':batch,'import_preview':service.preview_context(batch)}
            elif action=='commit_import':
                batch=service.commit_import(request.user,request.POST.get('import_id'),request.POST.get('expected_digest'))
                messages.success(request,'Reviewed workbook created as separate drafts. Open each draft to review and publish.')
                from django.urls import reverse
                return redirect(reverse('checklist_wizard')+'?import_id='+str(batch.pk)+'&complete=1')
            else:raise ValidationError('Choose a supported Wizard action.')
        except WorkbookValidationError as error:
            extra={'import_errors':error.errors};status=400
        except ValidationError as error:
            extra={'error':'; '.join(error.messages)};status=400
    elif request.GET.get('import_id'):
        batch=service.get_batch(request.user,request.GET['import_id'])
        extra={'import_batch':batch,'import_preview':service.preview_context(batch)}
    return render(request,'dashboards/checklist_wizard.html',context(request,**extra),status=status)


@login_required
@never_cache
@require_http_methods(['GET','POST'])
@guarded_write
def edit(request,template_id):
    service.guard(request.user,True)
    template=get_object_or_404(template_scope(request.user),pk=template_id)
    if not template.published and template.created_by_id!=request.user.pk:
        raise PermissionDenied('Replicate this source into your own draft before editing it.')
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
