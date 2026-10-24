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
@require_POST
@api_errors
def document_upload(request,checklist_id):
    from .engineer_documents import upload
    try:
        response=JsonResponse(upload(request,checklist_id),status=201)
    except DatabaseError:
        response=JsonResponse({'error':'Supporting documents could not be saved. Saved originals are preserved; refresh and retry.'},status=503)
    response['Cache-Control']='private, no-store'
    return response


@login_required
@require_POST
@api_errors
def document_remove(request,checklist_id):
    from .engineer_documents import remove
    try:
        response=JsonResponse(remove(request,checklist_id,body(request)))
    except DatabaseError:
        response=JsonResponse({'error':'The document removal could not be saved. Refresh and retry.'},status=503)
    response['Cache-Control']='private, no-store'
    return response


@login_required
@require_GET
@api_errors
def document(request,checklist_id,document_id):
    from .engineer_documents import delivery
    return delivery(request,checklist_id,document_id)


@login_required
@require_GET
@api_errors
def review_state(request,checklist_id):
    return JsonResponse(intake.review_state(request,checklist_id))


@login_required
@require_GET
@api_errors
def review_progress(request,checklist_id):
    from .qa_review_progress import progress
    response=JsonResponse(progress(request,checklist_id))
    response['Cache-Control']='private, no-store'
    return response


@login_required
@require_POST
@api_errors
def review_action(request,checklist_id):
    data=body(request)
    verified=None
    if data.get('action')=='retry_current_model':
        from .survey_model_identity import prepare_recovery
        verified=prepare_recovery(request,checklist_id,data)
    return JsonResponse(intake.review_action(request,checklist_id,data,verified_model_identity=verified))
