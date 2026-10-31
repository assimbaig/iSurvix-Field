"""Invite-only, scoped administration; no cloud services or destructive resets."""
import hashlib
import secrets
import hmac
from urllib.parse import urlencode
from datetime import timedelta
from functools import wraps
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from .access import is_super_admin,role_for,can_access_project,managed_project_ids,project_role_guard,accessible_projects,user_project_ids,users_for_project,company_id_for
from .models import Profile,Project,Checklist,WorkAssignment,ProjectInvitation,GovernanceAudit,GovernanceState,Company,ProjectMembership,IndustryCatalog,ClientOrganization
from .governance_forms import ProjectForm,InvitationForm,InvitationAcceptForm,AssignmentForm,ClientApprovalForm,MaintenanceResetForm,ProjectAdministratorForm,CompanyForm,ProjectCompanyForm,MembershipForm,IndustryForm,AdminIndustryForm,ClientOrganizationForm,ProjectClientForm
from .privileged_audit import snapshot_user,snapshot_project,snapshot_membership,snapshot_invitation,snapshot_maintenance,snapshot_client_organization,change_details


def guarded_write(view):
    @wraps(view)
    def wrapped(*args,**kwargs):
        try:
            return view(*args,**kwargs)
        except OperationalError:
            response=HttpResponse('The local database is busy. Retry this action.',status=503)
            response['Retry-After']='1'
            return response
        except IntegrityError:
            return HttpResponse('This action conflicts with a record created in another request. Reload and retry.',status=409)
    return wrapped


def audit(actor,action,project=None,**details):
    return GovernanceAudit.objects.create(actor=actor,actor_name=getattr(actor,'username',''),action=action,project=project,details=details)


def lock_governance(actor=None):
    # Shared DB row serializes membership changes and invite consumption on SQLite
    # and databases with row locks. Caller must hold transaction.atomic().
    GovernanceState.objects.get_or_create(key='membership')
    GovernanceState.objects.filter(key='membership').update(revision=F('revision')+1)
    if actor is not None:
        actor.refresh_from_db()
        if not actor.is_active:
            raise PermissionDenied('This account is inactive.')


def manager_guard(actor):
    if not is_super_admin(actor) and role_for(actor)!=Profile.Roles.ADMIN:
        raise PermissionDenied('Project administration access is required.')


_ACCOUNT_AUTHORITY_FIELDS={'is_superuser','is_staff','groups','user_permissions'}


def reject_authority_fields(request,extra=()):
    """Account authority is supplied by an authorised route, never mass assigned.

    Reject attempted overrides explicitly instead of reporting an unrelated valid
    account change as successful. Ordinary form validation remains unchanged.
    """
    authority=set(extra)|{key+'_id' for key in extra}
    if (_ACCOUNT_AUTHORITY_FIELDS|authority).intersection(request.POST):
        return HttpResponse('Account authority cannot be changed through this action.',status=400)
    return None


def project_creation_guard(actor):
    if is_super_admin(actor) or role_for(actor)!=Profile.Roles.ADMIN:
        raise PermissionDenied('Only a Project Admin can create company projects.')
    profile=actor.profile
    if (profile.admin_industry_pending or not profile.admin_industry_id or
        not profile.admin_industry.is_active or not company_id_for(actor)):
        raise PermissionDenied('An active company and industry binding are required before creating a project.')


def issue_guard(actor,project,role,company=None,industry=None):
    manager_guard(actor)
    if is_super_admin(actor) and role==Profile.Roles.CLIENT:
        raise PermissionDenied('Only Project Admin may invite Clients.')
    if project is None:
        if not is_super_admin(actor) or role!=Profile.Roles.ADMIN or not company or not industry or not industry.is_active:
            raise PermissionDenied('A project-free invitation requires Super Admin, an Admin role, a company and an active industry.')
        return
    project_role_guard(actor,project,{Profile.Roles.ADMIN})
    allowed={Profile.Roles.ADMIN,Profile.Roles.ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.CLIENT,Profile.Roles.QUALITY_ENGINEER} if is_super_admin(actor) else {Profile.Roles.ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.CLIENT,Profile.Roles.QUALITY_ENGINEER}
    if role not in allowed:
        raise PermissionDenied('This invitation role is outside your authority.')


def scoped_projects(actor):
    return accessible_projects(actor)


