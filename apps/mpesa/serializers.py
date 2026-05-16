"""M-Pesa serializers."""

from decimal import Decimal

from rest_framework import serializers

from apps.mpesa.models import MpesaTransaction


class MpesaTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MpesaTransaction
        fields = [
            "id",
            "kind",
            "status",
            "mpesa_receipt",
            "account_reference",
            "msisdn",
            "amount_kes",
            "paid_at",
            "contribution",
            "note",
            "created_at",
        ]
        read_only_fields = fields


class StkPushSerializer(serializers.Serializer):
    msisdn = serializers.RegexField(
        r"^254\d{9}$",
        help_text="Payer phone in 2547XXXXXXXX format.",
    )
    amount_kes = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("1.00"),
    )
