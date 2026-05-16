"""Admin for welfare claims.

Read-mostly. Decisions must go through the API where the state machine,
threshold gate, and audit middleware apply — not be hand-edited here.
"""

from django.contrib import admin

from apps.welfare.models import WelfareClaim


@admin.register(WelfareClaim)
class WelfareClaimAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "claimant",
        "category",
        "amount_requested_kes",
        "status",
        "reviewed_by",
        "paid_at",
    )
    list_filter = ("status", "category")
    search_fields = (
        "claimant__first_name",
        "claimant__last_name",
        "claimant__membership_id",
    )
    readonly_fields = (
        "id",
        "claimant",
        "amount_requested_kes",
        "status",
        "reviewed_by",
        "reviewed_at",
        "reviewer_notes",
        "expense",
        "paid_at",
        "created_at",
        "updated_at",
    )

    def has_delete_permission(self, request, obj=None):
        return False
