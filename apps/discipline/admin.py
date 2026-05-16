"""Admin for discipline — view-only, staff superusers only.

Disciplinary records must not be hand-edited in the Django admin:
the state machine, encryption, recent-auth gate and audit middleware
only apply on the API path. Admin is registered for emergency
inspection by a superuser but blocks all mutation.
"""

from django.contrib import admin

from apps.discipline.models import DisciplinaryAction, DisciplinaryCase


@admin.register(DisciplinaryCase)
class DisciplinaryCaseAdmin(admin.ModelAdmin):
    list_display = (
        "case_number",
        "category",
        "status",
        "outcome",
        "opened_at",
    )
    list_filter = ("status", "category", "outcome")
    # Deliberately NOT searchable on subject/summary — minimise
    # incidental exposure in the admin changelist.
    readonly_fields = [f.name for f in DisciplinaryCase._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DisciplinaryAction)
class DisciplinaryActionAdmin(admin.ModelAdmin):
    list_display = ("action_type", "case", "recorded_by", "created_at")
    list_filter = ("action_type",)
    readonly_fields = [f.name for f in DisciplinaryAction._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
