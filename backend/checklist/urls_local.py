from django.contrib import admin
from django.urls import include, path
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from core import local_ai
from core import local_setup_views
from core import account_views

urlpatterns = [
    path('local/checklist-review/', include('core.checklist_ai_urls')),
    path('local/setup/', local_setup_views.setup, name='local_setup'),
    path('local/photos/', include('core.photo_urls')),
    path('local/', account_views.home, name='local_home'),
    path('local/assistant/', local_ai.home, name='local_assistant'),
    path('local-ai/status/', local_ai.status, name='local_ai_status'),
    path('local-ai/chat/', local_ai.chat, name='local_ai_chat'),
    path('app/', account_views.retired_preview, name='local_preview'),
    path('app/<path:asset>', account_views.retired_preview, name='local_preview_asset'),
    path('admin/', account_views.retired_admin),
    path('admin/<path:asset>', account_views.retired_admin),
    path('', include('core.urls')),
]
# Do not expose the media directory through an unrestricted development alias.
# Custom survey evidence continues through authenticated views.
urlpatterns += staticfiles_urlpatterns()