def workspace_context(request,**extra):
    actor=request.user
    role=role_for(actor)
    scope_projects=accessible_projects(actor).select_related('company','administrator','checklist_template').order_by('company__name','name')
    super_admin=is_super_admin(actor)
    if role==Profile.Roles.ADMIN:
        for project in scope_projects:
            project.client_candidates=ClientOrganization.objects.filter(company_id=company_id_for(actor),industry__code=project.industry)
    active_view=request.GET.get('view','dashboard' if super_admin else 'my_work')
    if super_admin and active_view in {'my_work','administration','reviews','reports'}:active_view='dashboard'
    allowed_views={'dashboard','industries','clients','projects','sites'} if super_admin else {'my_work','projects','reviews','reports','administration'}
    if active_view not in allowed_views:raise Http404()
    selected_industry=request.GET.get('industry','')
    if selected_industry and not IndustryCatalog.objects.filter(code=selected_industry).exists():raise Http404()
    if selected_industry:scope_projects=scope_projects.filter(industry=selected_industry)
    selected=request.GET.get('project','')
    if not selected and role in {Profile.Roles.ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.CLIENT,Profile.Roles.QUALITY_ENGINEER}:
        primary=scope_projects.filter(pk=getattr(actor.profile,'project_id',None)).first() or scope_projects.first()
        selected=str(primary.pk) if primary else ''
    if selected and selected!='all':
        if not selected.isascii() or not selected.isdigit():
            raise Http404()
        chosen=get_object_or_404(scope_projects,pk=int(selected))
        projects=scope_projects.filter(pk=chosen.pk)
    else:
        chosen=None
        projects=scope_projects
    if is_super_admin(actor):
        projects=list(projects)
        for project in projects:
            project.admin_candidates=ProjectAdministratorForm(project=project).fields['administrator'].queryset
    surveys=Checklist.objects.filter(project__in=projects).select_related('project','user').order_by('project__name','site_id','pk')
    assignments=WorkAssignment.objects.filter(project__in=projects).select_related('project','assigned_to','checklist')
    if role==Profile.Roles.ENGINEER:
        surveys=surveys.filter(user=actor)
        assignments=assignments.filter(assigned_to=actor)
    if role==Profile.Roles.CLIENT:
        from .access import client_checklist_visibility
        surveys=surveys.filter(client_checklist_visibility(actor)).distinct()
        assignments=assignments.none()
        surveys=surveys.filter(Q(governance_mode=Checklist.GovernanceMode.LEGACY)|Q(review_policy__customer_reviewer=actor))
    if role==Profile.Roles.PROJECT_MANAGER:
        surveys=surveys.filter(governance_mode=Checklist.GovernanceMode.INDEPENDENT,review_policy__workflow_version=1,review_policy__l3_approver=actor)
        assignments=assignments.none()
    if role==Profile.Roles.TEAM_LEAD:
        surveys=surveys.filter(Q(governance_mode=Checklist.GovernanceMode.LEGACY)|Q(review_policy__workflow_version=1,review_policy__l2_reviewer=actor)|Q(review_policy__workflow_version=2,review_policy__l3_approver=actor))
    if role==Profile.Roles.QUALITY_ENGINEER:
        surveys=surveys.filter(Q(governance_mode=Checklist.GovernanceMode.LEGACY,quality_reviewer=actor)|Q(governance_mode=Checklist.GovernanceMode.INDEPENDENT,review_policy__workflow_version=2,review_policy__l2_reviewer=actor))
        assignments=assignments.filter(checklist__in=surveys)
    admin=is_super_admin(actor) or role==Profile.Roles.ADMIN
    if active_view=='administration' and not admin:raise PermissionDenied('Administration requires a scoped administrative role.')
    if role==Profile.Roles.CLIENT:
        review_queue=[survey for survey in surveys if survey.can_client_decide]
    elif role==Profile.Roles.ADMIN:
        # Only the named frozen v1 approver may finish an outstanding legacy
        # signature. Admin does not become a stage in the current v2 route.
        review_queue=[survey for survey in surveys.filter(
            review_policy__workflow_version=1,review_policy__l3_approver=actor,
            status__in=[Checklist.Status.SUBMITTED,Checklist.Status.REVIEW,Checklist.Status.PARTIAL])
            if survey.workflow_stage=='project_manager']
    elif role in {Profile.Roles.TEAM_LEAD,Profile.Roles.PROJECT_MANAGER,Profile.Roles.QUALITY_ENGINEER}:
        expected_stage={Profile.Roles.QUALITY_ENGINEER:'quality_engineer',Profile.Roles.TEAM_LEAD:'team_lead',Profile.Roles.PROJECT_MANAGER:'project_manager'}[role]
        review_queue=[survey for survey in surveys.filter(status__in=[Checklist.Status.SUBMITTED,Checklist.Status.REVIEW,Checklist.Status.PARTIAL]) if survey.workflow_stage==expected_stage]
    else:review_queue=Checklist.objects.none()
    invites=(ProjectInvitation.objects.all() if super_admin else ProjectInvitation.objects.filter(
        Q(company_id=company_id_for(actor))|Q(company__isnull=True),project__in=projects
    )).select_related('project','company','created_by') if admin else ProjectInvitation.objects.none()
    member_ids={user.pk for project in projects for user in users_for_project(project,include_inactive=True)} if admin else set()
    members=User.objects.filter(pk__in=member_ids).select_related('profile','profile__project','profile__company').order_by('username')
    if is_super_admin(actor):
        members=User.objects.filter(is_superuser=False).select_related('profile','profile__project','profile__company').order_by('username')
    members=list(members)
    actor_ids=set(scope_projects.values_list('pk',flat=True))
    for member in members:
        member.scope_memberships=list(member.project_memberships.filter(project_id__in=actor_ids).select_related('project','project__company'))
        company=company_id_for(member)
        member.grant_projects=scope_projects.filter(company_id=company) if company is not None else scope_projects
        active_ids=set(member.project_memberships.filter(is_active=True).values_list('project_id',flat=True))
        if member.profile.project_id and not member.project_memberships.filter(project_id=member.profile.project_id).exists():
            active_ids.add(member.profile.project_id)
        member.can_manage_account=is_super_admin(actor) or active_ids.issubset(actor_ids)
    context={'active_view':active_view,'selected_industry':selected_industry,'industry_choices':list(IndustryCatalog.objects.filter(code__in=accessible_projects(actor).values_list('industry',flat=True)).values_list('code','name')) if not super_admin else list(IndustryCatalog.objects.values_list('code','name')),'can_administer':admin,'review_queue':review_queue,'reports':surveys.filter(status=Checklist.Status.FINAL),'can_qualify':role==Profile.Roles.TEAM_LEAD,'role':role,'role_label':dict(Profile.Roles.choices).get(role,'Unassigned'),
        'is_super_admin':is_super_admin(actor),'is_project_admin':role==Profile.Roles.ADMIN,
        'can_create_project':bool(role==Profile.Roles.ADMIN and not super_admin and not actor.profile.admin_industry_pending and actor.profile.admin_industry_id and actor.profile.admin_industry.is_active and company_id_for(actor)),
        'is_client':role==Profile.Roles.CLIENT,'can_client_approve':not super_admin and role in {Profile.Roles.ADMIN,Profile.Roles.CLIENT},
        'can_invite':admin,'can_assign':not super_admin and role in {Profile.Roles.ADMIN,Profile.Roles.TEAM_LEAD},
        'projects':projects,'scope_projects':scope_projects,'project_filter':scope_projects,'selected_project_id':str(chosen.pk) if chosen else '',
        'scope_label':chosen.name if chosen else 'All assigned projects','companies':Company.objects.all() if is_super_admin(actor) else Company.objects.filter(pk=company_id_for(actor)),
        'clientorg_form':ClientOrganizationForm(),'client_organization_form':ClientOrganizationForm(),'client_organizations':ClientOrganization.objects.all() if super_admin else ClientOrganization.objects.filter(company_id=company_id_for(actor),industry_id=getattr(actor.profile,'admin_industry_id',None)),'company_form':CompanyForm(),'surveys':surveys,'assignments':assignments,'invitations':invites,'members':members,
        'admin_industry_form':AdminIndustryForm(),'project_form':ProjectForm(actor=actor),'invite_form':InvitationForm(actor=actor),'assignment_form':AssignmentForm(actor=actor)}
    engineer_home=role==Profile.Roles.ENGINEER and active_view=='my_work'
    if engineer_home:
        unlinked_assignments=assignments.filter(checklist__isnull=True)
        pending_assignments=unlinked_assignments.filter(status__in=[WorkAssignment.Status.PENDING,WorkAssignment.Status.IN_PROGRESS])
        project_query={'project':str(chosen.pk) if chosen else 'all'}
        if selected_industry:project_query['industry']=selected_industry
        def task_url(work=None):
            query=dict(project_query)
            if work:query['work']=work
            return reverse('task_explorer')+'?'+urlencode(query)
        context.update({
            'engineer_home':True,
            'engineer_home_metrics':[
                {'key':'assigned','label':'Total assigned scope','count':surveys.count()+unlinked_assignments.count(),'url':task_url()},
                {'key':'pending','label':'Pending for submission','count':surveys.filter(status=Checklist.Status.DRAFT).count()+pending_assignments.count(),'url':task_url('pending')},
                {'key':'returned','label':'Rejected pending for response','count':surveys.filter(status=Checklist.Status.REJECTED).count(),'url':task_url('returned')},
            ],
        })
    if super_admin:
        context['recent_audit']=GovernanceAudit.objects.select_related('actor','project').order_by('-created_at','-pk')[:12]
        context.update({'industries':IndustryCatalog.objects.all(),'industry_form':IndustryForm(),'sites':assignments,'counts':{'clients':ClientOrganization.objects.count(),'projects':Project.objects.count(),'sites':WorkAssignment.objects.count(),'users':User.objects.count(),'industries':IndustryCatalog.objects.count()}})
        context['surveys']=Checklist.objects.none()
        context['assignments']=WorkAssignment.objects.none()
        context['review_queue']=Checklist.objects.none()
        context['reports']=Checklist.objects.none()
    if super_admin:
        imported_ids=ClientOrganization.objects.exclude(legacy_company_id=None).values_list('legacy_company_id',flat=True)
        legacy_ids=[event.details.get('company_id') for event in GovernanceAudit.objects.filter(action='company_created') if isinstance(event.details,dict) and str(event.details.get('company_id','')).isdigit()]
        context['legacy_client_records']=Company.objects.filter(pk__in=legacy_ids,projects__isnull=True,profiles__isnull=True).exclude(pk__in=imported_ids).distinct()
    context.update(extra)
    return context


