"""Event serializers."""

from rest_framework import serializers

from apps.events.models import Event, EventAttendance


class EventSerializer(serializers.ModelSerializer):
    rsvp_count = serializers.IntegerField(read_only=True)
    attended_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "slug",
            "event_type",
            "description",
            "location",
            "starts_at",
            "image",
            "is_public",
            "rsvp_count",
            "attended_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class EventAttendanceSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)

    class Meta:
        model = EventAttendance
        fields = [
            "id",
            "event",
            "member",
            "member_name",
            "rsvp",
            "attended",
            "rsvp_at",
            "marked_by",
        ]
        read_only_fields = ["id", "marked_by"]
