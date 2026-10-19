from django.urls import path
from . import evidence_views as views

urlpatterns = [
    path('activities/<int:checklist_id>/evidence-learning/', views.learning, name='evidence_learning'),
    path('activities/<int:checklist_id>/evidence-learning/state/', views.state, name='evidence_learning_state'),
    path('activities/<int:checklist_id>/evidence-learning/cases/<int:case_id>/decide/', views.decide, name='evidence_learning_decide'),
    path('activities/<int:checklist_id>/evidence-learning/publish/', views.publish, name='evidence_learning_publish'),
]
