"""Welfare serializers — docs/permissions.md §5.7.

Claimants submit and see their own claims (limited fields). Reviewers
see the full record including reviewer notes and the linked expense.
"""

from rest_framework import serializers

from apps.welfare.models import WelfareClaim


class WelfareClaimCreateSerializer(serializers.ModelSerializer):
    """A member submitting a claim. claimant is forced server-side."""

    class Meta:
        model = WelfareClaim
        fields = [
            "id",
            "category",
            "amount_requested_kes",
            "description",
        ]
        read_only_fields = ["id"]


class MyWelfareClaimSerializer(serializers.ModelSerializer):
    """Claimant's view of their own claim — no internal reviewer notes
    until a decision is recorded, then the note is shown so they know
    why."""

    class Meta:
        model = WelfareClaim
        fields = [
            "id",
            "category",
            "amount_requested_kes",
            "description",
            "status",
            "reviewer_notes",
            "paid_at",
            "created_at",
        ]
        read_only_fields = fields


class WelfareClaimReviewSerializer(serializers.ModelSerializer):
    """Reviewer's full view."""

    claimant_name = serializers.CharField(source="claimant.full_name", read_only=True)
    requires_leadership_approval = serializers.BooleanField(read_only=True)

    class Meta:
        model = WelfareClaim
        fields = [
            "id",
            "claimant",
            "claimant_name",
            "category",
            "amount_requested_kes",
            "description",
            "status",
            "requires_leadership_approval",
            "reviewed_by",
            "reviewed_at",
            "reviewer_notes",
            "expense",
            "paid_at",
            "created_at",
        ]
        read_only_fields = fields


class WelfareDecisionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default="")
