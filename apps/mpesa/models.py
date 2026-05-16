"""M-Pesa transaction log.

Every inbound M-Pesa event (C2B confirmation, STK callback) is recorded
here verbatim *before* we try to turn it into a FinancialContribution.
This separation matters: the raw log is the forensic record of "what
Safaricom told us", independent of whether reconciliation succeeded. An
unmatched payment still has a row here for the treasurer to investigate.
"""

from __future__ import annotations

import uuid

from django.db import models


class MpesaTxnKind(models.TextChoices):
    C2B = "c2b", "Paybill C2B"
    STK = "stk", "STK push"


class MpesaTxnStatus(models.TextChoices):
    RECEIVED = "received", "Received, not yet processed"
    MATCHED = "matched", "Matched to a member"
    UNMATCHED = "unmatched", "No member found — needs review"
    DUPLICATE = "duplicate", "Duplicate receipt, ignored"
    FAILED = "failed", "STK push failed / cancelled"


class MpesaTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    kind = models.CharField(max_length=8, choices=MpesaTxnKind.choices)
    status = models.CharField(
        max_length=12,
        choices=MpesaTxnStatus.choices,
        default=MpesaTxnStatus.RECEIVED,
    )

    # Safaricom's unique receipt (e.g. "QGR7XK2P9L"). Unique so a retried
    # webhook can't double-credit.
    mpesa_receipt = models.CharField(max_length=32, unique=True)
    account_reference = models.CharField(
        max_length=64,
        blank=True,
        help_text="What the payer typed as the account — expected to be a membership_id for C2B.",
    )
    msisdn = models.CharField(
        max_length=20,
        blank=True,
        help_text="Payer phone, stored masked.",
    )
    amount_kes = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField()

    raw_payload = models.JSONField(default=dict)

    contribution = models.OneToOneField(
        "finances.FinancialContribution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mpesa_transaction",
    )
    note = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-paid_at",)
        indexes = [
            models.Index(fields=["status", "paid_at"]),
            models.Index(fields=["account_reference"]),
        ]

    def __str__(self) -> str:
        return f"{self.mpesa_receipt} — KES {self.amount_kes} ({self.status})"

    @staticmethod
    def mask_msisdn(raw: str) -> str:
        """254712345678 -> 2547****5678. Never store the full number."""
        if not raw or len(raw) < 8:
            return raw
        return f"{raw[:4]}****{raw[-4:]}"
