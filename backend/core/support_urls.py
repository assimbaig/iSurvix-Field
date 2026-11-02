from django.urls import path
from . import support_views as views

urlpatterns = [
    path('', views.index, name='support_index'),
    path('health/', views.health, name='support_health'),
    path('report/', views.create, name='support_case_create'),
    path('<uuid:case_id>/', views.detail, name='support_case_detail'),
    path('<uuid:case_id>/export/', views.export, name='support_case_export'),
    path('<uuid:case_id>/action/', views.action, name='support_case_action'),
    path('<uuid:case_id>/receipt/', views.receipt, name='support_case_receipt'),
]
