"""Two-step assignment intake and editable site information for authorized users."""
import csv
import json
from io import StringIO
from copy import deepcopy
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.http import HttpResponse,JsonResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods,require_GET
from .models import AssignmentIntakeBatch,Profile,Checklist
from .access import accessible_projects,is_super_admin,role_for
from .governance_views import guarded_write,lock_governance,audit
from .template_views import survey_access,require_field_editable
from .field_intake_service import preview_csv,commit_batch,general_fields,site_information_fields,validated_general_info


def assign_guard(actor):
    if is_super_admin(actor) or role_for(actor) not in {Profile.Roles.TEAM_LEAD,Profile.Roles.ADMIN}:
        raise PermissionDenied('Task assignment requires Team Lead or project administration.')


def catalog(actor):
    projects=accessible_projects(actor).filter(checklist_template__published=True,checklist_template__disabled=False).select_related('checklist_template').order_by('name')
    return projects,[{'project_id':p.pk,'project_name':p.name,'fields':[f for f in general_fields(p.checklist_template.definition).values() if not f.get('system')]} for p in projects]


@login_required(login_url='/login/')
@require_http_methods(['GET','POST'])
@never_cache
@guarded_write
def bulk_assign(request):
    assign_guard(request.user)
    batch=None
    error=''
    status=200
    if request.method=='POST':
        try:
            with transaction.atomic():
                lock_governance(request.user)
                assign_guard(request.user)
                if request.POST.get('action')=='preview':
                    upload=request.FILES.get('csv_file')
                    if not upload:
                        raise ValidationError('Choose a UTF-8 CSV file.')
                    batch=preview_csv(request.user,upload,request.POST.get('project',''))
                    status=400 if batch.errors else 200
                elif request.POST.get('action')=='commit':
                    batch_id=request.POST.get('batch_id','')
                    if not batch_id.isascii() or not batch_id.isdigit():
                        raise ValidationError('Choose a valid preview batch.')
                    batch=get_object_or_404(AssignmentIntakeBatch.objects.select_for_update(),pk=int(batch_id))
                    results=commit_batch(request.user,batch)
                    messages.success(request,f'{len(results)} assignments created. Site information remains editable by the assigned Engineer.')
                    return redirect('governance_home')
                else:
                    raise ValidationError('Preview the CSV before committing assignments.')
        except ValidationError as exc:
            error='; '.join(exc.messages)
            status=409 if request.POST.get('action')=='commit' else 400
    projects,fields=catalog(request.user)
    selected=request.POST.get('project') or request.GET.get('project','')
    return render(request,'dashboards/assignment_bulk.html',{'active_view':'tasks','bulk_projects':projects,'bulk_catalog':fields,'batch':batch,'error':error,'selected_bulk_project':selected},status=status)


@login_required(login_url='/login/')
@require_GET
@never_cache
def bulk_sample(request):
    assign_guard(request.user)
    projects,_=catalog(request.user)
    project_id=request.GET.get('project','')
    if not project_id.isascii() or not project_id.isdigit():
        return HttpResponse('Choose an accessible project.',status=400)
    project=get_object_or_404(projects,pk=int(project_id))
    fields=[fid for fid,f in general_fields(project.checklist_template.definition).items() if not f.get('system')]
    output=StringIO(newline='')
    writer=csv.writer(output)
    writer.writerow(['project','engineer','site_id','site_name','address','city','region','latitude','longitude','description','quality_reviewer','workflow_type','governance_mode','asset_reference','coordinate_source','coordinate_crs','l2_reviewer','l3_approver','client_review_required','customer_reviewer','review_reason',*[f'field:{fid}' for fid in fields]])
    response=HttpResponse(output.getvalue(),content_type='text/csv; charset=utf-8')
    response['Content-Disposition']='attachment; filename="site-assignment-template.csv"'
    return response


@require_http_methods(['GET','POST'])
@never_cache
@guarded_write
def site_information(request,checklist_id):
    access=survey_access(request,checklist_id)
    checklist=access['checklist']
    if request.method=='GET':
        return JsonResponse({'fields':site_information_fields(checklist),'site_id':checklist.site_id,'can_edit':bool(access['can_edit']),'updated_at':checklist.updated_at.isoformat(),'intake_metadata':checklist.intake_metadata})
    try:
        survey_access(request,checklist_id,edit=True)
        if len(request.body)>64000:
            raise ValidationError('Site information is too large.')
        payload=json.loads(request.body)
        if not isinstance(payload,dict) or not isinstance(payload.get('answers'),dict):
            raise ValidationError('Provide an answers object.')
        with transaction.atomic():
            lock_governance(request.user)
            survey_access(request,checklist_id,edit=True)
            checklist=Checklist.objects.select_for_update().get(pk=checklist_id)
            if payload.get('expected_updated_at')!=checklist.updated_at.isoformat():
                return JsonResponse({'error':'The site information changed. Reload before saving.'},status=409)
            answers=validated_general_info(checklist.schema_snapshot,payload['answers'])
            for fid in answers:
                require_field_editable(checklist,fid)
            data=deepcopy(checklist.answer_data or {})
            custom=data.setdefault('custom',{})
            previous={fid:custom.get(fid) for fid in answers}
            custom.update(answers)
            checklist.answer_data=data
            checklist.review_history=[*(checklist.review_history or []),{'action':'site_information_updated','by':request.user.pk,'name':request.user.username,'time':timezone.now().isoformat(),'previous':previous,'fields':list(answers)}]
            checklist.save(update_fields=['answer_data','review_history','updated_at'])
            audit(request.user,'site_information_updated',checklist.project,checklist_id=checklist.pk,field_ids=list(answers))
        return JsonResponse({'status':'success','updated_at':checklist.updated_at.isoformat()})
    except (ValidationError,ValueError,TypeError) as exc:
        return JsonResponse({'error':'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Invalid site information.'},status=400)
