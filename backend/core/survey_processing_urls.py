from django.urls import path
from . import survey_processing_views as views

urlpatterns = [
    path('<int:checklist_id>/', views.workspace, name='survey_processing_workspace'),
    path('<int:checklist_id>/state/', views.state, name='survey_processing_state'),
    path('<int:checklist_id>/action/', views.action, name='survey_processing_action'),
    path('<int:checklist_id>/documents/<int:document_id>/', views.document, name='survey_processing_document'),
    path('<int:checklist_id>/sources/<int:analysis_id>/', views.source_preview, name='survey_processing_source'),
    path('<int:checklist_id>/outputs/<int:asset_id>/<int:sheet>/<str:kind>/', views.output, name='survey_processing_output'),
]
