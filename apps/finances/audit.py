"""Audit-log registration for finance models.

docs/PLAN.md makes a full audit trail mandatory for anything touching
money. We register every finance model with django-auditlog so each
create/update/delete is recorded with actor and field-level diff.

auditlog's LogEntry has a GenericForeignKey to the tracked row; there is
no FK to draw on the ERD (noted in docs/erd.md §4).
"""

from auditlog.registry import auditlog

from apps.finances.models import BankAccount, Expense, FinancialContribution

auditlog.register(BankAccount)
auditlog.register(
    FinancialContribution,
    # mpesa_ref/amount are the audit-critical fields; track everything
    # except the bookkeeping timestamps to keep diffs readable.
    exclude_fields=["created_at", "updated_at"],
)
auditlog.register(
    Expense,
    exclude_fields=["created_at", "updated_at"],
)
