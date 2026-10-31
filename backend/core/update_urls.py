from django.urls import path
from . import update_views as views

urlpatterns=[
    path('',views.index,name='update_center'),
    path('request/',views.create,name='update_request'),
    path('<uuid:request_id>/reconcile/',views.reconcile,name='update_reconcile'),
    path('<uuid:request_id>/withdraw/',views.withdraw,name='update_withdraw'),
]
