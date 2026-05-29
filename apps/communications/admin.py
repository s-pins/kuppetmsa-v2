"""Admin for communications.

Read-mostly. Sending an announcement must go through the API where the
idempotent fan-out and audit middleware apply, not be triggered by a
hand-edit here.
"""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError

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

    actions = ["send_selected"]

    @admin.action(description="Send selected announcement(s) to members")
    def send_selected(self, request, queryset):
        # Calls the model's send() method, which is @transaction.atomic,
        # idempotent (refuses re-send), creates per-member Notification
        # rows, sets recipient_count, and goes through django-auditlog.
        # This is the proper send path the API uses; we just expose it
        # via the admin so officers don't need a curl-and-JWT setup.
        sent_ok = 0
        already = 0
        errors = []
        for ann in queryset:
            try:
                count = ann.send()
                sent_ok += 1
                self.message_user(
                    request,
                    f"Sent '{ann.title}' to {count} recipient(s).",
                    level=messages.SUCCESS,
                )
            except ValidationError as e:
                # Idempotency guard ('already sent') and audience-config
                # checks come through here.
                if "already been sent" in str(e):
                    already += 1
                    self.message_user(
                        request,
                        f"'{ann.title}' was already sent; skipped.",
                        level=messages.INFO,
                    )
                else:
                    errors.append((ann.title, str(e)))
                    self.message_user(
                        request,
                        f"'{ann.title}': {e}",
                        level=messages.ERROR,
                    )
        if not errors and sent_ok + already > 0:
            self.message_user(
                request,
                f"Done: {sent_ok} sent, {already} already-sent.",
                level=messages.SUCCESS,
            )

    def save_model(self, request, obj, form, change):
        # `created_by` is readonly in the admin form (officers can't
        # forge another user's identity), so it's never POSTed. On
        # first save, populate it from the request user. On subsequent
        # saves, leave it as-is.
        if obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)



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
