from django.urls import path
from .industry_views import industry_description
urlpatterns=[path('description/',industry_description,name='industry_description')]
