"""Welfare claim model.

Matches docs/erd.md §3. Design decisions carried from earlier phases:

  - UUID primary key (Phase 2 precedent for money-bearing tables —
    sequential ids leak claim volume/ordering, a privacy concern for
    welfare).
  - State machine transitions (submit -> review -> approve/reject ->
    paid) enforce the docs/permissions.md §6 threshold AT THE MODEL
    LAYER, not only in views, so the rule holds whether the call comes
    from API, admin, or shell (Phase 2 pattern).
  - is_large coerces amount defensively (Phase 4 bug class: str vs
    Decimal on uncoerced in-memory instances).
  - PROTECT from the linked Expense so paying a claim can never orphan
    its disbursement record.

Threshold rule (docs/permissions.md §5.7/§6): a welfare reviewer may
approve claims at or below WELFARE_AUTO_APPROVE_THRESHOLD_KES. Above it,
only leadership may approve. The model exposes requires_leadership_approval
so views/permissions enforce the right gate; the model itself refuses an
out-of-policy transition regardless.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.constants import (
    LEADERSHIP_ROLES,
    WELFARE_AUTO_APPROVE_THRESHOLD_KES,
)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class WelfareCategory(models.TextChoices):
    BEREAVEMENT = "bereavement", "Bereavement"
    ILLNESS = "illness", "Illness / hospitalisation"
    ACCIDENT = "accident", "Accident"
    EDUCATION = "education", "Education support"
    OTHER = "other", "Other"


class WelfareStatus(models.TextChoices):
    SUBMITTED = "submitted", "Submitted"
    UNDER_REVIEW = "under_review", "Under review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    PAID = "paid", "Paid"
    WITHDRAWN = "withdrawn", "Withdrawn by claimant"


class WelfareClaim(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    claimant = models.ForeignKey(
        "members.Member",
        on_delete=models.PROTECT,
        related_name="welfare_claims",
    )
    category = models.CharField(max_length=12, choices=WelfareCategory.choices)
    amount_requested_kes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    description = models.TextField()
    status = models.CharField(
        max_length=12,
        choices=WelfareStatus.choices,
        default=WelfareStatus.SUBMITTED,
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_welfare_claims",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_notes = models.TextField(blank=True)

    # Set when the approved claim is disbursed and linked to finances.
    expense = models.OneToOneField(
        "finances.Expense",
        on_delete=models.PROTECT,
        related_name="welfare_claim",
        null=True,
        blank=True,
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["claimant", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_requested_kes__gt=0),
                name="welfare_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.claimant} — {self.category} — KES {self.amount_requested_kes} ({self.status})"
        )

    # ---- threshold logic ------------------------------------------------

    @property
    def requires_leadership_approval(self) -> bool:
        """True if the amount exceeds the reviewer auto-approve ceiling.

        Defensive Decimal coercion: amount may still be a str on an
        in-memory instance not yet through field coercion (Phase 4 bug
        class).
        """
        amount = self.amount_requested_kes
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        return amount > Decimal(str(WELFARE_AUTO_APPROVE_THRESHOLD_KES))

    # ---- state machine --------------------------------------------------

    _OPEN_FOR_REVIEW = {
        WelfareStatus.SUBMITTED,
        WelfareStatus.UNDER_REVIEW,
    }

    def _assert_reviewer(self, actor) -> None:
        is_leadership = actor.role in LEADERSHIP_ROLES
        is_welfare_officer = bool(getattr(actor, "welfare_officer", False))
        if not (is_leadership or is_welfare_officer):
            raise ValidationError("Only welfare reviewers may act on this claim.")

    def start_review(self, actor) -> None:
        self._assert_reviewer(actor)
        if self.status != WelfareStatus.SUBMITTED:
            raise ValidationError(f"Cannot start review from status '{self.status}'.")
        self.status = WelfareStatus.UNDER_REVIEW
        self.reviewed_by = actor
        self.save(update_fields=["status", "reviewed_by", "updated_at"])

    def approve(self, actor, note: str = "") -> None:
        self._assert_reviewer(actor)
        if self.status not in self._OPEN_FOR_REVIEW:
            raise ValidationError(f"Cannot approve a claim in status '{self.status}'.")
        # Threshold gate: above the ceiling requires a leadership actor,
        # not merely a welfare_officer.
        if self.requires_leadership_approval and actor.role not in LEADERSHIP_ROLES:
            raise ValidationError(
                "Claims above the welfare threshold require leadership "
                "approval; a welfare officer cannot approve this amount."
            )
        self.status = WelfareStatus.APPROVED
        self.reviewed_by = actor
        self.reviewed_at = timezone.now()
        self.reviewer_notes = note
        self.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "reviewer_notes",
                "updated_at",
            ]
        )

    def reject(self, actor, note: str = "") -> None:
        self._assert_reviewer(actor)
        if self.status not in self._OPEN_FOR_REVIEW:
            raise ValidationError(f"Cannot reject a claim in status '{self.status}'.")
        self.status = WelfareStatus.REJECTED
        self.reviewed_by = actor
        self.reviewed_at = timezone.now()
        self.reviewer_notes = note
        self.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "reviewer_notes",
                "updated_at",
            ]
        )

    def withdraw(self, by_member) -> None:
        """The claimant withdraws their own claim, only while open."""
        if by_member != self.claimant:
            raise ValidationError("Only the claimant may withdraw their claim.")
        if self.status not in self._OPEN_FOR_REVIEW:
            raise ValidationError(f"Cannot withdraw a claim in status '{self.status}'.")
        self.status = WelfareStatus.WITHDRAWN
        self.save(update_fields=["status", "updated_at"])

    def mark_paid(self, expense) -> None:
        """Link an approved claim to its disbursement Expense.

        Caller (the finances integration) is responsible for creating the
        Expense; this only flips state and records the link, refusing if
        the claim was not approved.
        """
        if self.status != WelfareStatus.APPROVED:
            raise ValidationError("Only an approved claim can be marked paid.")
        self.expense = expense
        self.status = WelfareStatus.PAID
        self.paid_at = timezone.now()
        self.save(
            update_fields=[
                "expense",
                "status",
                "paid_at",
                "updated_at",
            ]
        )