def workspace_response(request,status=200,**context):
    if is_super_admin(request.user) and status>=400 and 'active_view' not in context:
        for key,view in [('industry_form','industries'),('project_form','projects'),('invite_form','dashboard')]:
            if key in context:
                context['active_view']=view
                break
    response=render(request,'dashboards/super_admin_workspace.html' if is_super_admin(request.user) else 'dashboards/governance_workspace.html',workspace_context(request,**context),status=status)
    response['Cache-Control']='private, no-store'
    return response


@login_required(login_url='/login/')
@require_GET
@never_cache
def home(request):
    if role_for(request.user) is None:
        raise PermissionDenied('This account does not have active workspace access.')
    if role_for(request.user)==Profile.Roles.QUALITY_ENGINEER and not request.GET:
        return redirect('task_explorer')
    return workspace_response(request)


@login_required(login_url='/login/')
@require_POST
@guarded_write
def industry(request):
    if not is_super_admin(request.user):raise PermissionDenied('Only Super Admin maintains the industry catalog.')
    with transaction.atomic():
        lock_governance(request.user)
        if not is_super_admin(request.user):raise PermissionDenied()
        if request.POST.get('action')=='delete':return HttpResponse('Deactivate an industry to preserve history.',status=409)
        identifier=request.POST.get('industry_id','')
        if identifier:
            if len(identifier)>19 or not identifier.isascii() or not identifier.isdigit():raise Http404()
            record=get_object_or_404(IndustryCatalog.objects.select_for_update(),pk=int(identifier))
        else:
            record=None
        form=IndustryForm(request.POST,instance=record)
        if not form.is_valid():return workspace_response(request,status=400,industry_form=form,error='Check the industry code, name and description.')
        data=form.cleaned_data
        from .industry_service import update_industry
        try:
            update_industry(request.user,record,data['code'],data['name'],data.get('description',''),data['is_active'],
                expected_token=request.POST.get('expected_token'),
                workflow_family=data.get('workflow_family') if not record or 'workflow_family' in request.POST else None)
        except ValidationError as error:
            return workspace_response(request,status=409 if record else 400,industry_form=form,error='; '.join(error.messages))
    return redirect(reverse('governance_home')+'?view=industries')


