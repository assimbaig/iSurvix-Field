from django.urls import path
from . import export_views as views
urlpatterns=[path('',views.index,name='data_exports'),path('status/',views.progress,name='data_export_status'),path('columns/<slug:section>/',views.template,name='data_export_template'),path('<uuid:job_id>/download/',views.download,name='data_export_download'),path('<uuid:job_id>/retry/',views.retry,name='data_export_retry')]
