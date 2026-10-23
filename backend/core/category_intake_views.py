from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import DatabaseError
from django.views.decorators.http import require_GET, require_POST,require_http_methods
from . import category_intake as intake
from .photo_views import api_errors, body


@login_required
@require_GET
@api_errors
def state(request,checklist_id):
    response=JsonResponse(intake.state(request,checklist_id))
    response['Cache-Control']='private, no-store'
    return response


@login_required
@require_http_methods(['GET','POST'])
@api_errors
def general_information(request,checklist_id):
    from . import engineer_general_info
    try:
        result=intake.state(request,checklist_id) if request.method=='GET' else engineer_general_info.save(request,checklist_id,body(request))
        response=JsonResponse(result)
    except DatabaseError:
        response=JsonResponse({'error':'Site information could not be confirmed. Refresh the saved information and retry.'},status=503)
    response['Cache-Control']='private, no-store'
    return response


@login_required
@require_POST
@api_errors
def submit(request,checklist_id):
    revision,created=intake.submit(request,checklist_id,body(request))
    return JsonResponse({'created':created,'revision_id':revision.pk,'job_id':revision.processing_job.pk,
        'stage':'quality_engineer','message':'Submitted to QA. AI Analysis runs in the background.',
        'state':intake.state(request,checklist_id)},status=201 if created else 200)


@login_required
@require_POST
@api_errors
def category(request,checklist_id):
    return JsonResponse(intake.move_or_remove(request,checklist_id,body(request)))


@login_required
@require_POST
@api_errors
def remove(request,checklist_id):
    return JsonResponse(intake.move_or_remove(request,checklist_id,body(request),remove=True))


@login_required
@require_GET
@api_errors
def review_state(request,checklist_id):
    return JsonResponse(intake.review_state(request,checklist_id))


@login_required
@require_POST
@api_errors
def review_action(request,checklist_id):
    return JsonResponse(intake.review_action(request,checklist_id,body(request)))