@login_required(login_url='/login/')
@require_POST
@guarded_write
def projects(request):
    project_creation_guard(request.user)
    with transaction.atomic():
        lock_governance(request.user)
        project_creation_guard(request.user)
        form=ProjectForm(request.POST,actor=request.user)
        if not form.is_valid():
            return workspace_response(request,status=400,project_form=form)
        project=form.save(commit=False)
        project.company_id=company_id_for(request.user)
        project.industry=request.user.profile.admin_industry.code
        project.administrator=request.user
        project.save()
        primary=not ProjectMembership.objects.filter(user=request.user,is_primary=True,is_active=True).exists()
        ProjectMembership.objects.create(user=request.user,project=project,is_active=True,is_primary=primary,granted_by=request.user)
        if not request.user.profile.project_id:
            request.user.profile.project=project
            request.user.profile.save(update_fields=['project'])
        audit(request.user,'project_created',project,name=project.name,template_id=project.checklist_template_id,
              company_id=project.company_id,industry=project.industry,review_layers=project.review_layers,
              **change_details(request.user,'project',project.pk,None,snapshot_project(project),project=project))
    messages.success(request,'Project created.')
    return redirect(reverse('governance_home')+'?view=projects&project='+str(project.pk))


@login_required(login_url='/login/')
@require_POST
@guarded_write
@never_cache
def invite(request):
    manager_guard(request.user)
    with transaction.atomic():
        lock_governance(request.user)
        manager_guard(request.user)
        rejected=reject_authority_fields(request)
        if rejected is not None:return rejected
        if not is_super_admin(request.user):
            for key,expected in [('company',company_id_for(request.user))]:
                if key in request.POST and request.POST[key] not in {'',str(expected)}:
                    return HttpResponse('Invitation authority must remain within your company and industry.',status=400)
        form=InvitationForm(request.POST,actor=request.user)
        if not form.is_valid():
            return workspace_response(request,status=400,invite_form=form)
        data=form.cleaned_data
        issue_guard(request.user,data['project'],data['role'],data.get('company'),data.get('admin_industry'))
        token=secrets.token_urlsafe(32)
        now=timezone.now()
        pending=ProjectInvitation.objects.filter(email__iexact=data['email'],project=data['project'],accepted_at__isnull=True,revoked_at__isnull=True)
        if not data['project']:pending=pending.filter(company=data.get('company'))
        pending.update(revoked_at=now)
        invitation=ProjectInvitation.objects.create(token_hash=hashlib.sha256(token.encode()).hexdigest(),email=data['email'],role=data['role'],admin_industry=data.get('admin_industry') if data['role']==Profile.Roles.ADMIN else None,company=data.get('company'),project=data['project'],created_by=request.user,expires_at=now+timedelta(hours=72))
        audit(request.user,'invitation_created',data['project'],invitation_id=invitation.pk,email=data['email'],role=data['role'],
              **change_details(request.user,'invitation',invitation.pk,None,snapshot_invitation(invitation),project=data['project'],company_id=invitation.company_id))
    # Raw bearer token is shown once, never persisted in session, messages or audit.
    return workspace_response(request,invite_url=request.build_absolute_uri(reverse('governance_accept_invite',args=[token])))


def invitation_for(token):
    if not isinstance(token,str) or not 16<=len(token)<=100:
        raise Http404('Invitation unavailable.')
    invitation=get_object_or_404(ProjectInvitation.objects.select_related('project','created_by'),token_hash=hashlib.sha256(token.encode()).hexdigest(),accepted_at__isnull=True,revoked_at__isnull=True,expires_at__gt=timezone.now())
    if invitation.role==Profile.Roles.ADMIN and invitation.admin_industry_id and invitation.project_id and invitation.admin_industry.code!=invitation.project.industry:
        raise Http404('Invitation industry changed.')
    if invitation.company_id and invitation.project_id and invitation.company_id!=invitation.project.company_id:
        raise Http404('Invitation company changed.')
    if invitation.role==Profile.Roles.ADMIN and invitation.project_id and invitation.project.administrator_id:
        raise Http404('This project now has an owning Admin. Request a company-level Admin invitation instead.')
    issuer=invitation.created_by
    if not issuer or getattr(getattr(issuer,'profile',None),'is_locked',True):
        raise Http404('Invitation unavailable.')
    try:
        issue_guard(issuer,invitation.project,invitation.role,invitation.company,invitation.admin_industry)
    except PermissionDenied:
        raise Http404('Invitation unavailable.')
    return invitation


