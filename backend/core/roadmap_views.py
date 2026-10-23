"""Scoped pilot workflow, frozen reports and inspection-control forms."""
import json
import hashlib
from functools import wraps
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404,HttpResponse,JsonResponse,FileResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.http import require_GET,require_POST,require_http_methods
from .access import accessible_projects,role_for
from .models import Checklist,Profile,SubmissionRevision,InspectionFinding,PhotoEvidence
from .template_views import survey_access
from .independent_workflow import revision_state,review_revision
from .independent_workflow import is_frozen
from .roadmap_service import current_qualification,qualify_template,record_finding,finding_action


def validation_response(view):
    @wraps(view)
    def wrapped(*args,**kwargs):
        try:return view(*args,**kwargs)
        except ValidationError as exc:return HttpResponse('; '.join(exc.messages),status=409,content_type='text/plain')
        except (ValueError,TypeError,json.JSONDecodeError):return HttpResponse('Invalid form or photo selection. Return to the activity and check the supplied values.',status=400)
    return wrapped


class QualificationForm(forms.Form):
    workflow_type=forms.ChoiceField(choices=Checklist.WorkflowType.choices)
    criteria_reference=forms.CharField(max_length=4000,widget=forms.Textarea,label='Applicable client specification, standard/edition and clauses')
    inspection_method=forms.CharField(max_length=4000,widget=forms.Textarea,label='Approved method, evidence, units and acceptance criteria')
    reason=forms.CharField(max_length=4000,widget=forms.Textarea,label='Technical applicability and exclusions')


class ReviewPolicyForm(forms.Form):
    l2_reviewer=forms.ModelChoiceField(queryset=Profile.objects.none(),label='Quality Engineer')
    l3_approver=forms.ModelChoiceField(queryset=Profile.objects.none(),label='Team Lead')
    customer_required=forms.BooleanField(required=False,label='Client release required')
    customer_reviewer=forms.ModelChoiceField(queryset=Profile.objects.none(),required=False,label='Named Client reviewer')
    reason=forms.CharField(max_length=4000,widget=forms.Textarea)
    expected_updated_at=forms.CharField(widget=forms.HiddenInput)
    def __init__(self,*args,checklist,**kwargs):
        super().__init__(*args,**kwargs)
        from .access import users_for_project
        for field,role in [('l2_reviewer',Profile.Roles.QUALITY_ENGINEER),('l3_approver',Profile.Roles.TEAM_LEAD),('customer_reviewer',Profile.Roles.CLIENT)]:
            self.fields[field].queryset=users_for_project(checklist.project_id,{role})
        self.fields['expected_updated_at'].initial=checklist.updated_at.isoformat()


def can_configure_policy(actor,c,policy):
    from .review_route_service import route_for
    if route_for(c):return False
    from .access import can_access_project
    if not can_access_project(actor,c.project_id) or c.status not in {Checklist.Status.DRAFT,Checklist.Status.REJECTED}:
        return False
    if policy and policy.current_revision_id and not (policy.workflow_version==1 and revision_state(policy.current_revision) in {'returned','customer_rejected'}):
        return False
    return role_for(actor)==Profile.Roles.ADMIN or (role_for(actor)==Profile.Roles.TEAM_LEAD and c.status==Checklist.Status.DRAFT and c.intake_metadata.get('created_by')==actor.pk and not policy and not c.submission_revisions.exists())


class FindingForm(forms.Form):
    description=forms.CharField(max_length=4000,widget=forms.Textarea)
    severity=forms.ChoiceField(choices=[('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')])
    blocking=forms.BooleanField(required=False,initial=True)
    photo_ids=forms.JSONField(required=False,initial=list,label='Source photo IDs (JSON list)')
    due_date=forms.DateField(required=False,widget=forms.DateInput(attrs={'type':'date'}))


