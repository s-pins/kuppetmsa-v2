"""Admin for finance models.

Deliberately conservative: amounts and statuses are mostly read-only in
admin. Real money operations (recording, approving) must go through the
API/console where the two-person rule and audit middleware apply. Admin
is for inspection and correcting clerical fields only.
"""

from django.contrib import admin

from apps.finances.models import BankAccount, Expense, FinancialContribution


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "paybill", "balance_kes", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "paybill")


@admin.register(FinancialContribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "member",
        "amount_kes",
        "source",
        "reconciled",
        "paid_at",
    )
    list_filter = ("reconciled", "source")
    search_fields = ("mpesa_ref", "member__first_name", "member__last_name")
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = ("member",)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "amount_kes",
        "status",
        "created_by",
        "approved_by",
        "decided_at",
    )
    list_filter = ("status",)
    search_fields = ("description",)
    readonly_fields = (
        "id",
        "status",
        "created_by",
        "approved_by",
        "decided_at",
        "decision_note",
        "created_at",
        "updated_at",
    )
