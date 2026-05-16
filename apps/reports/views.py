"""Report API.

docs/permissions.md §5.6:
  - view published                 : AllowAny
  - view drafts                    : uploader or leadership
  - upload                         : any officer
  - publish (make public)          : leadership
  - delete                         : leadership
"""

from __future__ import annotations

from rest_framework import (
    decorators,
    permissions,
    response,
    serializers,
    status,
    viewsets,
)

from apps.core.constants import LEADERSHIP_ROLES, OFFICER_ROLES
from apps.core.permissions import HasAnyRole
from apps.reports.models import Report


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            "id",
            "title",
            "category",
            "year",
            "description",
            "file",
            "is_published",
            "uploaded_by",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "is_published",
            "uploaded_by",
            "created_at",
        ]


class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    filterset_fields = ["category", "year", "is_published"]
    search_fields = ["title", "description"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        if self.action in ("publish", "unpublish", "destroy"):
            return [
                permissions.IsAuthenticated(),
                HasAnyRole(LEADERSHIP_ROLES)(),
            ]
        # create / update : any officer
        return [
            permissions.IsAuthenticated(),
            HasAnyRole(OFFICER_ROLES)(),
        ]

    def get_queryset(self):
        qs = Report.objects.select_related("uploaded_by")
        user = self.request.user
        if not user.is_authenticated:
            return qs.filter(is_published=True)
        if user.role in LEADERSHIP_ROLES:
            return qs
        if user.role in OFFICER_ROLES:
            # Officers see published + their own drafts.
            from django.db.models import Q

            return qs.filter(Q(is_published=True) | Q(uploaded_by=user))
        return qs.filter(is_published=True)

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    @decorators.action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        report = self.get_object()
        report.is_published = True
        report.save(update_fields=["is_published", "updated_at"])
        return response.Response(ReportSerializer(report).data)

    @decorators.action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        report = self.get_object()
        report.is_published = False
        report.save(update_fields=["is_published", "updated_at"])
        return response.Response(ReportSerializer(report).data, status=status.HTTP_200_OK)