@require_http_methods(['GET','POST'])
@guarded_write
@sensitive_post_parameters('password1','password2')
@never_cache
def accept_invite(request,token):
    invitation=invitation_for(token)
    form=InvitationAcceptForm(request.POST or None,invitation=invitation)
    if request.method=='POST':
        rejected=reject_authority_fields(request,{'role','project','company','admin_industry'})
        if rejected is not None:return rejected
        with transaction.atomic():
            lock_governance()
            invitation=invitation_for(token)
            form=InvitationAcceptForm(request.POST,invitation=invitation)
            if form.is_valid():
                project_before=snapshot_project(invitation.project) if invitation.project_id else None
                now=timezone.now()
                consumed=ProjectInvitation.objects.filter(pk=invitation.pk,accepted_at__isnull=True,revoked_at__isnull=True,expires_at__gt=now).update(accepted_at=now)
                if not consumed:
                    raise Http404('Invitation unavailable.')
                user=form.save(commit=False)
                user.email=invitation.email
                user.is_superuser=False
                user.is_staff=False
                user.save()
                profile=user.profile
                profile.role=invitation.role
                profile.project=invitation.project
                profile.company=invitation.project.company if invitation.project_id else invitation.company
                profile.admin_industry=invitation.admin_industry
                profile.save(update_fields=['role','project','company','admin_industry'])
                from .company_service import grant_membership
                if invitation.project_id:grant_membership(invitation.created_by,user,invitation.project,make_primary=True)
                if invitation.role==Profile.Roles.ADMIN and invitation.project_id and project_before['administrator_id'] is None:
                    invitation.project.administrator=user
                    invitation.project.save(update_fields=['administrator'])
                    audit(invitation.created_by,'project_administrator_assigned',invitation.project,administrator_id=user.pk,via_invitation_id=invitation.pk,
                          **change_details(invitation.created_by,'project',invitation.project_id,project_before,snapshot_project(invitation.project),project=invitation.project))
                invitation.accepted_by=user
                invitation.accepted_at=now
                invitation.save(update_fields=['accepted_by','accepted_at'])
                audit(user,'invitation_accepted',invitation.project,invitation_id=invitation.pk,role=invitation.role,email=invitation.email,
                      **change_details(user,'user',user.pk,None,snapshot_user(user),project=invitation.project,company_id=invitation.company_id))
                login(request,user,backend='django.contrib.auth.backends.ModelBackend')
                return redirect('governance_home')
    response=render(request,'dashboards/governance_accept_invite.html',{'invitation':invitation,'form':form},status=400 if request.method=='POST' else 200)
    response['Referrer-Policy']='no-referrer'
    return response


@login_required(login_url='/login/')
@require_POST
@guarded_write
def assign(request):
    if is_super_admin(request.user) or role_for(request.user) not in {Profile.Roles.ADMIN,Profile.Roles.TEAM_LEAD}:
        raise PermissionDenied('Task assignment requires Team Lead or project administration.')
    with transaction.atomic():
        lock_governance(request.user)
        form=AssignmentForm(request.POST,actor=request.user)
        if not form.is_valid():
            return workspace_response(request,status=400,assignment_form=form)
        data=form.cleaned_data
        project_role_guard(request.user,data['project'],{Profile.Roles.ADMIN,Profile.Roles.TEAM_LEAD})
        engineer=data['engineer']
        engineer.refresh_from_db()
        if not engineer.is_active or engineer.profile.role!=Profile.Roles.ENGINEER or not can_access_project(engineer,data['project']):
            raise PermissionDenied('Engineer membership changed.')
        from .field_intake_service import create_assignment
        create_assignment(request.user,data,{'kind':'single_assignment'})
    messages.success(request,'Task assigned with its checklist.')
    return redirect('governance_home')


@login_required(login_url='/login/')
@require_POST
@guarded_write
def client_approval(request,checklist_id):
    if is_super_admin(request.user):raise PermissionDenied('Super Admin manages the platform; project roles record Client correspondence and decisions.')
    c=get_object_or_404(Checklist,pk=checklist_id)
    project_role_guard(request.user,c.project_id,{Profile.Roles.ADMIN,Profile.Roles.CLIENT})
    from .review_route_service import route_for,act_on_route
    if route_for(c):
        if role_for(request.user)!=Profile.Roles.CLIENT:
            raise PermissionDenied('Only the assigned Client may sign this project approval stage.')
        action={'approved':'approve','rejected':'reject'}.get(request.POST.get('decision'))
        try:
            act_on_route(request.user,c,action,request.POST.get('reference',''),request.POST.get('expected_route_token',''))
        except ValidationError as error:
            return HttpResponse('; '.join(error.messages),status=409,content_type='text/plain')
        return redirect('roadmap_activity',checklist_id=c.pk)
    with transaction.atomic():
        lock_governance(request.user)
        c=Checklist.objects.select_for_update().get(pk=checklist_id)
        project_role_guard(request.user,c.project_id,{Profile.Roles.ADMIN,Profile.Roles.CLIENT})
        posted=request.POST.copy()
        authenticated_client=role_for(request.user)==Profile.Roles.CLIENT
        if authenticated_client and c.governance_mode==Checklist.GovernanceMode.INDEPENDENT:
            policy=getattr(c,'review_policy',None)
            if not policy or policy.customer_reviewer_id!=request.user.pk:raise PermissionDenied('This Client is not assigned to this activity release.')
        if authenticated_client:
            posted['approver_name']=request.user.get_full_name().strip() or request.user.username
            posted['approver_email']=request.user.email
        form=ClientApprovalForm(posted)
        if not form.is_valid():
            return workspace_response(request,status=400,error='Provide the external approver identity and current checklist version.',client_approval_form=form)
        data=form.cleaned_data
        if c.status!=Checklist.Status.FINAL:
            return workspace_response(request,status=409,error='Complete internal engineering approval before recording the client decision.')
        if data['expected_updated_at']!=c.updated_at.isoformat() or not hmac.compare_digest(data['expected_review_token'],c.client_review_token):
            return workspace_response(request,status=409,error='This checklist changed. Reload before recording client approval.')
        from .workflow_service import can_client_decide,apply_client_decision,sync_assignment
        if not can_client_decide(c):
            return workspace_response(request,status=409,error='This activity is closed; its recorded decisions are preserved.')
        decision={'decision':data['decision'],'approver_name':data['approver_name'],'approver_email':data['approver_email'],'reference':data['reference'],'recorded_by':request.user.pk,'recorded_by_name':request.user.username,'recorded_at':timezone.now().isoformat(),'reviewed_updated_at':data['expected_updated_at'],'authenticated_client':authenticated_client}
        previous=c.client_approval
        c.client_approval=decision
        c.review_history=[*(c.review_history or []),{'action':'client_decision','previous':previous,**decision}]
        apply_client_decision(c,request.user,authenticated_client)
        if authenticated_client and c.governance_mode==Checklist.GovernanceMode.INDEPENDENT:
            from .independent_workflow import record_customer_decision
            try:
                record_customer_decision(request.user,c,data['decision'],data['reference'])
            except ValidationError as exc:
                transaction.set_rollback(True)
                return HttpResponse('; '.join(exc.messages),status=409,content_type='text/plain')
        c.save(update_fields=['client_approval','review_history','client_review_completed_at','status','section_approvals','updated_at'])
        sync_assignment(c)
        audit(request.user,'client_decision_recorded',c.project,checklist_id=c.pk,previous=previous,decision=decision)
    messages.success(request,'Client decision recorded separately from engineering approval.')
    return redirect('governance_home')


