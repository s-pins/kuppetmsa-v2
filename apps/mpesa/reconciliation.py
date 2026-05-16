"""Reconciliation: turn a raw inbound M-Pesa event into a member
contribution, or flag it for the treasurer.

Idempotency is the whole game here. Safaricom retries confirmation
webhooks aggressively until it gets a success response. The unique
constraint on MpesaTransaction.mpesa_receipt plus the get_or_create here
means a retried receipt is recognised as a duplicate and never
double-credits a member.

Matching rule (docs/PLAN.md §8): the account reference the payer typed
is expected to be a membership_id. Exact match -> create a reconciled
contribution. No match -> store the transaction as UNMATCHED so it
surfaces in the treasurer's review queue. We never guess.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.finances.models import (
    BankAccount,
    ContributionSource,
    FinancialContribution,
)
from apps.members.models import Member
from apps.mpesa.models import (
    MpesaTransaction,
    MpesaTxnKind,
    MpesaTxnStatus,
)

logger = logging.getLogger("mpesa")


@dataclass
class InboundPayment:
    """Normalised shape both C2B and STK callbacks reduce to."""

    mpesa_receipt: str
    account_reference: str
    msisdn: str
    amount_kes: Decimal
    paid_at: object  # datetime
    kind: str
    raw_payload: dict


@dataclass
class ReconcileResult:
    transaction: MpesaTransaction
    created: bool
    status: str


def _default_bank_account() -> BankAccount | None:
    return BankAccount.objects.filter(is_active=True).order_by("pk").first()


@transaction.atomic
def reconcile_inbound(payment: InboundPayment) -> ReconcileResult:
    """Idempotently record an inbound payment.

    Returns the (possibly pre-existing) MpesaTransaction and whether this
    call created it.
    """
    txn, created = MpesaTransaction.objects.get_or_create(
        mpesa_receipt=payment.mpesa_receipt,
        defaults={
            "kind": payment.kind,
            "account_reference": payment.account_reference,
            "msisdn": MpesaTransaction.mask_msisdn(payment.msisdn),
            "amount_kes": payment.amount_kes,
            "paid_at": payment.paid_at,
            "raw_payload": payment.raw_payload,
            "status": MpesaTxnStatus.RECEIVED,
        },
    )

    if not created:
        # Safaricom retry of an already-seen receipt. Do nothing further.
        if txn.status == MpesaTxnStatus.RECEIVED:
            txn.status = MpesaTxnStatus.DUPLICATE
            txn.note = "Duplicate webhook for an unprocessed receipt."
            txn.save(update_fields=["status", "note", "updated_at"])
        logger.info(
            "Duplicate M-Pesa receipt %s ignored (status=%s)",
            payment.mpesa_receipt,
            txn.status,
        )
        return ReconcileResult(txn, created=False, status=txn.status)

    member = Member.objects.filter(membership_id__iexact=payment.account_reference.strip()).first()

    if member is None:
        txn.status = MpesaTxnStatus.UNMATCHED
        txn.note = (
            f"No member with membership_id '{payment.account_reference}'. Needs treasurer review."
        )
        txn.save(update_fields=["status", "note", "updated_at"])
        logger.warning(
            "Unmatched M-Pesa payment %s ref=%s amount=%s",
            payment.mpesa_receipt,
            payment.account_reference,
            payment.amount_kes,
        )
        return ReconcileResult(txn, created=True, status=txn.status)

    account = _default_bank_account()
    if account is None:
        txn.status = MpesaTxnStatus.UNMATCHED
        txn.note = "No active bank account configured to credit."
        txn.save(update_fields=["status", "note", "updated_at"])
        logger.error(
            "M-Pesa %s matched member %s but no active bank account exists",
            payment.mpesa_receipt,
            member.membership_id,
        )
        return ReconcileResult(txn, created=True, status=txn.status)

    source = (
        ContributionSource.MPESA_STK
        if payment.kind == MpesaTxnKind.STK
        else ContributionSource.MPESA_C2B
    )
    contribution = FinancialContribution.objects.create(
        member=member,
        bank_account=account,
        amount_kes=payment.amount_kes,
        source=source,
        mpesa_ref=payment.mpesa_receipt,
        paid_at=payment.paid_at or timezone.now(),
        reconciled=True,
    )
    txn.contribution = contribution
    txn.status = MpesaTxnStatus.MATCHED
    txn.note = f"Auto-matched to {member.membership_id}."
    txn.save(update_fields=["contribution", "status", "note", "updated_at"])
    logger.info(
        "M-Pesa %s auto-matched to %s (KES %s)",
        payment.mpesa_receipt,
        member.membership_id,
        payment.amount_kes,
    )
    return ReconcileResult(txn, created=True, status=txn.status)
