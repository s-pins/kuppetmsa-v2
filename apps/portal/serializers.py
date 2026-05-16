"""Portal serializers.

Deliberately compact, read-only projections — the portal shows a member
*their own* summary, not the full officer-facing records. Reusing the
underlying models, not duplicating them.
"""

from rest_framework import serializers

from apps.events.models import EventAttendance
from apps.finances.models import FinancialContribution


class MyContributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialContribution
        fields = [
            "id",
            "amount_kes",
            "source",
            "mpesa_ref",
            "paid_at",
            "reconciled",
        ]
        read_only_fields = fields


class MyEventSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)
    event_slug = serializers.CharField(source="event.slug", read_only=True)
    starts_at = serializers.DateTimeField(source="event.starts_at", read_only=True)

    class Meta:
        model = EventAttendance
        fields = [
            "id",
            "event_title",
            "event_slug",
            "starts_at",
            "rsvp",
            "attended",
            "rsvp_at",
        ]
        read_only_fields = fields


class DashboardSerializer(serializers.Serializer):
    """At-a-glance composite. Pure read projection, no model."""

    member_name = serializers.CharField()
    membership_id = serializers.CharField()
    is_active = serializers.BooleanField()
    total_contributed_kes = serializers.DecimalField(max_digits=14, decimal_places=2)
    contribution_count = serializers.IntegerField()
    upcoming_rsvp_count = serializers.IntegerField()
    last_contribution_at = serializers.DateTimeField(allow_null=True)
