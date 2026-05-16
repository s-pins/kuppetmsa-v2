"""Finance models.

Matches docs/erd.md §1 (People & money). Design decisions:

  - UUID primary keys on FinancialContribution and Expense. Sequential
    integer ids leak transaction volume and ordering — a real privacy
    concern for union finances.
  - PROTECT from these tables onto BankAccount and Member: you cannot
    delete an account or member that has financial history. Deactivate.
  - Expense is a state machine. Large expenses (> threshold) require a
    second leadership signatory who is NOT the creator (two-person rule,
    docs/permissions.md §6.1). That rule is enforced here at the model
    layer via approve()/reject(), not only in views, so it holds no
    matter which surface (API, admin, shell) drives it.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.constants import LARGE_EXPENSE_THRESHOLD_KES, LEADERSHIP_ROLES


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BankAccount(TimeStampedModel):
    name = models.CharField(max_length=120)
    paybill = models.CharField(max_length=20, blank=True)
    balance_kes = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} ({self.paybill or 'no paybill'})"


class ContributionSource(models.TextChoices):
    MPESA_C2B = "mpesa_c2b", "M-Pesa Paybill (C2B)"
    MPESA_STK = "mpesa_stk", "M-Pesa STK push"
    MANUAL_CASH = "manual_cash", "Cash (manual entry)"
    BANK_TRANSFER = "bank_transfer", "Bank transfer"


class FinancialContribution(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    member = models.ForeignKey(
        "members.Member",
        on_delete=models.PROTECT,
        related_name="contributions",
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="contributions",
    )
    amount_kes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    source = models.CharField(max_length=20, choices=ContributionSource.choices)
    # Nullable: manual/cash entries have no M-Pesa reference.
    mpesa_ref = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        unique=True,
    )
    paid_at = models.DateTimeField(default=timezone.now)
    # False == unmatched, sits in the treasurer reconciliation queue.
    reconciled = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_contributions",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-paid_at",)
        indexes = [
            models.Index(fields=["reconciled", "paid_at"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self) -> str:
        return f"KES {self.amount_kes} from {self.member} ({self.source})"


class ExpenseStatus(models.TextChoices):
    PROPOSED = "proposed", "Proposed"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class Expense(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="expenses",
    )
    # NOTE: project FK is added in Phase 4 when the projects app lands
    # (see docs/erd.md §2 cross-link). Kept out of Phase 2 so finances
    # migrates as a self-contained unit.
    amount_kes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    description = models.TextField()
    status = models.CharField(
        max_length=12,
        choices=ExpenseStatus.choices,
        default=ExpenseStatus.PROPOSED,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_expenses",
    )
    # Set when a leadership user approves/rejects. Must differ from
    # created_by for large expenses (two-person rule).
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approved_expenses",
        null=True,
        blank=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_kes__gt=0),
                name="expense_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"KES {self.amount_kes} — {self.status} — {self.description[:40]}"

    @property
    def is_large(self) -> bool:
        return self.amount_kes > Decimal(str(LARGE_EXPENSE_THRESHOLD_KES))

    @property
    def requires_second_signatory(self) -> bool:
        """Large expenses need a different leadership user to approve."""
        return self.is_large

    def _assert_can_decide(self, actor) -> None:
        if self.status != ExpenseStatus.PROPOSED:
            raise ValidationError(f"Expense is already {self.status}; cannot decide again.")
        if actor.role not in LEADERSHIP_ROLES:
            raise ValidationError("Only leadership may approve or reject expenses.")
        # Two-person rule: for large expenses the decider must not be the
        # creator. This holds even if one person wears both hats (chair
        # who is also treasurer) — they are blocked, a different
        # leadership user must act.
        if self.requires_second_signatory and actor.pk == self.created_by_id:
            raise ValidationError(
                "Large expenses require a second leadership signatory. "
                "The person who created this expense cannot also approve it."
            )

    def approve(self, actor, note: str = "") -> None:
        self._assert_can_decide(actor)
        self.status = ExpenseStatus.APPROVED
        self.approved_by = actor
        self.decided_at = timezone.now()
        self.decision_note = note
        self.save(
            update_fields=[
                "status",
                "approved_by",
                "decided_at",
                "decision_note",
                "updated_at",
            ]
        )

    def reject(self, actor, note: str = "") -> None:
        self._assert_can_decide(actor)
        self.status = ExpenseStatus.REJECTED
        self.approved_by = actor
        self.decided_at = timezone.now()
        self.decision_note = note
        self.save(
            update_fields=[
                "status",
                "approved_by",
                "decided_at",
                "decision_note",
                "updated_at",
            ]
        )
