"""Invitation-based sign-in; roles come from the account, never a login selector."""
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import F
from django.http import HttpResponse
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.views.decorators.debug import sensitive_post_parameters


def home(request, **kwargs):
    if not request.user.is_authenticated:
        if not get_user_model().objects.filter(is_superuser=True).exists():
            return redirect('/local/setup/')
        return redirect('/login/')
    return redirect('/governance/')


@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters('password')
def sign_in(request):
    if request.user.is_authenticated:
        return home(request)
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            profile = getattr(user, 'profile', None)
            if profile and profile.is_locked:
                form.add_error(None, 'This account is locked. Contact your administrator.')
            else:
                login(request, user)
                request.session.pop('is_dev_admin', None)
                if profile:
                    type(profile).objects.filter(pk=profile.pk).update(failed_attempts=0)
                from .governance_views import audit
                audit(user, 'sign_in', getattr(profile, 'project', None))
                return redirect('/governance/')
        else:
            from .models import Profile
            username = request.POST.get('username', '')
            Profile.objects.filter(user__username=username, user__is_active=True).update(failed_attempts=F('failed_attempts') + 1)
            Profile.objects.filter(user__username=username, failed_attempts__gte=5).update(is_locked=True)
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
