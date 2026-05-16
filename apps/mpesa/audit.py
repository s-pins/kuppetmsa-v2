"""Audit-log registration for M-Pesa.

Inbound money events are audit-critical. The raw_payload is excluded
from the diff (it is large and already stored verbatim on the row);
status transitions and the contribution link are what matter for the
trail.
"""

from auditlog.registry import auditlog

from apps.mpesa.models import MpesaTransaction

auditlog.register(
    MpesaTransaction,
    exclude_fields=["raw_payload", "created_at", "updated_at"],
)
