"""Bearer-authenticated machine endpoints, separate from browser session actions."""
import json
from functools import wraps
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from . import remote_worker_service as service
from .remote_worker_models import RemoteSurveyLease, RemoteSurveyTask
from .survey_processing_models import SurveyProcessingJob

MAX_BODY = 256 * 1024


def endpoint(function):
    @csrf_exempt
    @wraps(function)
    def wrapped(request, *args, **kwargs):
        try:
            authorization = request.headers.get('Authorization', '')
            if not authorization.startswith('Bearer ') or len(authorization) > 300:
                raise PermissionDenied('A scoped worker credential is required.')
            credential = service.authenticate(authorization[7:])
            if request.method not in {'POST', 'GET'}:
                return JsonResponse({'error': 'Use the documented worker method.'}, status=405)
            if request.method == 'POST':
                if request.content_type != 'application/json' or int(request.META.get('CONTENT_LENGTH') or 0) > MAX_BODY:
                    raise ValidationError('Use bounded JSON worker messages.')
                if len(request.body) > MAX_BODY:
                    raise ValidationError('The worker message exceeds its safe size.')
                payload = json.loads(request.body)
                if not isinstance(payload, dict):
                    raise ValidationError('Use a JSON object for the worker message.')
            else:
                payload = {}
            response = function(request, credential, payload, *args, **kwargs)
        except PermissionDenied:
            response = JsonResponse({'error': 'Worker credentials or scoped lease are invalid or expired.'}, status=403)
        except (SurveyProcessingJob.DoesNotExist, RemoteSurveyLease.DoesNotExist, RemoteSurveyTask.DoesNotExist):
            response = JsonResponse({'error': 'The scoped worker job or task is unavailable.'}, status=404)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
            if function.__name__ in {'next_task', 'image'}:
                service.preparation_failure(credential, kwargs.get('job_id'), request.headers.get('X-Worker-Lease', ''))
            response = JsonResponse({'error': 'The worker message is invalid.'}, status=400)
        except ValidationError as exc:
            if function.__name__ in {'next_task', 'image'}:
                service.preparation_failure(credential, kwargs.get('job_id'), request.headers.get('X-Worker-Lease', ''))
            response = JsonResponse({'error': '; '.join(exc.messages)}, status=409)
        except OSError:
            if function.__name__ in {'next_task', 'image'}:
                service.preparation_failure(credential, kwargs.get('job_id'), request.headers.get('X-Worker-Lease', ''))
            response = JsonResponse({'error': 'The server evidence store is temporarily unavailable; saved checkpoints are preserved.'}, status=503)
        response['Cache-Control'] = 'no-store, private'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    return wrapped


@endpoint
def claim(request, credential, payload):
    if request.method != 'POST':
        return JsonResponse({'error': 'Use POST.'}, status=405)
    return JsonResponse({'job': service.claim(credential, payload), 'versions': service.versions()})


@endpoint
def heartbeat(request, credential, payload, job_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Use POST.'}, status=405)
    return JsonResponse(service.heartbeat(credential, job_id, request.headers.get('X-Worker-Lease', '')))


@endpoint
def next_task(request, credential, payload, job_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Use POST.'}, status=405)
    return JsonResponse(service.next_task(credential, job_id, request.headers.get('X-Worker-Lease', '')))


@endpoint
def image(request, credential, payload, job_id, task_id):
    if request.method != 'GET':
        return JsonResponse({'error': 'Use GET.'}, status=405)
    task = service.image_input(credential, job_id, request.headers.get('X-Worker-Lease', ''), task_id)
    response = FileResponse(task.image.open('rb'), content_type='image/jpeg', as_attachment=True, filename='worker-input.jpg')
    response['X-Evidence-SHA256'] = task.image_sha256
    return response


@endpoint
def complete(request, credential, payload, job_id, task_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Use POST.'}, status=405)
    return JsonResponse(service.complete_task(credential, job_id, request.headers.get('X-Worker-Lease', ''), task_id, payload))


@endpoint
def failure(request, credential, payload, job_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Use POST.'}, status=405)
    return JsonResponse(service.fail(credential, job_id, request.headers.get('X-Worker-Lease', ''), payload.get('code'), payload.get('retryable', False)))
