"""Single CSRF-protected route action endpoint; all authority stays in service."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import DatabaseError,IntegrityError
from django.http import HttpResponse,JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse
from .governance_views import guarded_write
from .template_views import survey_access
from .review_route_service import act_on_route

@login_required
@require_POST
@guarded_write
def review_route_action(request,checklist_id):
    checklist=survey_access(request,checklist_id)['checklist']
    from .access import role_for
    from .category_intake import enabled,qa_id
    target=reverse('photo_workspace',args=[checklist.pk])+'?qa_step=decision'
    quick_return=role_for(request.user)=='QUALITY_ENGINEER' and enabled(checklist) and qa_id(checklist)==request.user.pk and request.POST.get('return_to')==target
    wants_json=quick_return and any(part.split(';',1)[0].strip()=='application/json'
        for part in request.headers.get('Accept','').split(','))
    def json_result(data,status=200):
        response=JsonResponse(data,status=status)
        response['Cache-Control']='private, no-store'
        return response
    try:
        event=act_on_route(request.user,checklist,request.POST.get('action',''),request.POST.get('reason',''),request.POST.get('expected_token',''))
    except ValidationError as error:
        if wants_json:return json_result({'ok':False,'error':'; '.join(error.messages)},409)
        return HttpResponse('; '.join(error.messages),status=409,content_type='text/plain')
    except PermissionDenied:
        if wants_json:return json_result({'ok':False,'error':'This decision is no longer available at your assigned review stage. Refresh the saved task.'},403)
        raise
    except IntegrityError:
        if wants_json:return json_result({'ok':False,'error':'This decision conflicts with a saved change. Refresh and retry; no decision was recorded.'},409)
        raise
    except DatabaseError:
        if not wants_json:raise
        response=json_result({'ok':False,'error':'The decision could not be saved. Your earlier review is preserved; retry after refreshing the saved task.'},503)
        response['Retry-After']='1'
        return response
    if quick_return:
        next_stage={'engineer':'Engineer for correction','team_lead':'Team Lead','client':'Client','closed':'the closed activity'}.get(event.to_stage,'the next assigned reviewer')
        message='QA decision saved and sent to '+next_stage+'. Original evidence and review history are preserved.'
        messages.success(request,message)
        if wants_json:return json_result({'ok':True,'message':message,'redirect_url':target})
        return redirect(target)
    return redirect('roadmap_activity',checklist_id=checklist.pk)
