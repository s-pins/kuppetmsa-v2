"""Admin registration for the members app."""

from django.contrib import admin

from apps.members.models import Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        "membership_id",
        "full_name",
        "tsc_number",
        "school",
        "sub_county",
        "is_active",
    )
    list_filter = ("is_active", "sub_county")
    search_fields = (
        "membership_id",
        "first_name",
        "last_name",
        "tsc_number",
        "school",
    )
    readonly_fields = ("membership_id", "created_at", "updated_at")
    autocomplete_fields = ()

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "membership_id",
                    "tsc_number",
                    "first_name",
                    "last_name",
                    "user",
                )
            },
        ),
        ("Contact", {"fields": ("phone", "email")}),
        ("Posting", {"fields": ("school", "sub_county", "ward")}),
        ("Profile", {"fields": ("bio", "photo")}),
        ("Status", {"fields": ("is_active", "joined_on")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
