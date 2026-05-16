"""Member portal tests.

The headline tests are the isolation ones: member A must never see
member B's contributions, events, or dashboard figures through ANY
portal endpoint. That invariant is the entire security rationale for
the PortalScopedMixin, so it gets exhaustive coverage.
"""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.constants import ROLE_CHAIRPERSON, ROLE_MEMBER
from apps.events.models import Event, EventAttendance
from apps.finances.models import BankAccount, FinancialContribution
from apps.members.models import Member

pytestmark = pytest.mark.django_db


@pytest.fixture
def account():
    return BankAccount.objects.create(name="Main", paybill="600100")


@pytest.fixture
def make_member(django_user_model):
    n = {"i": 0}

    def _make(role=ROLE_MEMBER, *, with_profile=True):
        n["i"] += 1
        user = django_user_model.objects.create_user(
            email=f"u{n['i']}@example.com",
            password="StrongPass-12345",
            role=role,
        )
        member = None
        if with_profile:
            member = Member.objects.create(
                tsc_number=f"TSC-{n['i']}",
                first_name=f"First{n['i']}",
                last_name="Member",
                user=user,
            )
        return user, member

    return _make


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


DASH = "/api/v1/portal/dashboard/"
MYC = "/api/v1/portal/my-contributions/"
MYE = "/api/v1/portal/my-events/"


class TestPortalAccess:
    def test_anonymous_denied_everywhere(self):
        c = APIClient()
        assert c.get(DASH).status_code == 401
        assert c.get(MYC).status_code == 401
        assert c.get(MYE).status_code == 401

    def test_account_without_member_profile_denied(self, make_member):
        # An officer-only account with no linked Member.
        user, _ = make_member(ROLE_CHAIRPERSON, with_profile=False)
        resp = _client(user).get(DASH)
        assert resp.status_code == 403

    def test_member_with_profile_allowed(self, make_member):
        user, _ = make_member()
        assert _client(user).get(DASH).status_code == 200


class TestDashboardComposition:
    def test_dashboard_aggregates_own_data(self, make_member, account):
        user, member = make_member()
        FinancialContribution.objects.create(
            member=member,
            bank_account=account,
            amount_kes=Decimal("500.00"),
            source="mpesa_c2b",
        )
        FinancialContribution.objects.create(
            member=member,
            bank_account=account,
            amount_kes=Decimal("750.00"),
            source="manual_cash",
        )
        ev = Event.objects.create(
            title="Future AGM",
            slug="future-agm",
            starts_at=timezone.now() + timezone.timedelta(days=30),
        )
        EventAttendance.objects.create(event=ev, member=member, rsvp=True, rsvp_at=timezone.now())

        data = _client(user).get(DASH).data
        assert data["membership_id"] == member.membership_id
        assert data["total_contributed_kes"] == "1250.00"
        assert data["contribution_count"] == 2
        assert data["upcoming_rsvp_count"] == 1
        assert data["last_contribution_at"] is not None

    def test_past_rsvp_not_counted_as_upcoming(self, make_member, account):
        user, member = make_member()
        past = Event.objects.create(
            title="Old AGM",
            slug="old-agm",
            starts_at=timezone.now() - timezone.timedelta(days=10),
        )
        EventAttendance.objects.create(event=past, member=member, rsvp=True, rsvp_at=timezone.now())
        data = _client(user).get(DASH).data
        assert data["upcoming_rsvp_count"] == 0


class TestCrossMemberIsolation:
    """The security invariant of Phase 5: no member sees another's data."""

    def test_my_contributions_excludes_other_members(self, make_member, account):
        user_a, member_a = make_member()
        _user_b, member_b = make_member()

        FinancialContribution.objects.create(
            member=member_a,
            bank_account=account,
            amount_kes=Decimal("100.00"),
            source="mpesa_c2b",
        )
        FinancialContribution.objects.create(
            member=member_b,
            bank_account=account,
            amount_kes=Decimal("9999.00"),
            source="mpesa_c2b",
        )

        resp = _client(user_a).get(MYC)
        assert resp.status_code == 200
        amounts = [r["amount_kes"] for r in resp.data["results"]]
        assert amounts == ["100.00"]
        assert "9999.00" not in amounts

    def test_dashboard_total_isolated_per_member(self, make_member, account):
        user_a, member_a = make_member()
        _user_b, member_b = make_member()
        FinancialContribution.objects.create(
            member=member_a,
            bank_account=account,
            amount_kes=Decimal("100.00"),
            source="mpesa_c2b",
        )
        FinancialContribution.objects.create(
            member=member_b,
            bank_account=account,
            amount_kes=Decimal("5000.00"),
            source="mpesa_c2b",
        )
        data = _client(user_a).get(DASH).data
        # A's dashboard must reflect only A's 100, never B's 5000.
        assert data["total_contributed_kes"] == "100.00"
        assert data["contribution_count"] == 1

    def test_my_events_excludes_other_members(self, make_member):
        user_a, member_a = make_member()
        _user_b, member_b = make_member()
        ev = Event.objects.create(title="AGM", slug="agm")
        EventAttendance.objects.create(event=ev, member=member_a, rsvp=True)
        EventAttendance.objects.create(event=ev, member=member_b, rsvp=True)
        resp = _client(user_a).get(MYE)
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1
        # The single row is A's attendance, not B's.
        assert resp.data["results"][0]["event_slug"] == "agm"

    def test_empty_state_is_clean_not_error(self, make_member):
        """A brand-new member with no activity gets zeros, not a 500."""
        user, _ = make_member()
        data = _client(user).get(DASH).data
        assert data["total_contributed_kes"] == "0.00"
        assert data["contribution_count"] == 0
        assert data["upcoming_rsvp_count"] == 0
        assert data["last_contribution_at"] is None
        assert _client(user).get(MYC).data["results"] == []
        assert _client(user).get(MYE).data["results"] == []
