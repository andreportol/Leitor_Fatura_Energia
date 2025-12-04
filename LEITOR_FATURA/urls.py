from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import include, path
from django.views.generic import RedirectView

try:
    FAVICON_URL = staticfiles_storage.url('img/logomarca.png')
except Exception:
    FAVICON_URL = f"{getattr(settings, 'STATIC_URL', '/static/')}img/logomarca.png"


urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'favicon.ico',
        RedirectView.as_view(
            url=FAVICON_URL,
            permanent=False,
        ),
    ),
    path('', include('app.core.urls', namespace='core')),
]
