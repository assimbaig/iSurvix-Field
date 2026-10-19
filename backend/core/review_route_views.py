"""Single CSRF-protected route action endpoint; all authority stays in service."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from .governance_views import guarded_write
from .template_views import survey_access
from .review_route_service import act_on_route

@login_required
@require_POST
@guarded_write
def review_route_action(request,checklist_id):
    checklist=survey_access(request,checklist_id)['checklist']
    try:
        act_on_route(request.user,checklist,request.POST.get('action',''),request.POST.get('reason',''),request.POST.get('expected_token',''))
    except ValidationError as error:
        return HttpResponse('; '.join(error.messages),status=409,content_type='text/plain')
    return redirect('roadmap_activity',checklist_id=checklist.pk)
