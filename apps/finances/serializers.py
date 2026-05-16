"""Finance serializers.

Maps to docs/permissions.md §5.3. The transparency serializer is the only
one ever exposed without auth — and it carries aggregates only, never
member-identifying rows.
"""

from rest_framework import serializers

from apps.finances.models import (
    BankAccount,
    Expense,
    FinancialContribution,
)


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = [
            "id",
            "name",
            "paybill",
            "balance_kes",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ContributionSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)

    class Meta:
        model = FinancialContribution
        fields = [
            "id",
            "member",
            "member_name",
            "bank_account",
            "amount_kes",
            "source",
            "mpesa_ref",
            "paid_at",
            "reconciled",
            "recorded_by",
            "created_at",
        ]
        read_only_fields = ["id", "recorded_by", "created_at"]


class ExpenseSerializer(serializers.ModelSerializer):
    is_large = serializers.BooleanField(read_only=True)
    requires_second_signatory = serializers.BooleanField(read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "bank_account",
            "project",
            "amount_kes",
            "description",
            "status",
            "created_by",
            "approved_by",
            "decided_at",
            "decision_note",
            "is_large",
            "requires_second_signatory",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_by",
            "approved_by",
            "decided_at",
            "decision_note",
            "created_at",
        ]


class ExpenseDecisionSerializer(serializers.Serializer):
    """Body for the approve/reject actions."""

    note = serializers.CharField(required=False, allow_blank=True, default="")


class TransparencySerializer(serializers.Serializer):
    """Public, aggregate-only. No member identities, no row-level data."""

    total_contributions_kes = serializers.DecimalField(max_digits=16, decimal_places=2)
    total_approved_expenses_kes = serializers.DecimalField(max_digits=16, decimal_places=2)
    net_position_kes = serializers.DecimalField(max_digits=16, decimal_places=2)
    contributions_by_source = serializers.DictField(
        child=serializers.DecimalField(max_digits=16, decimal_places=2)
    )
    monthly_contributions = serializers.ListField(child=serializers.DictField())
    generated_at = serializers.DateTimeField()
