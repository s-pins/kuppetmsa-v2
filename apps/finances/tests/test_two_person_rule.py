"""Expense state-machine and two-person-rule tests.

This is the most consequential logic in the system: it is what stops one
officer from unilaterally moving large sums. Every branch of
docs/permissions.md §6.1 is exercised here.
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.core.constants import (
    LARGE_EXPENSE_THRESHOLD_KES,
    ROLE_CHAIRPERSON,
    ROLE_EXECUTIVE_SECRETARY,
    ROLE_MEMBER,
    ROLE_TREASURER,
)
from apps.finances.models import (
    BankAccount,
    Expense,
    ExpenseStatus,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def account():
    return BankAccount.objects.create(name="Main", paybill="123456")


@pytest.fixture
def make_user(django_user_model):
    n = {"i": 0}

    def _make(role=ROLE_MEMBER):
        n["i"] += 1
        return django_user_model.objects.create_user(
            email=f"{role}-{n['i']}@example.com",
            password="StrongPass-12345",
            role=role,
        )

    return _make


SMALL = Decimal(str(LARGE_EXPENSE_THRESHOLD_KES)) - Decimal("1")
LARGE = Decimal(str(LARGE_EXPENSE_THRESHOLD_KES)) + Decimal("1")


def _expense(account, creator, amount):
    return Expense.objects.create(
        bank_account=account,
        amount_kes=amount,
        description="Test expense",
        created_by=creator,
    )


class TestSmallExpense:
    """At or below threshold: a single leadership user may approve."""

    def test_creator_can_approve_small_expense(self, account, make_user):
        chair = make_user(ROLE_CHAIRPERSON)
        exp = _expense(account, chair, SMALL)
        assert not exp.is_large
        exp.approve(chair, "ok")
        exp.refresh_from_db()
        assert exp.status == ExpenseStatus.APPROVED
        assert exp.approved_by == chair

    def test_treasurer_creates_chair_approves_small(self, account, make_user):
        treas = make_user(ROLE_TREASURER)
        chair = make_user(ROLE_CHAIRPERSON)
        exp = _expense(account, treas, SMALL)
        exp.approve(chair)
        exp.refresh_from_db()
        assert exp.status == ExpenseStatus.APPROVED


class TestLargeExpenseTwoPersonRule:
    """Above threshold: decider must differ from creator."""

    def test_creator_cannot_approve_own_large_expense(self, account, make_user):
        chair = make_user(ROLE_CHAIRPERSON)
        exp = _expense(account, chair, LARGE)
        assert exp.is_large
        with pytest.raises(ValidationError) as exc:
            exp.approve(chair)
        assert "second leadership signatory" in str(exc.value)
        exp.refresh_from_db()
        assert exp.status == ExpenseStatus.PROPOSED  # unchanged

    def test_chair_who_is_also_treasurer_is_still_blocked(self, account, make_user):
        """The exact edge case from §6.1: one person, both hats.

        Creating as treasurer-minded and approving as chair-minded is the
        same DB user, so the rule must still block them.
        """
        dual = make_user(ROLE_CHAIRPERSON)  # also acts as treasurer
        exp = _expense(account, dual, LARGE)
        with pytest.raises(ValidationError):
            exp.approve(dual)

    def test_second_leadership_user_can_approve_large(self, account, make_user):
        treas = make_user(ROLE_TREASURER)
        chair = make_user(ROLE_CHAIRPERSON)
        exp = _expense(account, treas, LARGE)
        exp.approve(chair, "reviewed and approved")
        exp.refresh_from_db()
        assert exp.status == ExpenseStatus.APPROVED
        assert exp.approved_by == chair

    def test_second_signatory_can_also_reject_large(self, account, make_user):
        treas = make_user(ROLE_TREASURER)
        exsec = make_user(ROLE_EXECUTIVE_SECRETARY)
        exp = _expense(account, treas, LARGE)
        exp.reject(exsec, "insufficient documentation")
        exp.refresh_from_db()
        assert exp.status == ExpenseStatus.REJECTED


class TestExpenseStateMachine:
    def test_non_leadership_cannot_decide(self, account, make_user):
        treas = make_user(ROLE_TREASURER)
        member = make_user(ROLE_MEMBER)
        exp = _expense(account, treas, SMALL)
        with pytest.raises(ValidationError) as exc:
            exp.approve(member)
        assert "leadership" in str(exc.value).lower()

    def test_cannot_decide_twice(self, account, make_user):
        treas = make_user(ROLE_TREASURER)
        chair = make_user(ROLE_CHAIRPERSON)
        exp = _expense(account, treas, SMALL)
        exp.approve(chair)
        with pytest.raises(ValidationError) as exc:
            exp.reject(chair)
        assert "already" in str(exc.value).lower()

    def test_amount_must_be_positive(self, account, make_user):
        treas = make_user(ROLE_TREASURER)
        exp = Expense(
            bank_account=account,
            amount_kes=Decimal("0.00"),
            description="zero",
            created_by=treas,
        )
        with pytest.raises(ValidationError):
            exp.full_clean()
