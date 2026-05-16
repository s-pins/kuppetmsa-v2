"""M-Pesa API.

Endpoint permission model:

  - validate / confirm (C2B webhooks) : AllowAny. Safaricom calls these
    server-to-server; they cannot present a JWT. Protection is by
    receipt-uniqueness + idempotent reconciliation, not auth. In
    production these are additionally IP-allowlisted to Safaricom at the
    nginx layer (documented in DEPLOYMENT.md).
  - stk-push (member-initiated)       : authenticated member, paying for
    themselves.
  - transactions / unmatched review   : finance-view roles.

The webhooks always return Safaricom's expected ack shape even on our
internal errors — returning a 500 makes Safaricom retry forever, which
corrupts nothing (idempotent) but spams logs.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from rest_framework import decorators, permissions, response, status, viewsets
from rest_framework.views import APIView

from apps.core.constants import FINANCE_VIEW_ROLES
from apps.core.permissions import HasAnyRole
from apps.mpesa.adapters import get_adapter
from apps.mpesa.models import MpesaTransaction, MpesaTxnStatus
from apps.mpesa.parsers import (
    PayloadError,
    parse_c2b_confirmation,
    parse_stk_callback,
    stk_result_code,
)
from apps.mpesa.reconciliation import reconcile_inbound
from apps.mpesa.serializers import MpesaTransactionSerializer, StkPushSerializer

logger = logging.getLogger("mpesa")

_C2B_ACCEPT = {"ResultCode": 0, "ResultDesc": "Accepted"}


class C2BValidationView(APIView):
    """Safaricom calls this before completing a Paybill payment.

    We accept everything (the union wants all incoming payments recorded
    even if the account ref is wrong — it becomes an UNMATCHED txn for
    the treasurer, not a rejected payment).
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def post(self, request):
        return response.Response(_C2B_ACCEPT)


class C2BConfirmationView(APIView):
    """Safaricom calls this after a successful Paybill payment."""

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def post(self, request):
        try:
            payment = parse_c2b_confirmation(request.data)
            reconcile_inbound(payment)
        except PayloadError as exc:
            logger.warning("Unparseable C2B payload: %s", exc)
        except Exception:
            # Never 500 to Safaricom; it would retry indefinitely.
            logger.exception("C2B confirmation processing error")
        return response.Response(_C2B_ACCEPT)


class StkCallbackView(APIView):
    """Safaricom calls this with the result of an STK push."""

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def post(self, request):
        body = request.data
        try:
            if stk_result_code(body) != 0:
                logger.info("STK callback non-zero result; nothing to record")
                return response.Response(_C2B_ACCEPT)
            payment = parse_stk_callback(body)
            reconcile_inbound(payment)
        except PayloadError as exc:
            logger.warning("Unparseable STK callback: %s", exc)
        except Exception:
            logger.exception("STK callback processing error")
        return response.Response(_C2B_ACCEPT)


class StkPushView(APIView):
    """Member-initiated payment from the portal.

    The member pays for their own membership; account reference is forced
    to their own membership_id server-side so a member can't push a
    payment crediting someone else.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        body = StkPushSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        member = getattr(request.user, "member_profile", None)
        if member is None:
            return response.Response(
                {"detail": "No member profile linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        adapter = get_adapter()
        result = adapter.initiate_stk_push(
            msisdn=body.validated_data["msisdn"],
            amount=Decimal(str(body.validated_data["amount_kes"])),
            account_reference=member.membership_id,
            description="KUPPET dues",
        )
        return response.Response(
            {
                "ok": result.ok,
                "checkout_request_id": result.checkout_request_id,
                "customer_message": result.customer_message,
            },
            status=(status.HTTP_200_OK if result.ok else status.HTTP_502_BAD_GATEWAY),
        )


class MpesaTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """Treasurer-facing log + unmatched review queue."""

    queryset = MpesaTransaction.objects.select_related("contribution")
    serializer_class = MpesaTransactionSerializer
    filterset_fields = ["status", "kind"]

    def get_permissions(self):
        return [
            permissions.IsAuthenticated(),
            HasAnyRole(FINANCE_VIEW_ROLES)(),
        ]

    @decorators.action(detail=False, methods=["get"])
    def unmatched(self, request):
        qs = self.get_queryset().filter(status=MpesaTxnStatus.UNMATCHED)
        page = self.paginate_queryset(qs)
        data = self.get_serializer(page if page is not None else qs, many=True).data
        if page is not None:
            return self.get_paginated_response(data)
        return response.Response(data)
