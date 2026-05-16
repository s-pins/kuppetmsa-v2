"""Admin for events."""

from django.contrib import admin

from apps.events.models import Event, EventAttendance


class EventAttendanceInline(admin.TabularInline):
    model = EventAttendance
    extra = 0
    autocomplete_fields = ("member",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "event_type", "starts_at", "is_public")
    list_filter = ("event_type", "is_public")
    search_fields = ("title", "description", "location")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [EventAttendanceInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(EventAttendance)
class EventAttendanceAdmin(admin.ModelAdmin):
    list_display = ("event", "member", "rsvp", "attended", "rsvp_at")
    list_filter = ("rsvp", "attended")
    search_fields = ("event__title", "member__first_name", "member__last_name")
    autocomplete_fields = ("event", "member")