@login_required
@require_GET
def activity(request,checklist_id):
    access=survey_access(request,checklist_id)
    c=access['checklist']
    policy=getattr(c,'review_policy',None)
    current=policy.current_revision if policy else None
    state=revision_state(current) if current else 'draft'
    role=role_for(request.user)
    from .review_route_service import route_context
    routing=route_context(request.user,c)
    if routing:state='closed' if routing['stage']=='closed' else routing['stage']+'_'+routing['mode']
    quality_flow=bool(current and current.workflow_version>=2 or not current and policy and policy.workflow_version>=2)
    l2_role=Profile.Roles.QUALITY_ENGINEER if quality_flow else Profile.Roles.TEAM_LEAD
    l3_role=Profile.Roles.TEAM_LEAD if quality_flow else (Profile.Roles.ADMIN if role==Profile.Roles.ADMIN else Profile.Roles.PROJECT_MANAGER)
    return render(request,'dashboards/roadmap_activity.html',{'review_route':routing,'checklist':c,'can_configure_policy':can_configure_policy(request.user,c,policy),'policy_form':ReviewPolicyForm(checklist=c),'quality_flow':quality_flow,'policy':policy,'current_revision':current,'revision_state':state,'revisions':c.submission_revisions.order_by('-number').prefetch_related('decisions__actor'),'qualification':current_qualification(c),'findings':c.inspection_findings.prefetch_related('events__actor').order_by('-pk'),'finding_form':FindingForm(),'can_record_finding':bool(access.get('can_edit') and role==Profile.Roles.ENGINEER and c.user_id==request.user.pk),'can_validate':not routing and bool(policy and current and state=='submitted' and request.user.pk==policy.l2_reviewer_id and role==l2_role),'can_approve':not routing and bool(policy and current and state=='validated' and request.user.pk==policy.l3_approver_id and role==l3_role),'can_return':not routing and bool(policy and current and (state=='submitted' and request.user.pk==policy.l2_reviewer_id or state=='validated' and request.user.pk==policy.l3_approver_id)),'can_retest':bool(policy and not is_frozen(c) and c.status!=Checklist.Status.FINAL and request.user.pk in {policy.l2_reviewer_id,policy.l3_approver_id}),'can_qualify':role==Profile.Roles.TEAM_LEAD,'role':role})


@login_required
@require_POST
@validation_response
def policy_assign(request,checklist_id):
    from django.core.exceptions import PermissionDenied
    from .independent_workflow import configure_policy,policy_for
    c=survey_access(request,checklist_id)['checklist']
    if not can_configure_policy(request.user,c,policy_for(c)):
        raise PermissionDenied('This reviewer policy cannot be configured by this account at its current stage.')
    form=ReviewPolicyForm(request.POST,checklist=c)
    if not form.is_valid():
        return HttpResponse('Choose active project reviewers and record the assignment reason.',status=400)
    configure_policy(request.user,c,**form.cleaned_data)
    return redirect('roadmap_activity',checklist_id=c.pk)


@login_required
@require_POST
@validation_response
def quality_reviewer_assign(request,checklist_id):
    from django.contrib.auth.models import User
    from .quality_workflow import assign_quality_reviewer
    checklist=survey_access(request,checklist_id)['checklist']
    reviewer=get_object_or_404(User,pk=int(request.POST.get('quality_reviewer','0')))
    assign_quality_reviewer(request.user,checklist,reviewer,request.POST.get('reason',''),request.POST.get('expected_updated_at',''))
    return redirect('custom_checklist',checklist_id=checklist.pk)


@login_required
@require_POST
@validation_response
def quality_review(request,checklist_id):
    from .quality_workflow import review_quality
    checklist=survey_access(request,checklist_id)['checklist']
    review_quality(request.user,checklist,request.POST.get('decision',''),request.POST.get('reason',''),request.POST.get('expected_updated_at',''))
    return redirect('custom_checklist',checklist_id=checklist.pk)


@login_required
@require_POST
@validation_response
def revision_review(request,checklist_id,revision_id):
    c=survey_access(request,checklist_id)['checklist']
    revision=get_object_or_404(SubmissionRevision,pk=revision_id,checklist=c)
    review_revision(request.user,c,revision.pk,request.POST.get('action',''),request.POST.get('reason',''))
    return redirect('roadmap_activity',checklist_id=c.pk)


