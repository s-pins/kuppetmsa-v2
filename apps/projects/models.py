"""Project model.

Matches docs/erd.md §2. The cross-link that matters: finances.Expense
gains a nullable FK to Project this phase (it was deliberately deferred
in Phase 2 so finances could migrate standalone). That FK is what makes
budget-vs-actual real on the public transparency page.

spent_kes / variance are computed, never stored — they always reflect
the current set of APPROVED expenses tagged to the project. Proposed or
rejected expenses do not count against budget, matching how the
transparency aggregate treats them.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import Sum


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ProjectStatus(models.TextChoices):
    PLANNED = "planned", "Planned"
    ACTIVE = "active", "Active"
    ON_HOLD = "on_hold", "On hold"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class Project(TimeStampedModel):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=12,
        choices=ProjectStatus.choices,
        default=ProjectStatus.PLANNED,
    )
    budget_kes = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    started_on = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)
    beneficiaries = models.CharField(max_length=255, blank=True)
    is_public = models.BooleanField(
        default=True,
        help_text="Visible on the public transparency site.",
    )

    class Meta:
        ordering = ("-started_on", "name")
        indexes = [models.Index(fields=["status", "is_public"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.status})"

    @property
    def spent_kes(self) -> Decimal:
        """Sum of APPROVED expenses tagged to this project.

        An unsaved instance has no PK, so the reverse relation can't be
        queried — and semantically it can have no expenses yet, so the
        answer is zero. Returning 0 here (rather than letting Django
        raise ValueError) keeps spent_kes / variance_kes safe to call on
        any instance, saved or not.
        """
        if self.pk is None:
            return Decimal("0.00")

        from apps.finances.models import ExpenseStatus

        total = self.expenses.filter(status=ExpenseStatus.APPROVED).aggregate(s=Sum("amount_kes"))[
            "s"
        ]
        return total or Decimal("0.00")

    @property
    def variance_kes(self) -> Decimal:
        """Budget minus spent. Negative == over budget.

        budget_kes may still be a str on an unsaved in-memory instance;
        coerce defensively so the property never depends on whether the
        object has been through field coercion (mirrors
        Expense.is_large).
        """
        budget = self.budget_kes
        if not isinstance(budget, Decimal):
            budget = Decimal(str(budget))
        return budget - self.spent_kes
