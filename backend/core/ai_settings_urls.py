from django.urls import path
from . import ai_settings_views

urlpatterns = [
    path('', ai_settings_views.index, name='ai_settings_index'),
    path('<int:company_id>/', ai_settings_views.company_settings, name='ai_settings_company'),
]
