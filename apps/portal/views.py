"""Member portal API.

Three surfaces, all strictly scoped to the caller's own member:

  GET /api/v1/portal/dashboard/        — at-a-glance composite
  GET /api/v1/portal/my-contributions/ — own contribution history
  GET /api/v1/portal/my-events/        — own RSVPs / attendance

Every queryset is filtered by self.member. There is no path parameter
that could address another member's data — the only identity the portal
recognises is the authenticated caller's.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from rest_framework import generics, response, views

from apps.events.models import EventAttendance
from apps.finances.models import FinancialContribution
from apps.portal.permissions import PortalScopedMixin
from apps.portal.serializers import (
    DashboardSerializer,
    MyContributionSerializer,
    MyEventSerializer,
)


class DashboardView(PortalScopedMixin, views.APIView):
    def get(self, request):
        member = self.member

        contrib_qs = FinancialContribution.objects.filter(member=member)
        agg = contrib_qs.aggregate(total=Sum("amount_kes"))
        total = agg["total"] or Decimal("0.00")
        latest = contrib_qs.order_by("-paid_at").first()

        upcoming_rsvps = EventAttendance.objects.filter(
            member=member,
            rsvp=True,
            event__starts_at__gte=timezone.now(),
        ).count()

        payload = {
            "member_name": member.full_name,
            "membership_id": member.membership_id,
            "is_active": member.is_active,
            "total_contributed_kes": total,
            "contribution_count": contrib_qs.count(),
            "upcoming_rsvp_count": upcoming_rsvps,
            "last_contribution_at": latest.paid_at if latest else None,
        }
        return response.Response(DashboardSerializer(payload).data)


class MyContributionsView(PortalScopedMixin, generics.ListAPIView):
    serializer_class = MyContributionSerializer

    def get_queryset(self):
        return FinancialContribution.objects.filter(member=self.member).order_by("-paid_at")


class MyEventsView(PortalScopedMixin, generics.ListAPIView):
    serializer_class = MyEventSerializer

    def get_queryset(self):
        return (
            EventAttendance.objects.filter(member=self.member)
            .select_related("event")
            .order_by("-rsvp_at")
        )
