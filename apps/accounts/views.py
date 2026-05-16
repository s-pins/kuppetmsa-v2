"""Account views: gated docs views and the /me self-service endpoint."""

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import generics, permissions

from apps.accounts.serializers import UserSerializer
from apps.core.permissions import IsOfficer


class OfficerGatedSchemaView(SpectacularAPIView):
    """The raw OpenAPI schema. Officers only."""

    permission_classes = [permissions.IsAuthenticated, IsOfficer]


class OfficerGatedSwaggerView(SpectacularSwaggerView):
    """Swagger UI. Officers only."""

    permission_classes = [permissions.IsAuthenticated, IsOfficer]


class OfficerGatedRedocView(SpectacularRedocView):
    """Redoc UI. Officers only."""

    permission_classes = [permissions.IsAuthenticated, IsOfficer]


class MeView(generics.RetrieveUpdateAPIView):
    """`GET /api/v1/accounts/me/` — current user.

    Returns the authenticated user's record. Used by the web/mobile clients
    to hydrate session state.
    """

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