def scoped_revision(request,checklist_id,revision_id):
    from .independent_workflow import accessible_revision
    revision=accessible_revision(request.user,revision_id)
    if revision.checklist_id!=checklist_id:
        raise Http404()
    return revision.checklist,revision


@login_required
@require_GET
def revision_export(request,checklist_id,revision_id):
    c,revision=scoped_revision(request,checklist_id,revision_id)
    response=JsonResponse({'revision':revision.number,'digest':revision.digest,'snapshot':revision.snapshot,'decisions':list(revision.decisions.values('action','level','actor_id','reason','created_at'))})
    response['Content-Disposition']=f'attachment; filename="activity-{c.pk}-revision-{revision.number}.json"'
    response['Cache-Control']='private, no-store'
    return response


@login_required
@require_GET
def revision_report(request,checklist_id,revision_id):
    c,revision=scoped_revision(request,checklist_id,revision_id)
    response=render(request,'dashboards/roadmap_revision_report.html',{'checklist':c,'revision':revision,'record':revision.snapshot,'decisions':revision.decisions.select_related('actor'),'revision_state':revision_state(revision)})
    response['Cache-Control']='private, no-store'
    return response


@login_required
@require_GET
def revision_source(request,checklist_id,revision_id,photo_id):
    c,revision=scoped_revision(request,checklist_id,revision_id)
    source=next((item for item in revision.snapshot.get('photos',[]) if item['id']==photo_id),None)
    if not source:raise Http404()
    photo=get_object_or_404(PhotoEvidence,pk=photo_id,checklist=c,sha256=source['sha256'],original=source['original'])
    try:
        stream=photo.original.open('rb')
    except OSError:
        return HttpResponse('The frozen source file is unavailable. Contact the project administrator to restore the original from backup.',status=503)
    digest=hashlib.sha256()
    try:
        for block in iter(lambda:stream.read(65536),b''):digest.update(block)
    except OSError:
        stream.close()
        return HttpResponse('The frozen source could not be read. Contact the project administrator to check original storage.',status=503)
    if digest.hexdigest()!=source['sha256']:
        stream.close()
        return HttpResponse('The stored original no longer matches the frozen source hash. Contact the project administrator.',status=409)
    stream.seek(0)
    response=FileResponse(stream,as_attachment=True,filename=source['filename'],content_type={'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp'}.get(source.get('metadata',{}).get('format'),'application/octet-stream'))
    response['Cache-Control']='private, no-store'
    response['X-Content-Type-Options']='nosniff'
    return response


@login_required
@require_http_methods(['GET','POST'])
@validation_response
def qualify(request,project_id):
    project=get_object_or_404(accessible_projects(request.user),pk=project_id)
    form=QualificationForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        qualify_template(request.user,project,**form.cleaned_data)
        return redirect('roadmap_qualify',project_id=project.pk)
    return render(request,'dashboards/roadmap_qualification.html',{'project':project,'form':form,'can_qualify':role_for(request.user)==Profile.Roles.TEAM_LEAD,'qualifications':project.template_qualifications.select_related('reviewed_by','template').order_by('-pk')},status=400 if request.method=='POST' else 200)


@login_required
@require_POST
@validation_response
def finding_create(request,checklist_id):
    c=survey_access(request,checklist_id)['checklist']
    form=FindingForm(request.POST)
    if not form.is_valid():return HttpResponse(form.errors.as_text(),status=400,content_type='text/plain')
    record_finding(request.user,c,**form.cleaned_data)
    return redirect('roadmap_activity',checklist_id=c.pk)


@login_required
@require_POST
@validation_response
def finding_update(request,checklist_id,finding_id):
    c=survey_access(request,checklist_id)['checklist']
    finding=get_object_or_404(InspectionFinding,pk=finding_id,checklist=c)
    raw=request.POST.get('photo_ids','[]')
    if len(raw)>10000:raise ValueError('Too many photo references.')
    finding_action(request.user,finding,request.POST.get('action',''),request.POST.get('reason',''),json.loads(raw))
    return redirect('roadmap_activity',checklist_id=c.pk)
