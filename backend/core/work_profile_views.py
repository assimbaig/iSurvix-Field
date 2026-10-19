"""Every published-profile read rechecks both parties' effective project grants."""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404,render,redirect
from django.views.decorators.http import require_http_methods,require_GET,require_POST
from .models import Profile
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
    candidates=WorkProfile.objects.filter(published=True,user__is_active=True,user__is_superuser=False,user__profile__is_locked=False).filter(Q(user__project_memberships__project__in=projects)|Q(user__profile__project__in=projects)).select_related('user','user__profile','user__profile__company','user__profile__project').distinct()
    if role_for(actor)==Profile.Roles.CLIENT:candidates=candidates.filter(user__profile__role__in=CLIENT_STAFF)
    rows=[]
    for record in candidates:
        shared=shared_projects(actor,record.user)
        if shared:rows.append({'profile':record,'shared_projects':shared,'role':record.user.profile.get_role_display()})
    page=Paginator(rows,24).get_page(request.GET.get('page'))
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