@login_required(login_url='/login/')
@require_POST
@guarded_write
def revoke_invite(request,invitation_id):
    manager_guard(request.user)
    with transaction.atomic():
        lock_governance(request.user)
        invitation=get_object_or_404(ProjectInvitation,pk=invitation_id)
        if is_super_admin(request.user):
            pass
        else:
            if invitation.company_id is not None and invitation.company_id!=company_id_for(request.user):
                raise Http404()
            issue_guard(request.user,invitation.project,invitation.role)
        if invitation.accepted_at:
            return HttpResponse('An accepted invitation cannot be revoked; manage the member instead.',status=409)
        before=snapshot_invitation(invitation)
        invitation.revoked_at=timezone.now()
        invitation.save(update_fields=['revoked_at'])
        audit(request.user,'invitation_revoked',invitation.project,invitation_id=invitation.pk,
              **change_details(request.user,'invitation',invitation.pk,before,snapshot_invitation(invitation),project=invitation.project,company_id=invitation.company_id))
    return redirect('governance_home')


@login_required(login_url='/login/')
@require_POST
@guarded_write
def member(request,user_id):
    manager_guard(request.user)
    rejected=reject_authority_fields(request,{'company','admin_industry','project'})
    if rejected is not None:return rejected
    with transaction.atomic():
        lock_governance(request.user)
        target=get_object_or_404(User,pk=user_id)
        profile=target.profile
        if target.pk==request.user.pk or target.is_superuser or profile.role==Profile.Roles.SUPER_ADMIN:
            raise PermissionDenied('This account cannot be changed through project membership controls.')
        target_ids=set(user_project_ids(target))
        # Inactive accounts still have affiliations; use stored grants for global controls.
        target_ids.update(target.project_memberships.filter(is_active=True).values_list('project_id',flat=True))
        if profile.project_id and not target.project_memberships.filter(project_id=profile.project_id).exists():
            target_ids.add(profile.project_id)
        actor_ids=set(managed_project_ids(request.user))
        if not is_super_admin(request.user) and (not target_ids or not target_ids.issubset(actor_ids) or company_id_for(target)!=company_id_for(request.user)):
            raise PermissionDenied('Use scoped project revocation; this account also belongs to a project outside your management scope.')
        if not is_super_admin(request.user) and profile.role not in {Profile.Roles.ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.CLIENT,Profile.Roles.PROJECT_MANAGER,Profile.Roles.QUALITY_ENGINEER}:
            raise PermissionDenied('Project Admin can manage non-administrative project memberships only.')
        action=request.POST.get('action')
        if action not in {'activate','deactivate','role','unlock'}:
            return HttpResponse('Choose a membership action.',status=400)
        before=snapshot_user(target)
        if action=='unlock':
            profile.is_locked=False
            profile.failed_attempts=0
            profile.login_locked_until=None
            profile.save(update_fields=['is_locked','failed_attempts','login_locked_until'])
        elif action=='role':
            if profile.role==Profile.Roles.CLIENT:
                raise PermissionDenied('Client roles cannot be converted through membership controls.')
            role=request.POST.get('role')
            if role not in {Profile.Roles.ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.QUALITY_ENGINEER}:
                raise PermissionDenied('Choose Engineer, Team Lead or Quality Engineer; administrator access requires an invitation.')
            profile.role=role
            profile.save(update_fields=['role'])
        else:
            target.is_active=action=='activate'
            target.save(update_fields=['is_active'])
        audit(request.user,'member_'+action,profile.project,user_id=target.pk,role=profile.role,active=target.is_active,
              **change_details(request.user,'user',target.pk,before,snapshot_user(target),project=profile.project))
    return redirect('governance_home')


@login_required(login_url='/login/')
@require_GET
@never_cache
def audit_log(request):
    manager_guard(request.user)
    entries=GovernanceAudit.objects.select_related('actor','project')
    if not is_super_admin(request.user):
        entries=entries.filter(project_id__in=managed_project_ids(request.user))
    return render(request,'dashboards/governance_audit.html',{'audit_entries':entries[:500],'events':entries[:500],'is_super_admin':is_super_admin(request.user)})


