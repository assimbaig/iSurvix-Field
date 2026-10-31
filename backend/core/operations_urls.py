from django.urls import path
from . import operations_views as views

urlpatterns=[
    path('health/live/',views.live,name='operations_live'),
    path('health/ready/',views.ready,name='operations_ready'),
    path('status/',views.status,name='operations_status'),
]
