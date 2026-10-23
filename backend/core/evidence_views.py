"""Scoped internal learning; all decisions remain explicit CSRF-protected posts."""
import json
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET, require_POST
from . import evidence_learning as service


def payload(request):
    if request.content_type == 'application/json':
        try:
            value = json.loads(request.body)
        except (ValueError, UnicodeError):
            raise ValidationError('Invalid JSON request.')
        if not isinstance(value, dict):
            raise ValidationError('The request must be an object.')
        return value
    return request.POST


def mutation_response(request, checklist_id, operation):
    try:
        operation()
    except ValidationError as error:
        return JsonResponse({'error': '; '.join(error.messages)}, status=409)
    except IntegrityError:
        return JsonResponse({'error': 'This decision was already recorded. Refresh the page.'}, status=409)
    except OperationalError:
        response = JsonResponse({'error': 'The local database is busy. Retry shortly.'}, status=503)
        response['Retry-After'] = '1'
        return response
    if request.content_type == 'application/json' or 'application/json' in request.headers.get('Accept', ''):
        return JsonResponse(service.learning_state(request.user, checklist_id))
    return redirect('evidence_learning', checklist_id=checklist_id)


@login_required
@require_GET
def learning(request, checklist_id):
    from .access import role_for
    from .models import Profile
    if role_for(request.user)==Profile.Roles.ENGINEER:
        from .category_intake import access as capture_access
        capture_access(request,checklist_id)
        return redirect('photo_workspace',checklist_id=checklist_id)
    checklist = service.learning_access(request.user, checklist_id)
    return render(request, 'dashboards/evidence_learning.html', {'checklist': checklist, 'state': service.learning_state(request.user, checklist_id)})


@login_required
@require_GET
def state(request, checklist_id):
    return JsonResponse(service.learning_state(request.user, checklist_id))


@login_required
@require_POST
def decide(request, checklist_id, case_id):
    from .category_intake import deny_engineer_ai
    deny_engineer_ai(request,checklist_id)
    def operation():
        data = payload(request)
        service.decide_correction(request.user, checklist_id, case_id, data.get('decision'), data.get('reason', ''))
    return mutation_response(request, checklist_id, operation)


@login_required
@require_POST
def publish(request, checklist_id):
    from .category_intake import deny_engineer_ai
    deny_engineer_ai(request,checklist_id)
    def operation():
        data = payload(request)
        ids = data.getlist('case_ids') if hasattr(data, 'getlist') else data.get('case_ids', [])
        try:
            if not isinstance(ids, list) or any(type(v) not in (int, str) for v in ids):
                raise ValueError()
            ids = [int(value) for value in ids]
        except (ValueError, TypeError):
            raise ValidationError('Select valid correction IDs.')
        service.publish_release(request.user, checklist_id, ids, data.get('reason', ''))
    return mutation_response(request, checklist_id, operation)