@login_required(login_url='/login/')
@require_http_methods(['GET','POST'])
@guarded_write
@sensitive_post_parameters('password')
@never_cache
def reset(request):
    if not is_super_admin(request.user):
        raise PermissionDenied('Only Super Admin can run access maintenance.')
    form=MaintenanceResetForm(request.POST or None,actor=request.user)
    counts={'sessions':Session.objects.count(),'locked_profiles':Profile.objects.filter(is_locked=True).count(),'open_invitations':ProjectInvitation.objects.filter(accepted_at__isnull=True,revoked_at__isnull=True).count()}
    if request.method=='POST':
        with transaction.atomic():
            lock_governance(request.user)
            if not is_super_admin(request.user):
                raise PermissionDenied()
            form=MaintenanceResetForm(request.POST,actor=request.user)
            if form.is_valid():
                before=snapshot_maintenance()
                sessions=Session.objects.count()
                invitations=ProjectInvitation.objects.filter(accepted_at__isnull=True,revoked_at__isnull=True).update(revoked_at=timezone.now())
                profiles=Profile.objects.filter(is_locked=True).update(is_locked=False,failed_attempts=0,login_locked_until=None)
                Profile.objects.exclude(failed_attempts=0).update(failed_attempts=0,login_locked_until=None)
                Profile.objects.filter(login_locked_until__isnull=False).update(login_locked_until=None)
                Session.objects.all().delete()
                audit(request.user,'access_maintenance_reset',sessions=sessions,invitations=invitations,unlocked_profiles=profiles,
                      **change_details(request.user,'maintenance',None,before,snapshot_maintenance()))
                logout(request)
                return redirect('/login/')
    return render(request,'dashboards/governance_reset.html',{'form':form,'counts':counts},status=400 if request.method=='POST' else 200)


@login_required(login_url='/login/')
@require_POST
@guarded_write
def project_admin(request,project_id):
    if not is_super_admin(request.user):
        raise PermissionDenied('Only Super Admin can assign the primary project administrator.')
    with transaction.atomic():
        lock_governance(request.user)
        if not is_super_admin(request.user):
            raise PermissionDenied()
        project=get_object_or_404(Project.objects.select_for_update(),pk=project_id)
        form=ProjectAdministratorForm(request.POST,project=project)
        if not form.is_valid():
            return workspace_response(request,status=400,error='Choose an active Project Admin assigned to this project or not yet assigned to any project.',project_admin_form=form)
        administrator=form.cleaned_data['administrator']
        administrator.refresh_from_db()
        profile=administrator.profile
        if profile.role!=Profile.Roles.ADMIN:
            raise PermissionDenied('Choose a Project Admin account.')
        previous=project.administrator_id
        before=snapshot_project(project)
        from .company_service import grant_membership
        try:
            grant_membership(request.user,administrator,project,transfer_owner=True)
        except ValidationError as exc:
            return workspace_response(request,status=400,error='; '.join(exc.messages))
        project.administrator=administrator
        project.save(update_fields=['administrator'])
        audit(request.user,'project_administrator_assigned',project,administrator_id=administrator.pk,previous_administrator_id=previous,
              **change_details(request.user,'project',project.pk,before,snapshot_project(project),project=project))
    messages.success(request,'Project ownership assigned. Only this Admin can administer or view the project; evidence and history are preserved.')
    return redirect('governance_home')


@login_required(login_url='/login/')
@require_POST
@guarded_write
def company(request):
    if is_super_admin(request.user) or role_for(request.user)!=Profile.Roles.ADMIN:raise PermissionDenied('Only a bound Project Admin may add Client organizations.')
    with transaction.atomic():
        lock_governance(request.user)
        request.user=User.objects.select_related('profile').get(pk=request.user.pk)
        if is_super_admin(request.user) or role_for(request.user)!=Profile.Roles.ADMIN:raise PermissionDenied()
        profile=Profile.objects.select_for_update().select_related('admin_industry').get(user=request.user)
        if profile.role!=Profile.Roles.ADMIN or not profile.admin_industry_id or profile.admin_industry_pending or not company_id_for(request.user):raise PermissionDenied('A company and industry binding are required.')
        form=ClientOrganizationForm(request.POST)
        if not form.is_valid():return workspace_response(request,status=400,clientorg_form=form)
        organization=form.save(commit=False)
        organization.company_id=company_id_for(request.user)
        organization.industry=profile.admin_industry
        organization.created_by=request.user
        if ClientOrganization.objects.filter(company_id=organization.company_id,industry=organization.industry,name__iexact=organization.name).exists():return workspace_response(request,status=400,clientorg_form=form,error='This Client organization already exists in your industry.')
        organization.save()
        audit(request.user,'client_organization_created',client_organization_id=organization.pk,company_id=organization.company_id,industry_id=organization.industry_id,name=organization.name,
              **change_details(request.user,'client_organization',organization.pk,None,snapshot_client_organization(organization),company_id=organization.company_id))
    return redirect('governance_home')


