"""Admin for M-Pesa transactions — inspection only.

Transactions are created by webhooks/reconciliation, never by hand. The
admin is read-only so a clerical edit can't desynchronise a row from the
contribution it produced.
"""

from django.contrib import admin

from apps.mpesa.models import MpesaTransaction


@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "mpesa_receipt",
        "kind",
        "status",
        "amount_kes",
        "account_reference",
        "paid_at",
    )
    list_filter = ("status", "kind")
    search_fields = ("mpesa_receipt", "account_reference")
    readonly_fields = [f.name for f in MpesaTransaction._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
