"""Invitation-based sign-in; roles come from the account, never a login selector."""
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings
from django.db import transaction
from django.db.models import F,Q
from django.db.models.functions import Least
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.views.decorators.debug import sensitive_post_parameters
from .governance_views import guarded_write


def home(request, **kwargs):
    if not request.user.is_authenticated:
        if not get_user_model().objects.filter(is_superuser=True).exists():
            return redirect('/local/setup/')
        return redirect('/login/')
    return redirect('/governance/')


def record_failed_login(username,now=None):
    """Atomic, bounded per-account throttle; failures cannot set manual locks.

    The first UPDATE obtains the write lock before reading/incrementing counters,
    so concurrent failures cannot lose increments or extend an active window.
    Deliberate or historical is_locked values are never automatically cleared.
    """
    from .models import Profile
    now=now or timezone.now()
    limit=max(1,min(1000,int(getattr(settings,'LOGIN_FAILURE_LIMIT',5))))
    seconds=max(1,min(86400,int(getattr(settings,'LOGIN_LOCKOUT_SECONDS',900))))
    available=Profile.objects.filter(user__username=username,user__is_active=True,is_locked=False)
    with transaction.atomic(using=available.db):
        available.filter(login_locked_until__lte=now).update(failed_attempts=0,login_locked_until=None)
        available.filter(login_locked_until__isnull=True).update(failed_attempts=Least(F('failed_attempts')+1,limit))
        # An active deadline is never moved by further unauthenticated requests.
        available.filter(login_locked_until__isnull=True,failed_attempts__gte=limit).update(login_locked_until=now+timedelta(seconds=seconds))


@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters('password')
@guarded_write
def sign_in(request):
    if request.user.is_authenticated:
        return home(request)
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            profile = getattr(user, 'profile', None)
            with transaction.atomic():
                now=timezone.now()
                allowed=not profile or type(profile).objects.filter(pk=profile.pk,is_locked=False,user__is_active=True).filter(
                    Q(login_locked_until__isnull=True)|Q(login_locked_until__lte=now)).update(failed_attempts=0,login_locked_until=None)
                if not allowed:
                    form.add_error(None,form.get_invalid_login_error())
                else:
                    login(request, user)
                    request.session.pop('is_dev_admin', None)
                    from .governance_views import audit
                    audit(user, 'sign_in', getattr(profile, 'project', None))
                    return redirect('/governance/')
        else:
            username=form.cleaned_data.get('username','')
            record_failed_login(username)
    response = render(request, 'login.html', {'form': form})
    response['Cache-Control'] = 'no-store'
    return response


def retired_preview(request, **kwargs):
    return HttpResponse('The sample website has been removed. Open /local/ for your project workspace.', status=410)


def retired_admin(request, **kwargs):
    if request.method == 'GET':
        return home(request)
    return HttpResponse('Use project invitations and the role administration page.', status=410)


def retired_action(request, **kwargs):
    return HttpResponse('Use the assigned task and project workspace for this action.', status=410)


def governed_assignment(request):
    if request.method=='GET':
        return redirect('/governance/?view=projects')
    from .governance_views import assign
    return assign(request)


def legacy_survey_access(request, checklist_id, path=None):
    from .access import is_super_admin,can_access_project
    from .models import Checklist, Profile
    if not request.user.is_authenticated or not request.user.is_active:
        raise Http404()
    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_locked:
        raise Http404()
    checklist = get_object_or_404(Checklist, pk=checklist_id)
    if checklist.schema_snapshot:
        from .template_views import survey_access
        access=survey_access(request,checklist_id)
        if path is not None and profile and profile.role==Profile.Roles.ENGINEER and profile.path!=path:
            raise Http404()
        return {**access,'profile':profile,'back_url':'governance_home','back_name':'governance_home','back_path':None}
    admin = is_super_admin(request.user) or bool(profile and profile.role == Profile.Roles.ADMIN and can_access_project(request.user,checklist.project_id))
    supervisor = bool(profile and profile.role == Profile.Roles.TEAM_LEAD and can_access_project(request.user,checklist.project_id))
    owner = bool(profile and profile.role == Profile.Roles.ENGINEER and can_access_project(request.user,checklist.project_id) and checklist.user_id == request.user.pk)
    if not (admin or supervisor or owner) or owner and path is not None and profile.path != path:
        raise Http404()
    return {'checklist': checklist, 'profile': profile, 'can_edit': checklist.status != Checklist.Status.FINAL,
            'role': 'ADMIN' if admin else profile.role, 'redirect': None,
            'back_url': 'governance_home', 'back_name': 'governance_home', 'back_path': None}
