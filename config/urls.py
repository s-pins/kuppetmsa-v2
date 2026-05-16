"""Root URL config."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('config.api_urls', namespace='api_v1')),
    # Phase 1+ will add: path('', include('apps.public_site.urls')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
]
