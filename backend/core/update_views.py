"""Owner-only saved update requests; privileged work stays on the host."""
import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET,require_POST
from .governance_views import guarded_write
from .operations_service import release_id
from .update_models import ServerUpdateRequest
from . import update_service as service


@login_required
@never_cache
@require_GET
def index(request):
    service.owner(request.user)
    catalog_error=''
    try:choices,_=service.available_releases()
    except ValidationError as error:choices=[];catalog_error=' '.join(error.messages)
    rows=list(ServerUpdateRequest.objects.select_related('requested_by').prefetch_related('events').order_by('-created_at')[:20])
    for row in rows:row.safe_error=service.ERROR_LABELS.get(row.error_code,'')
    return render(request,'core/update_center.html',{'active_view':'updates','is_super_admin':True,
        'current_release':release_id(),'choices':choices,'catalog_error':catalog_error,'updates':rows,
        'has_active':any(row.active for row in rows),'request_key':str(uuid.uuid4())})


@login_required
@never_cache
@require_POST
@guarded_write
def create(request):
    service.owner(request.user)
    if set(request.POST)-{'target_release','expected_current','request_key','maintenance_confirmed','csrfmiddlewaretoken'}:
        return HttpResponse('Only the displayed update request fields are accepted.',status=400)
    try:
        saved=service.request_update(request.user,target_release=request.POST.get('target_release'),
            expected_current=request.POST.get('expected_current'),request_key=request.POST.get('request_key'),
            maintenance_confirmed=request.POST.get('maintenance_confirmed')=='on')
    except ValidationError as error:
        response=HttpResponse(' '.join(error.messages),status=409 if any(getattr(item,'code','')=='conflict' for item in getattr(error,'error_list',[])) else 400)
        return response
    messages.success(request,'Update request saved. It is awaiting the host operator; no installation has started.')
    return redirect('update_center')


@login_required
@never_cache
@require_POST
@guarded_write
def reconcile(request,request_id):
    service.owner(request.user)
    get_object_or_404(ServerUpdateRequest,pk=request_id)
    try:
        saved,count=service.reconcile_receipts(request.user,request_id)
    except ValidationError as error:
        messages.error(request,' '.join(error.messages))
    else:
        messages.success(request,'Verified host receipts reconciled. Current state: '+saved.get_status_display()+'.' if count else 'No host receipts are available. The saved state is unchanged.')
    return redirect('update_center')


@login_required
@never_cache
@require_POST
@guarded_write
def withdraw(request,request_id):
    service.owner(request.user)
    get_object_or_404(ServerUpdateRequest,pk=request_id)
    try:service.withdraw_request(request.user,request_id)
    except ValidationError as error:messages.error(request,' '.join(error.messages))
    else:messages.success(request,'Pending update request withdrawn. No host installation was authorized by this action.')
    return redirect('update_center')
