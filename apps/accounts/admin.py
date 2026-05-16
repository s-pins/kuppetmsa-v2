"""Admin registration for the accounts app."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "role", "is_active", "is_2fa_enrolled", "date_joined")
    list_filter = ("role", "is_active", "is_2fa_enrolled", "discipline_committee_member")
    search_fields = ("email", "first_name", "last_name")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Role & flags",
            {
                "fields": (
                    "role",
                    "discipline_committee_member",
                    "welfare_officer",
                    "manifesto_editor",
                )
            },
        ),
        ("Security", {"fields": ("is_2fa_enrolled", "last_strong_auth_at", "last_login_ip")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "role"),
            },
        ),
    )
