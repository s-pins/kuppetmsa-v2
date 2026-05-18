"""Root URL config."""

from django.conf import settings
from django.conf.urls.static import static
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
    # Public website (server-rendered) — the branch's outward face.
    # Mounted last at root so it doesn't shadow API/admin/accounts.
    path("", include("apps.public_site.web_urls", namespace="public_site_web")),
]

# Serve user-uploaded media in development ONLY. In production nginx
# serves /media/ directly (see docs/DEPLOYMENT.md §6); this block is a
# no-op when DEBUG is False, so it is safe to leave in.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
