from django.urls import path
from . import remote_worker_views as views

urlpatterns = [
    path('claim/', views.claim, name='remote_worker_claim'),
    path('jobs/<int:job_id>/heartbeat/', views.heartbeat, name='remote_worker_heartbeat'),
    path('jobs/<int:job_id>/next/', views.next_task, name='remote_worker_next'),
    path('jobs/<int:job_id>/tasks/<int:task_id>/image/', views.image, name='remote_worker_image'),
    path('jobs/<int:job_id>/tasks/<int:task_id>/complete/', views.complete, name='remote_worker_complete'),
    path('jobs/<int:job_id>/failure/', views.failure, name='remote_worker_failure'),
]
