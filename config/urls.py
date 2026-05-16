"""Root URL config."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("config.api_urls", namespace="api_v1")),
    # Our own namespaced account route (reauth).
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    # allauth — must stay un-namespaced for its internal reverse() calls.
    path("accounts/", include("allauth.urls")),
    # Officer console (server-rendered).
    path("members/", include("apps.members.urls", namespace="members")),
    # Phase 2+ will add: path('', include('apps.public_site.urls')),
]
