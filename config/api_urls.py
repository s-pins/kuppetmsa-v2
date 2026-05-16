"""API v1 URL configuration.

Auth endpoints are public (you can't get a token without them). Schema
and Swagger are gated to officers via the views wrapped in apps.accounts.views.
"""

from django.urls import include, path
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from apps.accounts.views import (
    OfficerGatedRedocView,
    OfficerGatedSchemaView,
    OfficerGatedSwaggerView,
)

app_name = "api_v1"

urlpatterns = [
    # JWT auth
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/blacklist/", TokenBlacklistView.as_view(), name="token_blacklist"),
    # Account self-service
    path("accounts/", include("apps.accounts.api_urls", namespace="accounts")),
    # Members
    path("", include("apps.members.api_urls", namespace="members")),
    path("finances/", include("apps.finances.api_urls", namespace="finances")),
    path("mpesa/", include("apps.mpesa.api_urls", namespace="mpesa")),
    path("", include("apps.projects.api_urls", namespace="projects")),
    path("", include("apps.events.api_urls", namespace="events")),
    path("", include("apps.reports.api_urls", namespace="reports")),
    # OpenAPI schema + UIs — all gated to officers.
    path("schema/", OfficerGatedSchemaView.as_view(), name="schema"),
    path("docs/", OfficerGatedSwaggerView.as_view(url_name="api_v1:schema"), name="swagger"),
    path("redoc/", OfficerGatedRedocView.as_view(url_name="api_v1:schema"), name="redoc"),
]
