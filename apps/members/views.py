"""Member API.

Enforces docs/permissions.md §5.2:

  - list/retrieve directory (minimal fields)  : any authenticated user
  - full record                               : officers / leadership
  - create / edit admin fields / deactivate   : leadership
  - edit own safe fields                       : the member themselves
  - bulk export                               : leadership

The viewset selects serializer and permission set per-action rather than
having one fixed pair, because the matrix grants different things to
different callers on the same resource.
"""

from __future__ import annotations

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import decorators, filters, permissions, response, viewsets

from apps.core.constants import LEADERSHIP_ROLES, OFFICER_ROLES
from apps.core.permissions import HasAnyRole
from apps.members.models import Member
from apps.members.serializers import (
    MemberSelfSerializer,
    MemberSerializer,
    PublicMemberSerializer,
)


class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all().select_related("user")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_active", "sub_county", "school"]
    search_fields = ["first_name", "last_name", "membership_id", "tsc_number", "school"]
    ordering_fields = ["last_name", "joined_on", "created_at"]

    # Per-action permission map. Default (unlisted actions) = leadership only.
    _LEADERSHIP_ACTIONS = {"create", "update", "partial_update", "destroy", "export"}

    def get_permissions(self):
        if self.action in ("list", "retrieve", "me"):
            return [permissions.IsAuthenticated()]
        if self.action in self._LEADERSHIP_ACTIONS:
            return [permissions.IsAuthenticated(), HasAnyRole(LEADERSHIP_ROLES)()]
        return [permissions.IsAuthenticated(), HasAnyRole(LEADERSHIP_ROLES)()]

    def get_serializer_class(self):
        user = self.request.user
        if self.action in ("list", "retrieve"):
            # Officers see the full record; everyone else sees the directory.
            if user.is_authenticated and user.role in OFFICER_ROLES:
                return MemberSerializer
            return PublicMemberSerializer
        if self.action == "me":
            return MemberSelfSerializer
        return MemberSerializer

    # --- self-service: a member editing their own profile ----------------

    @decorators.action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        """GET/PATCH the caller's own member profile (safe fields only)."""
        member = Member.objects.filter(user=request.user).first()
        if member is None:
            return response.Response(
                {"detail": "No member profile is linked to this account."},
                status=404,
            )
        if request.method == "GET":
            return response.Response(MemberSelfSerializer(member).data)

        serializer = MemberSelfSerializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response(serializer.data)

    # --- bulk export -----------------------------------------------------

    @decorators.action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """CSV-style JSON dump for leadership. (CSV file response in phase 9.)"""
        data = MemberSerializer(self.get_queryset(), many=True).data
        return response.Response({"count": len(data), "results": data})
