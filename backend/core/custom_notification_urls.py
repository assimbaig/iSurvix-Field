from django.urls import path
from . import custom_notification_views as views
urlpatterns=[path('',views.index,name='notification_settings_index'),path('<str:company_id>/',views.company,name='notification_settings_company')]
