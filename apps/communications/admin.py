"""Admin for communications.

Read-mostly. Sending an announcement must go through the API where the
idempotent fan-out and audit middleware apply, not be triggered by a
hand-edit here.
"""

from django.contrib import admin

from apps.communications.models import Announcement, Notification


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "audience_scope",
        "status",
        "recipient_count",
        "sent_at",
    )
    list_filter = ("status", "audience_scope")
    search_fields = ("title", "body")
    readonly_fields = (
        "status",
        "created_by",
        "sent_at",
        "recipient_count",
        "created_at",
        "updated_at",
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("announcement", "member", "is_read", "read_at")
    list_filter = ("is_read",)
    search_fields = (
        "member__first_name",
        "member__last_name",
        "announcement__title",
    )
    readonly_fields = [f.name for f in Notification._meta.fields]

    def has_add_permission(self, request):
        return False
