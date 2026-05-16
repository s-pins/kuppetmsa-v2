"""Project API + budget-vs-actual tests.

Covers docs/permissions.md §5.5 and the docs/erd.md §2 cross-link:
APPROVED expenses tagged to a project reduce its variance; proposed /
rejected ones do not.
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
from apps.projects.models import Project

pytestmark = pytest.mark.django_db


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


@pytest.fixture
def project():
    return Project.objects.create(name="Borehole", slug="borehole", budget_kes=Decimal("100000.00"))


P_URL = "/api/v1/projects/"


class TestProjectPermissions:
    def test_anonymous_can_list_public_projects(self, project):
        resp = APIClient().get(P_URL)
        assert resp.status_code == 200
        assert resp.data["count"] == 1

    def test_anonymous_cannot_see_non_public(self, project):
        project.is_public = False
        project.save()
        resp = APIClient().get(P_URL)
        assert resp.data["count"] == 0

    def test_member_cannot_create(self, make_user):
        c = APIClient()
        c.force_authenticate(make_user(ROLE_MEMBER))
        resp = c.post(
            P_URL,
            {"name": "X", "slug": "x", "budget_kes": "1000"},
            format="json",
        )
        assert resp.status_code == 403

    def test_organizing_secretary_cannot_create_not_leadership(self, make_user):
        c = APIClient()
        c.force_authenticate(make_user(ROLE_ORGANIZING_SECRETARY))
        resp = c.post(
            P_URL,
            {"name": "X", "slug": "x", "budget_kes": "1000"},
            format="json",
        )
        assert resp.status_code == 403

    def test_chairperson_can_create(self, make_user):
        c = APIClient()
        c.force_authenticate(make_user(ROLE_CHAIRPERSON))
        resp = c.post(
            P_URL,
            {"name": "Hall", "slug": "hall", "budget_kes": "50000"},
            format="json",
        )
        assert resp.status_code == 201


class TestBudgetVsActual:
    def test_only_approved_expenses_count_against_budget(self, project, make_user):
        account = BankAccount.objects.create(name="Main", paybill="600100")
        treas = make_user(ROLE_TREASURER)
        chair = make_user(ROLE_CHAIRPERSON)

        # Proposed — must NOT count.
        Expense.objects.create(
            bank_account=account,
            project=project,
            amount_kes=Decimal("30000.00"),
            description="proposed",
            created_by=treas,
        )
        # Approved — must count.
        approved = Expense.objects.create(
            bank_account=account,
            project=project,
            amount_kes=Decimal("40000.00"),
            description="approved",
            created_by=treas,
        )
        approved.approve(chair)

        project.refresh_from_db()
        assert project.spent_kes == Decimal("40000.00")
        assert project.variance_kes == Decimal("60000.00")

    def test_public_project_detail_exposes_budget_transparency(self, project, make_user):
        account = BankAccount.objects.create(name="Main", paybill="600100")
        treas = make_user(ROLE_TREASURER)
        chair = make_user(ROLE_CHAIRPERSON)
        e = Expense.objects.create(
            bank_account=account,
            project=project,
            amount_kes=Decimal("25000.00"),
            description="spent",
            created_by=treas,
        )
        e.approve(chair)

        resp = APIClient().get(f"{P_URL}{project.slug}/")
        assert resp.status_code == 200
        assert resp.data["spent_kes"] == "25000.00"
        assert resp.data["variance_kes"] == "75000.00"

    def test_deleting_project_preserves_expense_history(self, project, make_user):
        account = BankAccount.objects.create(name="Main", paybill="600100")
        treas = make_user(ROLE_TREASURER)
        e = Expense.objects.create(
            bank_account=account,
            project=project,
            amount_kes=Decimal("5000.00"),
            description="spent",
            created_by=treas,
        )
        project.delete()
        e.refresh_from_db()
        # SET_NULL: expense survives, project link cleared.
        assert e.project is None
        assert Expense.objects.filter(pk=e.pk).exists()

    def test_variance_handles_string_budget_on_unsaved_instance(self):
        """Regression: an unsaved Project whose budget_kes is still a str
        must not blow up variance_kes with a str-Decimal TypeError.
        Caught by the Phase 4 live demo (sibling of the
        Expense.is_large string-amount bug). Unit fixtures always used
        Decimal literals, so only the shell / raw-assignment path
        exposed it.
        """
        p = Project(name="X", slug="x-unsaved", budget_kes="500000.00")
        # Unsaved -> no related expenses -> spent is 0.
        assert p.variance_kes == Decimal("500000.00")
