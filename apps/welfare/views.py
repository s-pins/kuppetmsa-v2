"""Welfare API — docs/permissions.md §5.7.

Two viewsets:

  WelfareClaimViewSet     — member-facing: submit, list own, withdraw own
  WelfareReviewViewSet    — reviewer-facing: queue, start review,
                            approve/reject, mark paid

mark_paid is the finances integration point: approving a claim does NOT
move money; a reviewer then explicitly disburses it, which creates an
Expense (so welfare spend flows through the same audited finance trail
and the public transparency aggregate) and links it back to the claim.
Creating that Expense is gated to finance-write roles, matching the rule
that only treasury moves money.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import (
    decorators,
    mixins,
    permissions,
    response,
    status,
    viewsets,
)

from apps.core.constants import FINANCE_WRITE_ROLES
from apps.finances.models import BankAccount, Expense
from apps.portal.permissions import IsMemberWithProfile
from apps.welfare.models import WelfareClaim, WelfareStatus
from apps.welfare.permissions import IsWelfareReviewer
from apps.welfare.serializers import (
    MyWelfareClaimSerializer,
    WelfareClaimCreateSerializer,
    WelfareClaimReviewSerializer,
    WelfareDecisionSerializer,
)


class _IsFinanceWrite(permissions.BasePermission):
    """Treasury-only gate for welfare disbursement.

    Disbursing a welfare payout creates an Expense — moving money — so
    it is restricted to finance-write roles, independent of who may
    *review* a claim.
    """

    message = "Only treasury (finance-write) may disburse a welfare payment."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False
        return user.role in FINANCE_WRITE_ROLES


class WelfareClaimViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Member-facing. Strictly scoped to the caller's own claims."""

    permission_classes = [IsMemberWithProfile]

    def get_serializer_class(self):
        if self.action == "create":
            return WelfareClaimCreateSerializer
        return MyWelfareClaimSerializer

    def get_queryset(self):
        return WelfareClaim.objects.filter(claimant=self.request.user.member_profile).order_by(
            "-created_at"
        )

    def perform_create(self, serializer):
        serializer.save(claimant=self.request.user.member_profile)

    @decorators.action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        claim = self.get_object()
        try:
            claim.withdraw(request.user.member_profile)
        except DjangoValidationError as exc:
            return response.Response(
                {"detail": exc.messages[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response.Response(MyWelfareClaimSerializer(claim).data)


class WelfareReviewViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Reviewer-facing queue + decisions."""

    serializer_class = WelfareClaimReviewSerializer
    queryset = WelfareClaim.objects.select_related("claimant", "reviewed_by", "expense")
    filterset_fields = ["status", "category"]

    def get_permissions(self):
        # mark_paid is a treasury act, not a welfare-review act. A
        # treasurer is finance-write but neither leadership nor a
        # welfare officer, so the viewset-wide IsWelfareReviewer gate
        # would wrongly 403 them before the action runs. Give the
        # disbursement action its own finance-write policy (same shape
        # as ExpenseViewSet.approve in Phase 2).
        if self.action == "mark_paid":
            return [
                permissions.IsAuthenticated(),
                _IsFinanceWrite(),
            ]
        return [permissions.IsAuthenticated(), IsWelfareReviewer()]

    def _decide(self, request, fn):
        claim = self.get_object()
        body = WelfareDecisionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            fn(claim, request.user, body.validated_data["note"])
        except DjangoValidationError as exc:
            return response.Response(
                {"detail": exc.messages[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response.Response(WelfareClaimReviewSerializer(claim).data)

    @decorators.action(detail=False, methods=["get"])
    def queue(self, request):
        qs = self.get_queryset().filter(
            status__in=[
                WelfareStatus.SUBMITTED,
                WelfareStatus.UNDER_REVIEW,
            ]
        )
        page = self.paginate_queryset(qs)
        data = self.get_serializer(page if page is not None else qs, many=True).data
        if page is not None:
            return self.get_paginated_response(data)
        return response.Response(data)

    @decorators.action(detail=True, methods=["post"], url_path="start-review")
    def start_review(self, request, pk=None):
        claim = self.get_object()
        try:
            claim.start_review(request.user)
        except DjangoValidationError as exc:
            return response.Response(
                {"detail": exc.messages[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response.Response(WelfareClaimReviewSerializer(claim).data)

    @decorators.action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._decide(request, lambda c, u, n: c.approve(u, n))

    @decorators.action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._decide(request, lambda c, u, n: c.reject(u, n))

    @decorators.action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, pk=None):
        """Disburse an approved claim.

        Permission (_IsFinanceWrite, set in get_permissions) already
        guarantees the caller is treasury. This body handles the
        domain rules: claim must be approved, an active account must
        exist, and the resulting Expense links back to the claim.
        """
        claim = self.get_object()
        if claim.status != WelfareStatus.APPROVED:
            return response.Response(
                {"detail": "Only an approved claim can be paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        account = BankAccount.objects.filter(is_active=True).order_by("pk").first()
        if account is None:
            return response.Response(
                {"detail": "No active bank account to disburse from."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.finances.models import ExpenseStatus

        # The welfare claim already passed its own review + threshold
        # gate, so the resulting payout is an already-authorised
        # disbursement, not a proposed expense needing the two-person
        # rule. Creating it directly as APPROVED is intentional and
        # correct here; it still lands in the audit trail and the public
        # transparency aggregate like any other approved expense.
        expense = Expense.objects.create(
            bank_account=account,
            amount_kes=claim.amount_requested_kes,
            description=(f"Welfare payout: {claim.get_category_display()} — claim {claim.id}"),
            created_by=request.user,
            status=ExpenseStatus.APPROVED,
            approved_by=request.user,
        )
        try:
            claim.mark_paid(expense)
        except DjangoValidationError as exc:
            # Roll back the orphan expense if the claim refused.
            expense.delete()
            return response.Response(
                {"detail": exc.messages[0]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response.Response(WelfareClaimReviewSerializer(claim).data)
