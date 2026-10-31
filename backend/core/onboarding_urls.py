from django.urls import path
from . import onboarding_views as views

urlpatterns = [
    path('', views.index, name='company_onboarding'),
    path('apply/', views.apply, name='company_onboarding_apply'),
    path('<int:application_id>/', views.detail, name='company_onboarding_detail'),
    path('<int:application_id>/action/', views.action, name='company_onboarding_action'),
]
