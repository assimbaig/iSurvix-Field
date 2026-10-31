"""Public minimal probes and current platform-owner-only aggregate diagnostics."""
import re
import uuid
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .access import is_super_admin
from .operations_service import readiness,release_id,summary


def _request_id(request):
    supplied=request.headers.get('X-Request-ID','')
    return supplied if re.fullmatch('[a-f0-9]{32}',supplied) else uuid.uuid4().hex


def _response(data,request_id,status=200):
    response=JsonResponse(data,status=status)
    response['X-Request-ID']=request_id
    return response


@require_GET
@never_cache
def live(request):
    return _response({'status':'ok','release':release_id()},_request_id(request))


@require_GET
@never_cache
def ready(request):
    request_id=_request_id(request);available=readiness(request_id)
    return _response({'status':'ready' if available else 'unavailable','release':release_id()},request_id,status=200 if available else 503)


@login_required(login_url='/login/')
@require_GET
@never_cache
def status(request):
    if not is_super_admin(request.user):raise PermissionDenied('Platform administration access is required.')
    request_id=_request_id(request)
    return _response(summary(request_id),request_id)
