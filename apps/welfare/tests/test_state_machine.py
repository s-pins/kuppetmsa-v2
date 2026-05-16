"""Welfare state-machine + threshold tests.

The threshold gate (docs/permissions.md §6) is the consequential logic:
a welfare officer may approve up to the ceiling; above it only
leadership may. Every branch is exercised, plus the Phase 4
str-vs-Decimal regression on requires_leadership_approval.
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.core.constants import (
    ROLE_CHAIRPERSON,
    ROLE_MEMBER,
    ROLE_ORGANIZING_SECRETARY,
    WELFARE_AUTO_APPROVE_THRESHOLD_KES,
)
from apps.members.models import Member
from apps.welfare.models import WelfareClaim, WelfareStatus

pytestmark = pytest.mark.django_db

UNDER = Decimal(str(WELFARE_AUTO_APPROVE_THRESHOLD_KES)) - Decimal("1")
OVER = Decimal(str(WELFARE_AUTO_APPROVE_THRESHOLD_KES)) + Decimal("1")


@pytest.fixture
def claimant():
    return Member.objects.create(tsc_number="TSC-1", first_name="Asha", last_name="Otieno")


@pytest.fixture
def make_user(django_user_model):
    n = {"i": 0}

    def _make(role=ROLE_MEMBER, *, welfare_officer=False):
        n["i"] += 1
        return django_user_model.objects.create_user(
            email=f"{role}-{n['i']}@example.com",
            password="StrongPass-12345",
            role=role,
            welfare_officer=welfare_officer,
        )

    return _make


def _claim(claimant, amount):
    return WelfareClaim.objects.create(
        claimant=claimant,
        category="illness",
        amount_requested_kes=amount,
        description="Hospital bill",
    )


class TestThresholdProperty:
    def test_at_or_below_threshold_not_leadership_only(self, claimant):
        assert _claim(claimant, UNDER).requires_leadership_approval is False

    def test_above_threshold_requires_leadership(self, claimant):
        assert _claim(claimant, OVER).requires_leadership_approval is True

    def test_handles_string_amount_on_inmemory_instance(self, claimant):
        """Phase 4 bug class: amount still a str pre-coercion must not
        TypeError in the threshold comparison."""
        c = WelfareClaim(
            claimant=claimant,
            category="illness",
            amount_requested_kes="25000.00",  # deliberately str
            description="x",
        )
        assert c.requires_leadership_approval is True


class TestReviewerGate:
    def test_non_reviewer_cannot_act(self, claimant, make_user):
        member = make_user(ROLE_MEMBER)
        claim = _claim(claimant, UNDER)
        with pytest.raises(ValidationError) as exc:
            claim.approve(member)
        assert "reviewer" in str(exc.value).lower()

    def test_welfare_officer_can_approve_below_threshold(self, claimant, make_user):
        officer = make_user(ROLE_ORGANIZING_SECRETARY, welfare_officer=True)
        claim = _claim(claimant, UNDER)
        claim.approve(officer, "approved")
        claim.refresh_from_db()
        assert claim.status == WelfareStatus.APPROVED
        assert claim.reviewed_by == officer

    def test_welfare_officer_cannot_approve_above_threshold(self, claimant, make_user):
        officer = make_user(ROLE_ORGANIZING_SECRETARY, welfare_officer=True)
        claim = _claim(claimant, OVER)
        with pytest.raises(ValidationError) as exc:
            claim.approve(officer)
        assert "leadership" in str(exc.value).lower()
        claim.refresh_from_db()
        assert claim.status == WelfareStatus.SUBMITTED  # unchanged

    def test_leadership_can_approve_above_threshold(self, claimant, make_user):
        chair = make_user(ROLE_CHAIRPERSON)
        claim = _claim(claimant, OVER)
        claim.approve(chair, "leadership approved")
        claim.refresh_from_db()
        assert claim.status == WelfareStatus.APPROVED


class TestStateMachine:
    def test_full_happy_path(self, claimant, make_user):
        chair = make_user(ROLE_CHAIRPERSON)
        claim = _claim(claimant, UNDER)
        claim.start_review(chair)
        assert claim.status == WelfareStatus.UNDER_REVIEW
        claim.approve(chair)
        assert claim.status == WelfareStatus.APPROVED

    def test_cannot_approve_already_decided(self, claimant, make_user):
        chair = make_user(ROLE_CHAIRPERSON)
        claim = _claim(claimant, UNDER)
        claim.approve(chair)
        with pytest.raises(ValidationError):
            claim.reject(chair)

    def test_claimant_can_withdraw_while_open(self, claimant):
        claim = _claim(claimant, UNDER)
        claim.withdraw(claimant)
        assert claim.status == WelfareStatus.WITHDRAWN

    def test_non_claimant_cannot_withdraw(self, claimant):
        other = Member.objects.create(tsc_number="TSC-2", first_name="B", last_name="K")
        claim = _claim(claimant, UNDER)
        with pytest.raises(ValidationError):
            claim.withdraw(other)

    def test_cannot_withdraw_after_decision(self, claimant, make_user):
        chair = make_user(ROLE_CHAIRPERSON)
        claim = _claim(claimant, UNDER)
        claim.approve(chair)
        with pytest.raises(ValidationError):
            claim.withdraw(claimant)

    def test_mark_paid_requires_approved(self, claimant):
        claim = _claim(claimant, UNDER)
        with pytest.raises(ValidationError):
            claim.mark_paid(expense=None)

    def test_amount_must_be_positive(self, claimant):
        c = WelfareClaim(
            claimant=claimant,
            category="other",
            amount_requested_kes=Decimal("0.00"),
            description="zero",
        )
        with pytest.raises(ValidationError):
            c.full_clean()
