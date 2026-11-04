"""Every published-profile read rechecks both parties' effective project grants."""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q,F,Exists,OuterRef
from django.http import Http404
from django.shortcuts import get_object_or_404,render,redirect
from django.views.decorators.http import require_http_methods,require_GET,require_POST
from .models import Profile,ProjectMembership
from django.utils import timezone
from .work_profile_models import WorkProfile,ProfessionalExperience
from .work_profile_forms import WorkProfileForm,ProfessionalExperienceForm
from .access import role_for,is_super_admin,accessible_projects,company_id_for

CLIENT_STAFF={Profile.Roles.ENGINEER,Profile.Roles.QUALITY_ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.ADMIN}

def actor_for(request):
    actor=User.objects.select_related('profile','profile__company','profile__project').get(pk=request.user.pk)
    if not role_for(actor):raise PermissionDenied('An active, unlocked account is required.')
    request.user=actor
    return actor

def shared_projects(actor,target):
    if is_super_admin(actor) or target.is_superuser or not role_for(target) or company_id_for(actor)!=company_id_for(target):return []
    if role_for(actor)==Profile.Roles.CLIENT and role_for(target) not in CLIENT_STAFF:return []
    return list(accessible_projects(actor).filter(pk__in=accessible_projects(target).values('pk')).order_by('name'))


def directory_candidates(actor,projects):
    """Apply the effective-grant rules in SQL before counting/paging profiles.

    This is a request-local read, never a cache of authority. An explicit expired
    or revoked membership suppresses the legacy primary-project fallback.
    """
    roles={Profile.Roles.ADMIN,Profile.Roles.TEAM_LEAD,Profile.Roles.QUALITY_ENGINEER,
           Profile.Roles.ENGINEER,Profile.Roles.CLIENT,Profile.Roles.PROJECT_MANAGER}
    company=company_id_for(actor)
    affiliation=(Q(user__profile__company__isnull=True,user__profile__project__company__isnull=True)
                 if company is None else Q(user__profile__company_id=company)|
                 Q(user__profile__company__isnull=True,user__profile__project__company_id=company))
    grants=ProjectMembership.objects.filter(user_id=OuterRef('user_id'),project__in=projects,
        is_active=True).filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now()))
    # Admin grants additionally require current ownership or the migration-only
    # legacy delegation, and the Admin's fixed industry when one is assigned.
    grants=grants.filter(~Q(user__profile__role=Profile.Roles.ADMIN)|
        Q(project__administrator_id=F('user_id'))|Q(legacy_admin_access=True)).filter(
        ~Q(user__profile__role=Profile.Roles.ADMIN)|Q(user__profile__admin_industry__isnull=True)|
        Q(project__industry=F('user__profile__admin_industry__code')))
    primary_record=ProjectMembership.objects.filter(user_id=OuterRef('user_id'),
        project_id=OuterRef('user__profile__project_id'))
    legacy=Q(user__profile__project__in=projects,_primary_record=False)&(
        ~Q(user__profile__role=Profile.Roles.ADMIN)|(
            Q(user__profile__project__administrator_id=F('user_id'))&(
                Q(user__profile__admin_industry__isnull=True)|
                Q(user__profile__project__industry=F('user__profile__admin_industry__code')))))
    candidates=WorkProfile.objects.filter(published=True,user__is_active=True,
        user__is_superuser=False,user__profile__is_locked=False,user__profile__role__in=roles).filter(
        affiliation).exclude(user__profile__role=Profile.Roles.ADMIN,user__profile__admin_industry_pending=True)
    if role_for(actor)==Profile.Roles.CLIENT:candidates=candidates.filter(user__profile__role__in=CLIENT_STAFF)
    return candidates.alias(_shared_grant=Exists(grants),_primary_record=Exists(primary_record)).filter(
        Q(_shared_grant=True)|legacy).select_related('user','user__profile','user__profile__company',
            'user__profile__project','user__profile__admin_industry').order_by('pk')


def directory_rows(records,projects):
    """Expand shared-project labels only for the displayed page with one grant read."""
    records=list(records)
    project_map={project.pk:project for project in projects.order_by('name','pk')}
    grants={}
    for grant in ProjectMembership.objects.filter(user_id__in=[record.user_id for record in records],
            project_id__in=project_map):
        grants.setdefault(grant.user_id,{})[grant.project_id]=grant
    now=timezone.now()
    rows=[]
    for record in records:
        profile=record.user.profile
        shared=[]
        for project in project_map.values():
            grant=grants.get(record.user_id,{}).get(project.pk)
            permitted=(grant.is_active and (grant.expires_at is None or grant.expires_at>now)) if grant else profile.project_id==project.pk
            if permitted and profile.role==Profile.Roles.ADMIN:
                permitted=(project.administrator_id==record.user_id or bool(grant and grant.legacy_admin_access)) and (
                    not profile.admin_industry_id or project.industry==profile.admin_industry.code)
            if permitted:shared.append(project)
        if shared:rows.append({'profile':record,'shared_projects':shared,'role':profile.get_role_display()})
    return rows

