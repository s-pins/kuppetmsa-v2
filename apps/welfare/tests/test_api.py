"""Welfare API tests — docs/permissions.md §5.7.

Covers member submit/isolation, reviewer queue/decisions, the
finance-write gate on disbursement, and the finances integration
(mark-paid creates a linked, audited Expense that shows in transparency).
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.core.constants import (
    ROLE_CHAIRPERSON,
    ROLE_MEMBER,
    ROLE_ORGANIZING_SECRETARY,
    ROLE_TREASURER,
)
from apps.finances.models import BankAccount, Expense
from apps.members.models import Member
from apps.welfare.models import WelfareClaim, WelfareStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def account():
    return BankAccount.objects.create(name="Main", paybill="600100")


@pytest.fixture
def make_member(django_user_model):
    n = {"i": 0}

    def _make(role=ROLE_MEMBER, *, profile=True, welfare_officer=False):
        n["i"] += 1
        u = django_user_model.objects.create_user(
            email=f"u{n['i']}@example.com",
            password="StrongPass-12345",
            role=role,
            welfare_officer=welfare_officer,
        )
        m = None
        if profile:
            m = Member.objects.create(
                tsc_number=f"TSC-{n['i']}",
                first_name=f"F{n['i']}",
                last_name="M",
                user=u,
            )
        return u, m

    return _make


def _client(u):
    c = APIClient()
    c.force_authenticate(u)
    return c


CLAIMS = "/api/v1/welfare/claims/"
REVIEW = "/api/v1/welfare/review/"


class TestMemberClaims:
    def test_member_submits_claim(self, make_member):
        user, member = make_member()
        resp = _client(user).post(
            CLAIMS,
            {
                "category": "illness",
                "amount_requested_kes": "5000.00",
                "description": "Hospital",
            },
            format="json",
        )
        assert resp.status_code == 201
        claim = WelfareClaim.objects.get()
        assert claim.claimant == member
        assert claim.status == WelfareStatus.SUBMITTED

    def test_account_without_profile_denied(self, make_member):
        user, _ = make_member(ROLE_CHAIRPERSON, profile=False)
        resp = _client(user).get(CLAIMS)
        assert resp.status_code == 403

    def test_member_sees_only_own_claims(self, make_member):
        ua, ma = make_member()
        _ub, mb = make_member()
        WelfareClaim.objects.create(
            claimant=ma,
            category="illness",
            amount_requested_kes=Decimal("100.00"),
            description="mine",
        )
        WelfareClaim.objects.create(
            claimant=mb,
            category="illness",
            amount_requested_kes=Decimal("9999.00"),
            description="not mine",
        )
        resp = _client(ua).get(CLAIMS)
        assert resp.status_code == 200
        amounts = [r["amount_requested_kes"] for r in resp.data["results"]]
        assert amounts == ["100.00"]

    def test_member_withdraws_own_claim(self, make_member):
        user, member = make_member()
        claim = WelfareClaim.objects.create(
            claimant=member,
            category="other",
            amount_requested_kes=Decimal("200.00"),
            description="x",
        )
        resp = _client(user).post(f"{CLAIMS}{claim.id}/withdraw/", {}, format="json")
        assert resp.status_code == 200
        claim.refresh_from_db()
        assert claim.status == WelfareStatus.WITHDRAWN


class TestReviewerQueue:
    def test_plain_member_cannot_access_review(self, make_member):
        user, _ = make_member()
        assert _client(user).get(f"{REVIEW}queue/").status_code == 403

    def test_welfare_officer_sees_queue(self, make_member):
        _ua, ma = make_member()
        WelfareClaim.objects.create(
            claimant=ma,
            category="illness",
            amount_requested_kes=Decimal("100.00"),
            description="x",
        )
        officer_u, _ = make_member(ROLE_ORGANIZING_SECRETARY, profile=False, welfare_officer=True)
        resp = _client(officer_u).get(f"{REVIEW}queue/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        assert len(results) == 1

    def test_welfare_officer_blocked_above_threshold_via_api(self, make_member):
        _ua, ma = make_member()
        big = WelfareClaim.objects.create(
            claimant=ma,
            category="illness",
            amount_requested_kes=Decimal("25000.00"),
            description="big",
        )
        officer_u, _ = make_member(ROLE_ORGANIZING_SECRETARY, profile=False, welfare_officer=True)
        resp = _client(officer_u).post(f"{REVIEW}{big.id}/approve/", {}, format="json")
        assert resp.status_code == 400
        assert "leadership" in resp.data["detail"].lower()

    def test_leadership_approves_above_threshold_via_api(self, make_member):
        _ua, ma = make_member()
        big = WelfareClaim.objects.create(
            claimant=ma,
            category="illness",
            amount_requested_kes=Decimal("25000.00"),
            description="big",
        )
        chair_u, _ = make_member(ROLE_CHAIRPERSON, profile=False)
        resp = _client(chair_u).post(
            f"{REVIEW}{big.id}/approve/",
            {"note": "approved"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["status"] == "approved"


class TestDisbursementIntegration:
    def test_mark_paid_requires_finance_write(self, make_member):
        _ua, ma = make_member()
        claim = WelfareClaim.objects.create(
            claimant=ma,
            category="illness",
            amount_requested_kes=Decimal("3000.00"),
            description="x",
            status=WelfareStatus.APPROVED,
        )
        # Chairperson is leadership but NOT finance-write.
        chair_u, _ = make_member(ROLE_CHAIRPERSON, profile=False)
        resp = _client(chair_u).post(f"{REVIEW}{claim.id}/mark-paid/", {}, format="json")
        assert resp.status_code == 403

    def test_treasurer_disburses_creating_linked_expense(self, account, make_member):
        _ua, ma = make_member()
        claim = WelfareClaim.objects.create(
            claimant=ma,
            category="bereavement",
            amount_requested_kes=Decimal("8000.00"),
            description="funeral",
            status=WelfareStatus.APPROVED,
        )
        treas_u, _ = make_member(ROLE_TREASURER, profile=False)
        resp = _client(treas_u).post(f"{REVIEW}{claim.id}/mark-paid/", {}, format="json")
        assert resp.status_code == 200
        claim.refresh_from_db()
        assert claim.status == WelfareStatus.PAID
        assert claim.expense is not None
        # The expense is APPROVED so it flows into transparency.
        exp = Expense.objects.get(pk=claim.expense_id)
        assert exp.amount_kes == Decimal("8000.00")
        assert exp.status == "approved"

    def test_cannot_pay_unapproved_claim(self, account, make_member):
        _ua, ma = make_member()
        claim = WelfareClaim.objects.create(
            claimant=ma,
            category="other",
            amount_requested_kes=Decimal("1000.00"),
            description="x",
        )  # status submitted, not approved
        treas_u, _ = make_member(ROLE_TREASURER, profile=False)
        resp = _client(treas_u).post(f"{REVIEW}{claim.id}/mark-paid/", {}, format="json")
        assert resp.status_code == 400
        assert Expense.objects.count() == 0  # no orphan expense
