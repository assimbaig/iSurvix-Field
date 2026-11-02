"""Authenticated support UI; executable repair work never runs in the web process."""
import json
import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .access import accessible_projects
from .governance_views import guarded_write
from .support_models import SupportCase
from . import support_service as service


def _private(response):
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


def _case(request, case_id):
    service.principal(request.user)
    try:
        return service.get_case(request.user, case_id)
    except PermissionDenied:
        raise Http404('Support report unavailable.') from None


def _error_status(error):
    return 409 if any(getattr(item, 'code', '') == 'conflict' for item in getattr(error, 'error_list', [])) else 400


def _index_context(request, **changes):
    _profile, owner = service.principal(request.user)
    try:
        health = service.health(request.user)
        health_error = ''
    except DatabaseError:
        health = None
        health_error = 'Diagnostics are temporarily unavailable. No unknown count is shown as zero.'
    context = {'active_view': 'support', 'health': health, 'health_error': health_error,
               'cases': list(service.visible_cases(request.user)[:30]),
               'projects': accessible_projects(request.user).order_by('name')[:200],
               'category_choices': SupportCase.CATEGORIES, 'request_key': str(uuid.uuid4()),
               'is_support_owner': owner, 'form_error': '', 'submitted': {}}
    context.update(changes)
    return context


def _detail_response(request, case, status=200, **changes):
    _profile, owner = service.principal(request.user)
    context = {'active_view': 'support', 'case': case, 'events': service.history_rows(case),
               'references': service.case_references(case),
               'allowed_actions': service.allowed_actions(request.user, case),
               'is_support_owner': owner, 'request_key': str(uuid.uuid4()),
               'can_import_receipt': owner and case.status in {'repair_requested', 'changes_requested'},
               'form_error': '', 'submitted': {}, 'receipt_value': ''}
    context.update(changes)
    return _private(render(request, 'support/detail.html', context, status=status))


@login_required
@never_cache
@require_GET
def index(request):
    return _private(render(request, 'support/index.html', _index_context(request)))


@login_required
@never_cache
@require_GET
def health(request):
    service.principal(request.user)
    try:
        data = service.health(request.user)
    except DatabaseError:
        return _private(JsonResponse({'available': False, 'error': 'Scoped diagnostics are temporarily unavailable.'}, status=503))
    return _private(JsonResponse(data))


@login_required
@never_cache
@require_POST
@guarded_write
def create(request):
    service.principal(request.user)
    if set(request.POST) - {'category', 'description', 'project_id', 'request_key', 'csrfmiddlewaretoken'}:
        return _private(HttpResponse('Only the displayed support fields are accepted.', status=400))
    try:
        case = service.create_case(request.user, category=request.POST.get('category'),
            description=request.POST.get('description'), project_id=request.POST.get('project_id'),
            request_key=request.POST.get('request_key'))
    except ValidationError as error:
        context = _index_context(request, form_error=' '.join(error.messages), submitted=request.POST.dict(),
                                 request_key=request.POST.get('request_key', str(uuid.uuid4())))
        return _private(render(request, 'support/index.html', context, status=_error_status(error)))
    messages.success(request, 'Support report saved with an immutable scoped diagnostic snapshot.')
    return redirect('support_case_detail', case_id=case.pk)


@login_required
@never_cache
@require_GET
def detail(request, case_id):
    return _detail_response(request, _case(request, case_id))


@login_required
@never_cache
@require_GET
def export(request, case_id):
    case = _case(request, case_id)
    response = HttpResponse(service.export_bundle(request.user, case.pk), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="isurvix-support-' + str(case.pk) + '.zip"'
    return _private(response)


@login_required
@never_cache
@require_POST
@guarded_write
def action(request, case_id):
    service.principal(request.user, owner=True)
    case = _case(request, case_id)
    if set(request.POST) - {'action', 'reason', 'pr_url', 'expected_version', 'request_key', 'csrfmiddlewaretoken'}:
        return _private(HttpResponse('Only the displayed support action fields are accepted.', status=400))
    try:
        service.change_case(request.user, case.pk, action=request.POST.get('action'),
            reason=request.POST.get('reason', ''), pr_url=request.POST.get('pr_url', ''),
            expected_version=request.POST.get('expected_version'), request_key=request.POST.get('request_key'))
    except ValidationError as error:
        return _detail_response(request, service.get_case(request.user, case.pk), status=_error_status(error),
                                form_error=' '.join(error.messages), submitted=request.POST.dict())
    messages.success(request, 'Support action saved in the audit history. No repair, deployment or engineering approval was executed.')
    return redirect('support_case_detail', case_id=case.pk)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate receipt keys.')
        result[key] = value
    return result


@login_required
@never_cache
@require_POST
@guarded_write
def receipt(request, case_id):
    service.principal(request.user, owner=True)
    case = _case(request, case_id)
    if set(request.POST) - {'receipt', 'expected_version', 'request_key', 'csrfmiddlewaretoken'}:
        return _private(HttpResponse('Only the displayed operator receipt fields are accepted.', status=400))
    raw = request.POST.get('receipt', '')
    try:
        if len(raw.encode('utf-8')) > service.MAX_RECEIPT_BYTES:
            raise ValueError()
        data = json.loads(raw, object_pairs_hook=_unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))
        service.import_receipt(request.user, case.pk, receipt=data,
            expected_version=request.POST.get('expected_version'), request_key=request.POST.get('request_key'))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return _detail_response(request, case, status=400, form_error='Use a complete bounded JSON operator receipt.', receipt_value=raw)
    except ValidationError as error:
        return _detail_response(request, service.get_case(request.user, case.pk), status=_error_status(error),
                                form_error=' '.join(error.messages), receipt_value=raw)
    messages.success(request, 'Operator-attested test evidence recorded. The website did not execute or independently verify those tests.')
    return redirect('support_case_detail', case_id=case.pk)
