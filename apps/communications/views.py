"""Communications API — docs/permissions.md §5.9.

  AnnouncementViewSet  — comms officers compose, list, and send.
  MyInboxView / mark-read — a member's own notifications, self-scoped.

Recurring-lesson note (Phases 2/6/7): `send` is a privileged action,
but composing and sending are both equally "comms officer" acts — there
is no broader sub-policy needed, so one get_permissions gate is correct.
This is a conscious decision, documented, not the over-restriction trap.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import (
    decorators,
    generics,
    mixins,
    permissions,
    response,
    status,
    viewsets,
)

from apps.communications.models import Announcement, Notification
from apps.communications.serializers import (
    AnnouncementSerializer,
    MyNotificationSerializer,
)
from apps.core.constants import COMMUNICATIONS_ROLES
from apps.core.permissions import HasAnyRole
from apps.portal.permissions import IsMemberWithProfile


class AnnouncementViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Announcement.objects.select_related("created_by")
    serializer_class = AnnouncementSerializer
    filterset_fields = ["status", "audience_scope"]

    def get_permissions(self):
        # Single comms-role gate for all actions is intentional: compose,
        # list and send are equally comms-officer operations. No broader
        # sub-action exists, so this is not the Phase 2/6 trap.
        return [
            permissions.IsAuthenticated(),
            HasAnyRole(COMMUNICATIONS_ROLES)(),
        ]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @decorators.action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        announcement = self.get_object()
        try:
            count = announcement.send()
        except DjangoValidationError as exc:
            return response.Response(
                {"detail": exc.messages[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response.Response(
            {
                "detail": f"Sent to {count} member(s).",
                "announcement": AnnouncementSerializer(announcement).data,
            }
        )


class MyInboxView(generics.ListAPIView):
    """A member's own notifications. Strictly self-scoped."""

    serializer_class = MyNotificationSerializer
    permission_classes = [IsMemberWithProfile]
    filterset_fields = ["is_read"]

    def get_queryset(self):
        return Notification.objects.filter(member=self.request.user.member_profile).select_related(
            "announcement"
        )


class MarkNotificationReadView(generics.GenericAPIView):
    permission_classes = [IsMemberWithProfile]
    serializer_class = MyNotificationSerializer

    def post(self, request, pk=None):
        notif = Notification.objects.filter(pk=pk, member=request.user.member_profile).first()
        if notif is None:
            # Not theirs (or doesn't exist) — same response either way,
            # don't leak which.
            return response.Response(
                {"detail": "Not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        notif.mark_read()
        return response.Response(MyNotificationSerializer(notif).data)
