from django.urls import path
from .review_route_views import review_route_action
urlpatterns=[path('<int:checklist_id>/action/',review_route_action,name='review_route_action')]
