from django.contrib import admin
from django.urls import include, path
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from core import local_ai

urlpatterns = [
    path('local/', local_ai.home, name='local_home'),
    path('local-ai/status/', local_ai.status, name='local_ai_status'),
    path('local-ai/chat/', local_ai.chat, name='local_ai_chat'),
    path('app/', local_ai.preview, name='local_preview'),
    path('app/<path:asset>', local_ai.preview, name='local_preview_asset'),
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]
# Do not expose the media directory through an unrestricted development alias.
# Custom survey evidence continues through authenticated views.
urlpatterns += staticfiles_urlpatterns()