@login_required(login_url='/login/')
@require_POST
@guarded_write
def project_company(request,project_id):
    if not is_super_admin(request.user):
        raise PermissionDenied()
    with transaction.atomic():
        lock_governance(request.user)
        if not is_super_admin(request.user):
            raise PermissionDenied()
        project=get_object_or_404(Project.objects.select_for_update(),pk=project_id)
        form=ProjectCompanyForm(request.POST)
        if not form.is_valid():
            return workspace_response(request,status=400,error='Choose a company.')
        organization=form.cleaned_data['company']
        if project.company_id!=organization.pk:
            if project.client_organization_id:
                return workspace_response(request,status=409,error='This project has a Client organization. Preserve its tenant association.')
            # Reclassification must never silently transfer active user affiliations.
            if project.memberships.filter(is_active=True).exists() or Profile.objects.filter(project=project).exists() or project.administrator_id:
                return workspace_response(request,status=409,error='Revoke or explicitly reassign existing project memberships before changing its company. Survey history remains preserved.')
            if project.company_id is not None and (
                Checklist.objects.filter(project=project).exists() or
                WorkAssignment.objects.filter(project=project).exists() or
                ProjectInvitation.objects.filter(project=project).exists() or
                ProjectMembership.objects.filter(project=project).exists() or
                GovernanceAudit.objects.filter(project=project).exists() or
                project.locations.exists() or
                project.template_qualifications.exists() or
                project.evidence_rule_releases.exists() or
                bool(project.checklist_template_id) or
                bool(project.template_file)
            ):
                return workspace_response(request,status=409,error='This project has retained company records or evidence. Its company cannot be changed through classification; preserve the original tenant and review any migration separately.')
            previous=project.company_id
            before=snapshot_project(project)
            project.company=organization
            project.save(update_fields=['company'])
            audit(request.user,'project_company_assigned',project,company_id=organization.pk,previous_company_id=previous,
                  **change_details(request.user,'project',project.pk,before,snapshot_project(project),project=project))
    return redirect('governance_home')


@login_required(login_url='/login/')
@require_POST
@guarded_write
def membership(request,user_id):
    manager_guard(request.user)
    rejected=reject_authority_fields(request,{'role','company','admin_industry'})
    if rejected is not None:return rejected
    with transaction.atomic():
        lock_governance(request.user)
        manager_guard(request.user)
        target=get_object_or_404(User.objects.select_related('profile','profile__project','profile__company'),pk=user_id)
        form=MembershipForm(request.POST,actor=request.user)
        if not form.is_valid():
            return workspace_response(request,status=400,error='Choose an accessible project and a grant or revoke action.')
        data=form.cleaned_data
        from .company_service import grant_membership,revoke_membership
        before=snapshot_membership(target,data['project'])
        try:
            if data['action']=='grant':
                grant_membership(request.user,target,data['project'],data['make_primary'],expires_at=data.get('expires_at'))
            else:
                revoke_membership(request.user,target,data['project'])
        except ValidationError as exc:
            return workspace_response(request,status=400,error='; '.join(exc.messages))
        after=snapshot_membership(target,data['project'])
        audit(request.user,'project_membership_'+data['action'],data['project'],user_id=target.pk,primary_project_id=target.profile.project_id,expires_at=data['expires_at'].isoformat() if data.get('expires_at') else None,
              **change_details(request.user,'membership',after['id'],before,after,project=data['project']))
    return redirect('governance_home')


@login_required(login_url='/login/')
@require_POST
@guarded_write
def admin_industry(request,user_id):
    if not is_super_admin(request.user):raise PermissionDenied('Only Super Admin may bind an Admin industry.')
    with transaction.atomic():
        lock_governance(request.user)
        if not is_super_admin(request.user):raise PermissionDenied()
        target=get_object_or_404(User.objects.select_for_update(),pk=user_id,is_superuser=False,profile__role=Profile.Roles.ADMIN)
        form=AdminIndustryForm(request.POST)
        if not form.is_valid():return workspace_response(request,status=400,admin_industry_form=form,error='Choose an active industry.')
        profile=Profile.objects.select_for_update().get(user=target)
        previous=profile.admin_industry_id
        before=snapshot_user(target)
        profile.admin_industry=form.cleaned_data['admin_industry']
        profile.admin_industry_pending=False
        profile.save(update_fields=['admin_industry','admin_industry_pending'])
        audit(request.user,'admin_industry_bound',administrator_id=target.pk,industry_id=profile.admin_industry_id,previous_industry_id=previous,
              **change_details(request.user,'user',target.pk,before,snapshot_user(target)))
    return redirect('governance_home')


@login_required(login_url='/login/')
@require_POST
@guarded_write
def project_client(request,project_id):
    if is_super_admin(request.user) or role_for(request.user)!=Profile.Roles.ADMIN:raise PermissionDenied('Only scoped Project Admin may assign a Client organization.')
    with transaction.atomic():
        lock_governance(request.user)
        request.user=User.objects.select_related('profile').get(pk=request.user.pk)
        if is_super_admin(request.user) or role_for(request.user)!=Profile.Roles.ADMIN:raise PermissionDenied()
        project=get_object_or_404(Project.objects.select_for_update(),pk=project_id)
        project_role_guard(request.user,project,{Profile.Roles.ADMIN})
        profile=Profile.objects.get(user=request.user)
        if profile.role!=Profile.Roles.ADMIN or not profile.admin_industry_id or profile.admin_industry_pending or profile.admin_industry.code!=project.industry:raise PermissionDenied('A matching Admin industry binding is required.')
        form=ProjectClientForm(request.POST,actor=request.user,project=project)
        if not form.is_valid():return workspace_response(request,status=400,error='Choose a Client organization from your company and industry.')
        previous=project.client_organization_id
        before=snapshot_project(project)
        project.client_organization=form.cleaned_data['client_organization']
        project.save(update_fields=['client_organization'])
        audit(request.user,'project_client_assigned',project,client_organization_id=project.client_organization_id,previous_client_organization_id=previous,
              **change_details(request.user,'project',project.pk,before,snapshot_project(project),project=project))
    return redirect('governance_home')
