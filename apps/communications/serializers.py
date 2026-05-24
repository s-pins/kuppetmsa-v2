"""Communications serializers — docs/permissions.md §5.9."""

from rest_framework import serializers

from apps.communications.models import Announcement, Notification


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "body",
            "image",
            "image_alt",
            "audience_scope",
            "audience_sub_county",
            "is_public",
            "status",
            "created_by",
            "created_by_email",
            "sent_at",
            "recipient_count",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_by",
            "sent_at",
            "recipient_count",
            "created_at",
        ]


class MyNotificationSerializer(serializers.ModelSerializer):
    """A member's own inbox row — the announcement content inlined."""

    title = serializers.CharField(source="announcement.title", read_only=True)
    body = serializers.CharField(source="announcement.body", read_only=True)
    image = serializers.ImageField(source="announcement.image", read_only=True)
    image_alt = serializers.CharField(source="announcement.image_alt", read_only=True)
    sent_at = serializers.DateTimeField(source="announcement.sent_at", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "body",
            "image",
            "image_alt",
            "sent_at",
            "is_read",
            "read_at",
        ]
        read_only_fields = fields
