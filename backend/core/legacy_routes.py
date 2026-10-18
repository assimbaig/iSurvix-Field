"""Fence older routes around the invitation-based, versioned task workflow."""
from functools import wraps

from django.http import Http404, HttpResponse


def protected_legacy(view, route_name):
    @wraps(view)
    def guarded(request, *args, **kwargs):
        from .account_views import legacy_survey_access
        from .models import Checklist, WorkAssignment
        # A cached UI flag must never grant authorization.
        request.session.pop('is_dev_admin', None)
        if not request.user.is_authenticated or not request.user.is_active:
            raise Http404()
        profile = getattr(request.user, 'profile', None)
        if profile and profile.is_locked:
            raise Http404()
        cid = kwargs.get('checklist_id')
        if cid is not None:
            access = legacy_survey_access(request, cid, kwargs.get('path'))
            if request.method != 'GET' and not access['checklist'].schema_snapshot:
                return HttpResponse('This legacy record remains available for viewing/export. Use a published task checklist for changes.', status=410)
        if route_name == 'create_checklist_from_work':
            from .access import user_project_ids
            work = WorkAssignment.objects.filter(pk=kwargs.get('work_id'), assigned_to=request.user,
                                                project_id__in=user_project_ids(request.user)).first()
            if not work:
                raise Http404()
        return view(request, *args, **kwargs)
    return guarded
