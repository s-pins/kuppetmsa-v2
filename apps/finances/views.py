"""Finance API.

Enforces docs/permissions.md §5.3:

  - transparency aggregate            : public (AllowAny)
  - view contributions/expenses       : finance-view roles
  - record contribution / create expense : finance-write + 2FA + recent auth
  - approve/reject expense            : leadership (+ two-person rule in model)

The two-person rule itself lives in Expense.approve()/reject(); the view
just surfaces the ValidationError it raises as a 400.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework import decorators, permissions, response, status, viewsets
from rest_framework.views import APIView

from apps.core.constants import (
    FINANCE_VIEW_ROLES,
    FINANCE_WRITE_ROLES,
    LEADERSHIP_ROLES,
)
from apps.core.permissions import (
    HasAnyRole,
    Is2FAEnrolled,
    RecentAuthRequired,
)
from apps.finances.models import (
    BankAccount,
    Expense,
    ExpenseStatus,
    FinancialContribution,
)
from apps.finances.serializers import (
    BankAccountSerializer,
    ContributionSerializer,
    ExpenseDecisionSerializer,
    ExpenseSerializer,
    TransparencySerializer,
)


class _FinanceViewMixin:
    """Shared permission policy.

    Read = finance-view roles. Write = finance-write roles AND 2FA AND
    recent auth (matrix §5.3 — recording money is a sensitive op).
    """

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [
                permissions.IsAuthenticated(),
                HasAnyRole(FINANCE_VIEW_ROLES)(),
            ]
        if self.action in ("approve", "reject"):
            # Decisions are a leadership act, not a finance-write act.
            # Chairperson/exec-sec are leadership but not finance-write,
            # and must be able to approve. 2FA + recent auth still apply
            # because this moves money.
            return [
                permissions.IsAuthenticated(),
                HasAnyRole(LEADERSHIP_ROLES)(),
                Is2FAEnrolled(),
                RecentAuthRequired(),
            ]
        # create / update / destroy: finance-write + 2FA + recent auth.
        return [
            permissions.IsAuthenticated(),
            HasAnyRole(FINANCE_WRITE_ROLES)(),
            Is2FAEnrolled(),
            RecentAuthRequired(),
        ]


class BankAccountViewSet(_FinanceViewMixin, viewsets.ModelViewSet):
    queryset = BankAccount.objects.all()
    serializer_class = BankAccountSerializer


class ContributionViewSet(_FinanceViewMixin, viewsets.ModelViewSet):
    queryset = FinancialContribution.objects.select_related("member", "bank_account")
    serializer_class = ContributionSerializer
    filterset_fields = ["reconciled", "source", "bank_account"]

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


class ExpenseViewSet(_FinanceViewMixin, viewsets.ModelViewSet):
    queryset = Expense.objects.select_related("bank_account", "created_by", "approved_by")
    serializer_class = ExpenseSerializer
    filterset_fields = ["status", "bank_account"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def _decide(self, request, decide_fn):
        expense = self.get_object()
        body = ExpenseDecisionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            decide_fn(expense, request.user, body.validated_data["note"])
        except DjangoValidationError as exc:
            return response.Response(
                {"detail": exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response.Response(ExpenseSerializer(expense).data)

    @decorators.action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        # Approve requires leadership, not just finance-write — and the
        # model enforces the two-person rule on large expenses.
        if request.user.role not in LEADERSHIP_ROLES:
            return response.Response(
                {"detail": "Only leadership may approve expenses."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return self._decide(request, lambda e, u, n: e.approve(u, n))

    @decorators.action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        if request.user.role not in LEADERSHIP_ROLES:
            return response.Response(
                {"detail": "Only leadership may reject expenses."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return self._decide(request, lambda e, u, n: e.reject(u, n))


class TransparencyView(APIView):
    """Public aggregate snapshot. AllowAny — aggregates only, no PII."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        contrib_total = FinancialContribution.objects.aggregate(s=Sum("amount_kes"))[
            "s"
        ] or Decimal("0.00")

        approved_total = Expense.objects.filter(status=ExpenseStatus.APPROVED).aggregate(
            s=Sum("amount_kes")
        )["s"] or Decimal("0.00")

        by_source_qs = (
            FinancialContribution.objects.values("source")
            .annotate(total=Sum("amount_kes"))
            .order_by()
        )
        by_source = {row["source"]: row["total"] for row in by_source_qs}

        monthly_qs = (
            FinancialContribution.objects.annotate(month=TruncMonth("paid_at"))
            .values("month")
            .annotate(total=Sum("amount_kes"))
            .order_by("month")
        )
        monthly = [
            {
                "month": row["month"].strftime("%Y-%m"),
                "total": str(row["total"]),
            }
            for row in monthly_qs
            if row["month"] is not None
        ]

        payload = {
            "total_contributions_kes": contrib_total,
            "total_approved_expenses_kes": approved_total,
            "net_position_kes": contrib_total - approved_total,
            "contributions_by_source": by_source,
            "monthly_contributions": monthly,
            "generated_at": timezone.now(),
        }
        return response.Response(TransparencySerializer(payload).data)
