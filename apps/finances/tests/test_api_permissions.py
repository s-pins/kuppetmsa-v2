"""Finance API tests — enforce docs/permissions.md §5.3.

One cluster per matrix row. Also covers the public transparency endpoint
(the one unauthenticated surface) and confirms audit-log entries are
written for money operations.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.core.constants import (
    ROLE_CHAIRPERSON,
    ROLE_MEMBER,
    ROLE_TREASURER,
)
from apps.finances.models import (
    BankAccount,
    Expense,
    FinancialContribution,
)
from apps.members.models import Member

pytestmark = pytest.mark.django_db


@pytest.fixture
def account():
    return BankAccount.objects.create(name="Main", paybill="123456")


@pytest.fixture
def member():
    return Member.objects.create(tsc_number="TSC-1", first_name="Asha", last_name="Otieno")


@pytest.fixture
def make_user(django_user_model):
    n = {"i": 0}

    def _make(role=ROLE_MEMBER, *, two_fa=True, recent=True):
        from django.utils import timezone

        n["i"] += 1
        u = django_user_model.objects.create_user(
            email=f"{role}-{n['i']}@example.com",
            password="StrongPass-12345",
            role=role,
            is_2fa_enrolled=two_fa,
        )
        if recent:
            u.last_strong_auth_at = timezone.now()
            u.save(update_fields=["last_strong_auth_at"])
        return u

    return _make


def _client(user=None):
    c = APIClient()
    if user:
        c.force_authenticate(user=user)
    return c


C_URL = "/api/v1/finances/contributions/"
E_URL = "/api/v1/finances/expenses/"
T_URL = "/api/v1/finances/transparency/"


class TestTransparencyIsPublic:
    """Row: 'View public transparency aggregates' — AllowAny."""

    def test_anonymous_can_read_transparency(self, account, member):
        FinancialContribution.objects.create(
            member=member,
            bank_account=account,
            amount_kes=Decimal("500.00"),
            source="mpesa_c2b",
        )
        resp = _client().get(T_URL)
        assert resp.status_code == 200
        assert resp.data["total_contributions_kes"] == "500.00"
        # No member identities leak in the aggregate.
        body = str(resp.data)
        assert "Asha" not in body
        assert "Otieno" not in body

    def test_transparency_nets_approved_expenses_only(self, account, member, make_user):
        treas = make_user(ROLE_TREASURER)
        chair = make_user(ROLE_CHAIRPERSON)
        FinancialContribution.objects.create(
            member=member,
            bank_account=account,
            amount_kes=Decimal("1000.00"),
            source="mpesa_c2b",
        )
        # One proposed (should NOT count) + one approved (should count).
        Expense.objects.create(
            bank_account=account,
            amount_kes=Decimal("200.00"),
            description="proposed",
            created_by=treas,
        )
        approved = Expense.objects.create(
            bank_account=account,
            amount_kes=Decimal("300.00"),
            description="approved",
            created_by=treas,
        )
        approved.approve(chair)

        resp = _client().get(T_URL)
        assert resp.data["total_approved_expenses_kes"] == "300.00"
        assert resp.data["net_position_kes"] == "700.00"


class TestContributionAccess:
    def test_member_cannot_view_contributions(self, account, member, make_user):
        resp = _client(make_user(ROLE_MEMBER)).get(C_URL)
        assert resp.status_code == 403

    def test_treasurer_can_view_contributions(self, account, member, make_user):
        resp = _client(make_user(ROLE_TREASURER)).get(C_URL)
        assert resp.status_code == 200

    def test_chairperson_can_view_but_is_finance_view(self, account, member, make_user):
        resp = _client(make_user(ROLE_CHAIRPERSON)).get(C_URL)
        assert resp.status_code == 200


class TestRecordContribution:
    """Row: 'Record contribution' — finance-write + 2FA + recent auth."""

    def test_treasurer_without_2fa_denied(self, account, member, make_user):
        u = make_user(ROLE_TREASURER, two_fa=False)
        resp = _client(u).post(
            C_URL,
            {
                "member": member.pk,
                "bank_account": account.pk,
                "amount_kes": "500.00",
                "source": "manual_cash",
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_treasurer_with_stale_auth_denied(self, account, member, make_user):
        u = make_user(ROLE_TREASURER, recent=False)
        resp = _client(u).post(
            C_URL,
            {
                "member": member.pk,
                "bank_account": account.pk,
                "amount_kes": "500.00",
                "source": "manual_cash",
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_treasurer_full_creds_can_record(self, account, member, make_user):
        u = make_user(ROLE_TREASURER)
        resp = _client(u).post(
            C_URL,
            {
                "member": member.pk,
                "bank_account": account.pk,
                "amount_kes": "500.00",
                "source": "manual_cash",
            },
            format="json",
        )
        assert resp.status_code == 201
        c = FinancialContribution.objects.get()
        assert c.recorded_by == u  # perform_create stamped the actor


class TestExpenseApprovalAPI:
    """Rows: create expense (finance-write), approve (leadership)."""

    def test_member_cannot_create_expense(self, account, make_user):
        resp = _client(make_user(ROLE_MEMBER)).post(
            E_URL,
            {
                "bank_account": account.pk,
                "amount_kes": "100.00",
                "description": "x",
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_large_expense_two_person_rule_via_api(self, account, make_user):
        treas = make_user(ROLE_TREASURER)
        chair = make_user(ROLE_CHAIRPERSON)

        created = _client(treas).post(
            E_URL,
            {
                "bank_account": account.pk,
                "amount_kes": "75000.00",
                "description": "big spend",
            },
            format="json",
        )
        assert created.status_code == 201
        exp_id = created.data["id"]

        # Treasurer (creator) tries to approve own large expense -> 400.
        self_approve = _client(treas).post(f"{E_URL}{exp_id}/approve/", {}, format="json")
        assert self_approve.status_code in (400, 403)

        # Chair (different leadership user) approves -> 200.
        chair_approve = _client(chair).post(
            f"{E_URL}{exp_id}/approve/",
            {"note": "approved"},
            format="json",
        )
        assert chair_approve.status_code == 200
        assert chair_approve.data["status"] == "approved"

    def test_treasurer_cannot_approve_only_leadership(self, account, make_user):
        treas = make_user(ROLE_TREASURER)
        other_treas = make_user(ROLE_TREASURER)
        created = _client(treas).post(
            E_URL,
            {
                "bank_account": account.pk,
                "amount_kes": "100.00",
                "description": "small",
            },
            format="json",
        )
        exp_id = created.data["id"]
        # Another treasurer is finance-write but NOT leadership.
        resp = _client(other_treas).post(f"{E_URL}{exp_id}/approve/", {}, format="json")
        assert resp.status_code == 403


class TestAuditTrail:
    """docs/PLAN.md: money operations must be audit-logged."""

    def test_contribution_create_writes_audit_entry(self, account, member, make_user):
        from auditlog.models import LogEntry

        u = make_user(ROLE_TREASURER)
        _client(u).post(
            C_URL,
            {
                "member": member.pk,
                "bank_account": account.pk,
                "amount_kes": "500.00",
                "source": "manual_cash",
            },
            format="json",
        )
        c = FinancialContribution.objects.get()
        entries = LogEntry.objects.get_for_object(c)
        assert entries.count() >= 1
        assert entries.first().action == LogEntry.Action.CREATE
