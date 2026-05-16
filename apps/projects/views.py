"""Project API.

docs/permissions.md §5.5:
  - list/retrieve public projects : AllowAny
  - create/update/delete          : leadership

Anonymous and members see only is_public=True projects. Leadership sees
all (including internal/draft projects).
"""

from __future__ import annotations

from rest_framework import permissions, viewsets

from apps.core.constants import LEADERSHIP_ROLES, OFFICER_ROLES
from apps.core.permissions import HasAnyRole
from apps.projects.models import Project
from apps.projects.serializers import ProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    filterset_fields = ["status", "is_public"]
    search_fields = ["name", "description", "beneficiaries"]
    lookup_field = "slug"

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [
            permissions.IsAuthenticated(),
            HasAnyRole(LEADERSHIP_ROLES)(),
        ]

    def get_queryset(self):
        qs = Project.objects.all()
        user = self.request.user
        # Officers see everything; the public sees only public projects.
        if user.is_authenticated and user.role in OFFICER_ROLES:
            return qs
        return qs.filter(is_public=True)
