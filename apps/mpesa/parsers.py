"""Parsers for Safaricom's payload shapes.

Daraja sends two very different JSON structures for C2B confirmation vs
STK callback. We normalise both into InboundPayment so reconciliation
doesn't care which channel a payment arrived on. Parsing is defensive:
Safaricom's field presence varies, so every getter tolerates absence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from apps.mpesa.models import MpesaTxnKind
from apps.mpesa.reconciliation import InboundPayment


class PayloadError(ValueError):
    """Raised when a webhook body can't be parsed into a payment."""


def _decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise PayloadError(f"Bad amount: {value!r}") from None


def _parse_c2b_timestamp(raw: str):
    # Safaricom C2B uses "YYYYMMDDHHMMSS".
    if not raw:
        return datetime.now(UTC)
    try:
        return datetime.strptime(str(raw), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return datetime.now(UTC)


def parse_c2b_confirmation(body: dict) -> InboundPayment:
    """C2B confirmation payload -> InboundPayment.

    Shape (abridged): TransID, TransAmount, MSISDN, BillRefNumber,
    TransTime.
    """
    receipt = body.get("TransID") or ""
    if not receipt:
        raise PayloadError("C2B payload missing TransID")
    return InboundPayment(
        mpesa_receipt=str(receipt),
        account_reference=str(body.get("BillRefNumber", "")).strip(),
        msisdn=str(body.get("MSISDN", "")),
        amount_kes=_decimal(body.get("TransAmount")),
        paid_at=_parse_c2b_timestamp(body.get("TransTime", "")),
        kind=MpesaTxnKind.C2B,
        raw_payload=body,
    )


def _stk_metadata(body: dict) -> dict:
    """Pull the CallbackMetadata Items list into a flat dict."""
    stk = body.get("Body", {}).get("stkCallback", {})
    items = stk.get("CallbackMetadata", {}).get("Item", [])
    flat: dict = {}
    for item in items:
        name = item.get("Name")
        if name is not None:
            flat[name] = item.get("Value")
    return flat


def parse_stk_callback(body: dict) -> InboundPayment:
    """STK push callback -> InboundPayment.

    Only successful callbacks (ResultCode 0) carry payment metadata; the
    caller is expected to check result code first via stk_result_code().
    """
    meta = _stk_metadata(body)
    receipt = meta.get("MpesaReceiptNumber") or ""
    if not receipt:
        raise PayloadError("STK callback missing MpesaReceiptNumber")

    ts = meta.get("TransactionDate")
    paid_at = _parse_c2b_timestamp(str(ts) if ts else "")

    return InboundPayment(
        mpesa_receipt=str(receipt),
        account_reference=str(body.get("__account_reference__", "")).strip(),
        msisdn=str(meta.get("PhoneNumber", "")),
        amount_kes=_decimal(meta.get("Amount")),
        paid_at=paid_at,
        kind=MpesaTxnKind.STK,
        raw_payload=body,
    )


def stk_result_code(body: dict) -> int:
    try:
        return int(body.get("Body", {}).get("stkCallback", {}).get("ResultCode", -1))
    except (TypeError, ValueError):
        return -1
