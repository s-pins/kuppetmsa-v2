"""Event API.

docs/permissions.md §5.4:
  - list/retrieve            : AllowAny (public events only for anon)
  - create/update/delete     : event-organizer roles
  - rsvp / cancel rsvp       : authenticated member, for themselves
  - mark attendance          : event-organizer roles
  - attendee list            : event-organizer roles
"""

from __future__ import annotations

from django.utils import timezone
from rest_framework import decorators, permissions, response, status, viewsets

from apps.core.constants import EVENT_ORGANIZER_ROLES, OFFICER_ROLES
from apps.core.permissions import HasAnyRole
from apps.events.models import Event, EventAttendance
from apps.events.serializers import (
    EventAttendanceSerializer,
    EventSerializer,
)


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    filterset_fields = ["event_type", "is_public"]
    search_fields = ["title", "description", "location"]
    lookup_field = "slug"

    _ORGANIZER_ACTIONS = {
        "create",
        "update",
        "partial_update",
        "destroy",
        "mark_attendance",
        "attendees",
    }

    def get_permissions(self):
        if self.action in ("list", "retrieve", "rsvp", "cancel_rsvp"):
            if self.action in ("rsvp", "cancel_rsvp"):
                return [permissions.IsAuthenticated()]
            return [permissions.AllowAny()]
        return [
            permissions.IsAuthenticated(),
            HasAnyRole(EVENT_ORGANIZER_ROLES)(),
        ]

    def get_queryset(self):
        qs = Event.objects.all()
        user = self.request.user
        if user.is_authenticated and user.role in OFFICER_ROLES:
            return qs
        return qs.filter(is_public=True)

    # ---- member self-service RSVP --------------------------------------

    def _member_or_400(self, request):
        member = getattr(request.user, "member_profile", None)
        if member is None:
            return None, response.Response(
                {"detail": "No member profile linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return member, None

    @decorators.action(detail=True, methods=["post"])
    def rsvp(self, request, slug=None):
        event = self.get_object()
        member, err = self._member_or_400(request)
        if err:
            return err
        rec, _ = EventAttendance.objects.get_or_create(event=event, member=member)
        rec.rsvp = True
        rec.rsvp_at = timezone.now()
        rec.save(update_fields=["rsvp", "rsvp_at", "updated_at"])
        return response.Response(EventAttendanceSerializer(rec).data)

    @decorators.action(detail=True, methods=["post"], url_path="cancel-rsvp")
    def cancel_rsvp(self, request, slug=None):
        event = self.get_object()
        member, err = self._member_or_400(request)
        if err:
            return err
        rec = EventAttendance.objects.filter(event=event, member=member).first()
        if rec is None or not rec.rsvp:
            return response.Response(
                {"detail": "No active RSVP to cancel."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rec.rsvp = False
        rec.save(update_fields=["rsvp", "updated_at"])
        return response.Response({"detail": "RSVP cancelled."})

    # ---- organizer: attendance + roster --------------------------------

    @decorators.action(detail=True, methods=["get"])
    def attendees(self, request, slug=None):
        event = self.get_object()
        recs = event.attendance_records.select_related("member")
        page = self.paginate_queryset(recs)
        data = EventAttendanceSerializer(page if page is not None else recs, many=True).data
        if page is not None:
            return self.get_paginated_response(data)
        return response.Response(data)

    @decorators.action(detail=True, methods=["post"], url_path="mark-attendance")
    def mark_attendance(self, request, slug=None):
        """Body: {"member": <id>, "attended": true}."""
        event = self.get_object()
        member_id = request.data.get("member")
        attended = bool(request.data.get("attended", True))
        if member_id is None:
            return response.Response(
                {"detail": "member is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rec, _ = EventAttendance.objects.get_or_create(event=event, member_id=member_id)
        rec.attended = attended
        rec.marked_by = request.user
        rec.save(update_fields=["attended", "marked_by", "updated_at"])
        return response.Response(EventAttendanceSerializer(rec).data)