def experience_guard(actor):
    if is_super_admin(actor) or role_for(actor) not in {Profile.Roles.ENGINEER,Profile.Roles.QUALITY_ENGINEER}:raise PermissionDenied('Professional experience editing is available to Engineers and Quality Engineers only.')

def private_response(request,template,context,status=200):
    response=render(request,template,context,status=status)
    response['Cache-Control']='private, no-store'
    response['X-Robots-Tag']='noindex, nofollow'
    return response

@login_required(login_url='/login/')
@require_http_methods(['GET','POST'])
def profile(request):
    actor=actor_for(request)
    record,_=WorkProfile.objects.get_or_create(user=actor)
    form=WorkProfileForm(request.POST or None,instance=record)
    if request.method=='POST':
        from .governance_views import lock_governance,audit
        with transaction.atomic():
            lock_governance(actor)
            actor=actor_for(request)
            record=WorkProfile.objects.select_for_update().get(user=actor)
            form=WorkProfileForm(request.POST,instance=record)
            if form.is_valid():
                record=form.save()
                audit(actor,'professional_profile_saved',published=record.published)
                messages.success(request,'Professional profile saved.')
                return redirect('work_profile')
    return private_response(request,'dashboards/work_profile_edit.html',{'profile_form':form,'professional':record,'experiences':record.experiences.all(),'can_edit_experience':role_for(actor) in {Profile.Roles.ENGINEER,Profile.Roles.QUALITY_ENGINEER},'experience_form':ProfessionalExperienceForm()},400 if request.method=='POST' else 200)

@login_required(login_url='/login/')
@require_GET
def directory(request):
    actor=actor_for(request)
    if is_super_admin(actor):raise PermissionDenied('Super Admin uses administrative account controls, not the shared-project directory.')
    projects=accessible_projects(actor)
    page=Paginator(directory_candidates(actor,projects),24).get_page(request.GET.get('page'))
    page.object_list=directory_rows(page.object_list,projects)
    return private_response(request,'dashboards/work_profile_directory.html',{'page_obj':page})

@login_required(login_url='/login/')
@require_GET
def detail(request,user_id):
    actor=actor_for(request)
    record=get_object_or_404(WorkProfile.objects.select_related('user','user__profile','user__profile__company','user__profile__project'),user_id=user_id)
    own=actor.pk==user_id
    shared=[] if own else shared_projects(actor,record.user)
    if not own and (not record.published or not shared):raise Http404()
    return private_response(request,'dashboards/work_profile_detail.html',{'professional':record,'experiences':record.experiences.all(),'shared_projects':shared,'own_profile':own,'professional_role':record.user.profile.get_role_display()})

@login_required(login_url='/login/')
@require_http_methods(['GET','POST'])
def experience_edit(request,experience_id=None):
    actor=actor_for(request);experience_guard(actor)
    record,_=WorkProfile.objects.get_or_create(user=actor)
    entry=get_object_or_404(ProfessionalExperience,pk=experience_id,work_profile=record) if experience_id else None
    form=ProfessionalExperienceForm(request.POST or None,instance=entry)
    if request.method=='POST':
        from .governance_views import lock_governance,audit
        with transaction.atomic():
            lock_governance(actor)
            actor=actor_for(request);experience_guard(actor)
            record=WorkProfile.objects.select_for_update().get(user=actor)
            entry=get_object_or_404(ProfessionalExperience.objects.select_for_update(),pk=experience_id,work_profile=record) if experience_id else None
            form=ProfessionalExperienceForm(request.POST,instance=entry)
            if form.is_valid():
                entry=form.save(commit=False);entry.work_profile=record;entry.save()
                audit(actor,'professional_experience_saved',experience_id=entry.pk)
                return redirect('work_profile')
    return private_response(request,'dashboards/work_profile_experience.html',{'experience_form':form,'experience':entry},400 if request.method=='POST' else 200)

@login_required(login_url='/login/')
@require_POST
def experience_delete(request,experience_id):
    from .governance_views import lock_governance,audit
    with transaction.atomic():
        actor=actor_for(request);lock_governance(actor)
        actor=actor_for(request);experience_guard(actor)
        entry=get_object_or_404(ProfessionalExperience.objects.select_for_update(),pk=experience_id,work_profile__user=actor)
        pk=entry.pk;entry.delete()
        audit(actor,'professional_experience_deleted',experience_id=pk)
    return redirect('work_profile')
