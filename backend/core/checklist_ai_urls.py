from django.urls import path
from . import checklist_ai_review as v
urlpatterns=[
    path('<int:checklist_id>/',v.workspace,name='checklist_ai_review'),
    path('<int:checklist_id>/state/',v.state,name='checklist_ai_state'),
    path('<int:checklist_id>/request/',v.request_review,name='checklist_ai_request'),
    path('<int:checklist_id>/<int:review_id>/share/',v.share,name='checklist_ai_share'),
]
