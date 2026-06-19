"""URL configuration for the Creator AI Assistant backend."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("assistant.urls")),
]

# In local/dev, Django serves generated audio from MEDIA_ROOT.
# In production this is handled by nginx (see DEPLOY.md).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
