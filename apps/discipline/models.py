"""Disciplinary records — the most security-sensitive module.

Matches docs/erd.md §3. Hard requirements (docs/permissions.md §5.8):

  - case_number is UNSEQUENTIAL (token, not a counter). A sequential id
    leaks how many cases exist and their ordering — itself sensitive.
  - summary and action notes are FIELD-LEVEL ENCRYPTED at rest via
    django-cryptography (keyed by the dedicated CRYPTOGRAPHY_KEY, not
    SECRET_KEY — see settings comment).
  - UUID primary key (same rationale as case_number, plus consistency
    with other sensitive tables).
  - Access is role+flag+2FA+recent-auth, enforced by the Phase 0
    IsDisciplineCommittee permission; the view layer converts a denied
    check into 404, never 403 — an unauthorised caller must not even be
    able to confirm a case exists.

The state machine mirrors a real disciplinary process: opened ->
under_investigation -> hearing -> decided (sanction/dismissed) ->
closed, with an appeal branch.
"""

from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django_cryptography.fields import encrypt


def generate_case_number() -> str:
    """Unsequential, collision-resistant, human-quotable.

    Format: DC-XXXXXXXX (8 hex chars). ~4 billion space; uniqueness is
    additionally guaranteed by the unique constraint with a retry in
    save().
    """
    return f"DC-{secrets.token_hex(4).upper()}"


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CaseCategory(models.TextChoices):
    MISCONDUCT = "misconduct", "Professional misconduct"
    FINANCIAL = "financial", "Financial impropriety"
    ETHICS = "ethics", "Ethics / code of conduct"
    GRIEVANCE = "grievance", "Grievance"
    OTHER = "other", "Other"


class CaseStatus(models.TextChoices):
    OPENED = "opened", "Opened"
    UNDER_INVESTIGATION = "under_investigation", "Under investigation"
    HEARING = "hearing", "Hearing scheduled"
    DECIDED = "decided", "Decided"
    APPEALED = "appealed", "Under appeal"
    CLOSED = "closed", "Closed"


class CaseOutcome(models.TextChoices):
    PENDING = "pending", "Pending"
    DISMISSED = "dismissed", "Dismissed (no case)"
    WARNING = "warning", "Warning issued"
    SUSPENSION = "suspension", "Suspension"
    EXPULSION = "expulsion", "Expulsion"
    OTHER_SANCTION = "other_sanction", "Other sanction"


class DisciplinaryCase(TimeStampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    case_number = models.CharField(max_length=16, unique=True, editable=False)

    subject = models.ForeignKey(
        "members.Member",
        on_delete=models.PROTECT,
        related_name="disciplinary_cases",
    )
    category = models.CharField(max_length=12, choices=CaseCategory.choices)
    # Encrypted at rest. The DB column holds ciphertext; decryption
    # happens only in-process for an authorised request.
    summary = encrypt(models.TextField())

    status = models.CharField(
        max_length=20,
        choices=CaseStatus.choices,
        default=CaseStatus.OPENED,
    )
    outcome = models.CharField(
        max_length=16,
        choices=CaseOutcome.choices,
        default=CaseOutcome.PENDING,
    )

    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="opened_cases",
    )
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-opened_at",)
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["subject", "status"]),
        ]

    def __str__(self) -> str:
        # NEVER include summary (encrypted/sensitive) in repr.
        return f"{self.case_number} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.case_number:
            from django.db import IntegrityError

            for _ in range(5):
                self.case_number = generate_case_number()
                try:
                    return super().save(*args, **kwargs)
                except IntegrityError:
                    self.case_number = ""
            raise IntegrityError("Could not allocate a unique case number after retries.")
        return super().save(*args, **kwargs)

    # ---- state machine --------------------------------------------------

    _CLOSED_STATES = {CaseStatus.CLOSED}

    def _assert_open(self) -> None:
        if self.status in self._CLOSED_STATES:
            raise ValidationError(f"Case {self.case_number} is closed; reopen first.")

    def advance(self, to_status: str) -> None:
        """Move the case forward through the investigation lifecycle."""
        self._assert_open()
        valid = {
            CaseStatus.OPENED: {
                CaseStatus.UNDER_INVESTIGATION,
                CaseStatus.CLOSED,
            },
            CaseStatus.UNDER_INVESTIGATION: {
                CaseStatus.HEARING,
                CaseStatus.CLOSED,
            },
            CaseStatus.HEARING: {CaseStatus.DECIDED},
            CaseStatus.DECIDED: {
                CaseStatus.APPEALED,
                CaseStatus.CLOSED,
            },
            CaseStatus.APPEALED: {CaseStatus.DECIDED, CaseStatus.CLOSED},
        }
        allowed = valid.get(self.status, set())
        if to_status not in allowed:
            raise ValidationError(f"Illegal transition {self.status} -> {to_status}.")
        self.status = to_status
        self.save(update_fields=["status", "updated_at"])

    def decide(self, outcome: str) -> None:
        if self.status not in {CaseStatus.HEARING, CaseStatus.APPEALED}:
            raise ValidationError("A case can only be decided from hearing or appeal.")
        if outcome == CaseOutcome.PENDING:
            raise ValidationError("Must record a concrete outcome.")
        self.status = CaseStatus.DECIDED
        self.outcome = outcome
        self.save(update_fields=["status", "outcome", "updated_at"])

    def close(self) -> None:
        self._assert_open()
        if self.status not in {
            CaseStatus.DECIDED,
            CaseStatus.OPENED,
            CaseStatus.UNDER_INVESTIGATION,
        }:
            raise ValidationError(f"Cannot close from status '{self.status}'.")
        self.status = CaseStatus.CLOSED
        self.closed_at = timezone.now()
        self.save(update_fields=["status", "closed_at", "updated_at"])

    def reopen(self) -> None:
        if self.status != CaseStatus.CLOSED:
            raise ValidationError("Only a closed case can be reopened.")
        self.status = CaseStatus.UNDER_INVESTIGATION
        self.closed_at = None
        self.save(update_fields=["status", "closed_at", "updated_at"])


class ActionType(models.TextChoices):
    NOTE = "note", "Investigation note"
    EVIDENCE = "evidence", "Evidence logged"
    HEARING_MINUTE = "hearing_minute", "Hearing minute"
    DECISION = "decision", "Decision record"
    APPEAL = "appeal", "Appeal record"


class DisciplinaryAction(TimeStampedModel):
    """An append-only timeline entry on a case.

    notes is encrypted at rest like the case summary. Entries are never
    edited or deleted via the API (append-only audit principle); the
    model intentionally exposes no update path beyond creation.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    case = models.ForeignKey(
        DisciplinaryCase,
        on_delete=models.PROTECT,
        related_name="actions",
    )
    action_type = models.CharField(max_length=16, choices=ActionType.choices)
    notes = encrypt(models.TextField())
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_actions",
    )

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        # No notes in repr — sensitive.
        return f"{self.action_type} on {self.case.case_number}"
