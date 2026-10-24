from django.urls import path
from . import photo_views as v
from . import category_intake_views as capture
urlpatterns=[
 path('<int:checklist_id>/capture/',capture.state,name='photo_capture_state'),
 path('<int:checklist_id>/capture/general-information/',capture.general_information,name='photo_capture_general_information'),
 path('<int:checklist_id>/capture/submit/',capture.submit,name='photo_capture_submit'),
 path('<int:checklist_id>/capture/category/',capture.category,name='photo_capture_category'),
 path('<int:checklist_id>/capture/remove/',capture.remove,name='photo_capture_remove'),
 path('<int:checklist_id>/capture/documents/upload/',capture.document_upload,name='photo_capture_document_upload'),
 path('<int:checklist_id>/capture/documents/remove/',capture.document_remove,name='photo_capture_document_remove'),
 path('<int:checklist_id>/capture/documents/<int:document_id>/',capture.document,name='photo_capture_document'),
 path('<int:checklist_id>/capture/review/',capture.review_state,name='photo_capture_review_state'),
 path('<int:checklist_id>/capture/review/progress/',capture.review_progress,name='photo_capture_review_progress'),
 path('<int:checklist_id>/capture/review/action/',capture.review_action,name='photo_capture_review_action'),
 path('<int:checklist_id>/upload-session/',v.processing_upload_session,name='photo_processing_upload_session'),
 path('<int:checklist_id>/fast-state/',v.fast_state,name='photo_fast_state'),
 path('<int:checklist_id>/mapping/',v.mapping,name='photo_mapping'),
 path('<int:checklist_id>/',v.workspace,name='photo_workspace'),
 path('<int:checklist_id>/state/',v.state,name='photo_state'),
 path('<int:checklist_id>/upload/',v.upload,name='photo_upload'),
 path('<int:checklist_id>/enqueue/',v.enqueue,name='photo_enqueue'),
 path('<int:checklist_id>/jobs/<int:job_id>/retry/',v.retry,name='photo_retry'),
 path('<int:checklist_id>/drafts/<int:draft_id>/accept/',v.accept,name='photo_accept'),
 path('<int:checklist_id>/evidence/<int:photo_id>/<str:variant>/',v.evidence,name='photo_evidence'),
 path('<int:checklist_id>/report/',v.report,name='photo_report'),
]
