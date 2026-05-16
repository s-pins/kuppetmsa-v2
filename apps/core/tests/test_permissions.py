"""Tests for the core permission machinery.

These tests enforce the permissions matrix at docs/permissions.md. If you
change either the matrix or these tests, change both in the same commit.

Run: `pytest apps/core/tests/test_permissions.py`
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.core.constants import (
    DISCIPLINE_BASE_ROLES,
    FINANCE_WRITE_ROLES,
    FLAG_DISCIPLINE_COMMITTEE,
    LEADERSHIP_ROLES,
    OFFICER_ROLES,
    RECENT_AUTH_WINDOW_SECONDS,
    ROLE_CHAIRPERSON,
    ROLE_MEMBER,
    ROLE_TREASURER,
)
from apps.core.permissions import (
    HasAnyRole,
    HasFlag,
    Is2FAEnrolled,
    IsDisciplineCommittee,
    IsObjectOwner,
    IsOfficer,
    RecentAuthRequired,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def factory():
    return APIRequestFactory()


@pytest.fixture
def make_user(django_user_model):
    """Build users with arbitrary role + flag combinations."""

    counter = {"n": 0}

    def _make(role=ROLE_MEMBER, *, recent_auth=True, two_fa=False, **flags):
        counter["n"] += 1
        user = django_user_model.objects.create_user(
            email=f"{role}-{counter['n']}@example.com",
            password="supersecret-test-pass-1234",
            role=role,
            is_2fa_enrolled=two_fa,
            **flags,
        )
        if recent_auth:
            user.last_strong_auth_at = timezone.now()
            user.save(update_fields=["last_strong_auth_at"])
        return user

    return _make


class _DummyView(APIView):
    """Bare view used as the `view` parameter to permission checks."""

    pass


def _request_for(factory, user):
    req = factory.get("/test/")
    if user is not None:
        force_authenticate(req, user=user)
        # APIRequestFactory doesn't run middleware; populate request.user.
        req.user = user
    return req


# ---------------------------------------------------------------------------
# HasAnyRole
# ---------------------------------------------------------------------------


class TestHasAnyRole:
    def test_permits_user_in_allowed_set(self, factory, make_user):
        Perm = HasAnyRole(LEADERSHIP_ROLES)
        user = make_user(role=ROLE_CHAIRPERSON)
        assert Perm().has_permission(_request_for(factory, user), _DummyView())

    def test_denies_user_outside_allowed_set(self, factory, make_user):
        Perm = HasAnyRole(LEADERSHIP_ROLES)
        user = make_user(role=ROLE_MEMBER)
        assert not Perm().has_permission(_request_for(factory, user), _DummyView())

    def test_denies_anonymous(self, factory):
        Perm = HasAnyRole(LEADERSHIP_ROLES)
        req = factory.get("/")
        req.user = type("AnonUser", (), {"is_authenticated": False})()
        assert not Perm().has_permission(req, _DummyView())

    def test_treasurer_excluded_from_leadership(self, factory, make_user):
        Perm = HasAnyRole(LEADERSHIP_ROLES)
        user = make_user(role=ROLE_TREASURER)
        assert not Perm().has_permission(_request_for(factory, user), _DummyView())

    def test_treasurer_included_in_finance_write(self, factory, make_user):
        Perm = HasAnyRole(FINANCE_WRITE_ROLES)
        user = make_user(role=ROLE_TREASURER)
        assert Perm().has_permission(_request_for(factory, user), _DummyView())


# ---------------------------------------------------------------------------
# HasFlag
# ---------------------------------------------------------------------------


class TestHasFlag:
    def test_permits_user_with_flag(self, factory, make_user):
        Perm = HasFlag(FLAG_DISCIPLINE_COMMITTEE)
        user = make_user(role=ROLE_MEMBER, discipline_committee_member=True)
        assert Perm().has_permission(_request_for(factory, user), _DummyView())

    def test_denies_user_without_flag(self, factory, make_user):
        Perm = HasFlag(FLAG_DISCIPLINE_COMMITTEE)
        user = make_user(role=ROLE_MEMBER)
        assert not Perm().has_permission(_request_for(factory, user), _DummyView())


# ---------------------------------------------------------------------------
# Is2FAEnrolled
# ---------------------------------------------------------------------------


class TestIs2FAEnrolled:
    def test_permits_enrolled(self, factory, make_user):
        user = make_user(role=ROLE_TREASURER, two_fa=True)
        assert Is2FAEnrolled().has_permission(_request_for(factory, user), _DummyView())

    def test_denies_not_enrolled(self, factory, make_user):
        user = make_user(role=ROLE_TREASURER, two_fa=False)
        assert not Is2FAEnrolled().has_permission(_request_for(factory, user), _DummyView())


# ---------------------------------------------------------------------------
# RecentAuthRequired
# ---------------------------------------------------------------------------


class TestRecentAuthRequired:
    def test_permits_within_window(self, factory, make_user):
        user = make_user(role=ROLE_CHAIRPERSON, recent_auth=True)
        assert RecentAuthRequired().has_permission(_request_for(factory, user), _DummyView())

    def test_denies_outside_window(self, factory, make_user):
        user = make_user(role=ROLE_CHAIRPERSON, recent_auth=False)
        # Set last_strong_auth_at to *just* outside the window.
        user.last_strong_auth_at = timezone.now() - timedelta(
            seconds=RECENT_AUTH_WINDOW_SECONDS + 60
        )
        user.save(update_fields=["last_strong_auth_at"])
        assert not RecentAuthRequired().has_permission(_request_for(factory, user), _DummyView())

    def test_denies_never_authed(self, factory, make_user):
        user = make_user(role=ROLE_CHAIRPERSON, recent_auth=False)
        user.last_strong_auth_at = None
        user.save(update_fields=["last_strong_auth_at"])
        assert not RecentAuthRequired().has_permission(_request_for(factory, user), _DummyView())


# ---------------------------------------------------------------------------
# IsDisciplineCommittee — the composite check that gates the whole module
# ---------------------------------------------------------------------------


class TestIsDisciplineCommittee:
    def test_chairperson_with_2fa_and_recent_auth_allowed(self, factory, make_user):
        user = make_user(role=ROLE_CHAIRPERSON, two_fa=True, recent_auth=True)
        assert IsDisciplineCommittee().has_permission(_request_for(factory, user), _DummyView())

    def test_member_with_flag_and_2fa_allowed(self, factory, make_user):
        user = make_user(
            role=ROLE_MEMBER,
            discipline_committee_member=True,
            two_fa=True,
            recent_auth=True,
        )
        assert IsDisciplineCommittee().has_permission(_request_for(factory, user), _DummyView())

    def test_chairperson_without_2fa_denied(self, factory, make_user):
        user = make_user(role=ROLE_CHAIRPERSON, two_fa=False, recent_auth=True)
        assert not IsDisciplineCommittee().has_permission(_request_for(factory, user), _DummyView())

    def test_treasurer_denied_even_with_2fa(self, factory, make_user):
        """Treasurer is in finance roles but explicitly NOT in DISCIPLINE_BASE_ROLES."""
        user = make_user(role=ROLE_TREASURER, two_fa=True, recent_auth=True)
        assert ROLE_TREASURER not in DISCIPLINE_BASE_ROLES  # safety net
        assert not IsDisciplineCommittee().has_permission(_request_for(factory, user), _DummyView())

    def test_stale_auth_denied_even_with_role(self, factory, make_user):
        user = make_user(role=ROLE_CHAIRPERSON, two_fa=True, recent_auth=False)
        user.last_strong_auth_at = timezone.now() - timedelta(
            seconds=RECENT_AUTH_WINDOW_SECONDS + 60
        )
        user.save(update_fields=["last_strong_auth_at"])
        assert not IsDisciplineCommittee().has_permission(_request_for(factory, user), _DummyView())


# ---------------------------------------------------------------------------
# IsOfficer — gates Swagger UI
# ---------------------------------------------------------------------------


class TestIsOfficer:
    def test_chairperson_is_officer(self, factory, make_user):
        user = make_user(role=ROLE_CHAIRPERSON)
        assert IsOfficer().has_permission(_request_for(factory, user), _DummyView())

    def test_treasurer_is_officer(self, factory, make_user):
        user = make_user(role=ROLE_TREASURER)
        assert IsOfficer().has_permission(_request_for(factory, user), _DummyView())

    def test_member_is_not_officer(self, factory, make_user):
        user = make_user(role=ROLE_MEMBER)
        assert not IsOfficer().has_permission(_request_for(factory, user), _DummyView())

    def test_all_constitutional_roles_are_officers(self, factory, make_user):
        """Sanity check: every role in OFFICER_ROLES is admitted."""
        for role in OFFICER_ROLES:
            user = make_user(role=role)
            assert IsOfficer().has_permission(_request_for(factory, user), _DummyView()), (
                f"Role {role} unexpectedly rejected"
            )


# ---------------------------------------------------------------------------
# IsObjectOwner
# ---------------------------------------------------------------------------


class TestIsObjectOwner:
    def test_owner_attr_dotted_traversal(self, factory, make_user):
        owner = make_user(role=ROLE_MEMBER)
        other = make_user(role=ROLE_MEMBER)

        class Wrapper:
            class _Holder:
                pass

            user = None

        obj = Wrapper()
        obj.user = owner

        perm = IsObjectOwner()
        assert perm.has_object_permission(_request_for(factory, owner), _DummyView(), obj)
        assert not perm.has_object_permission(_request_for(factory, other), _DummyView(), obj)
