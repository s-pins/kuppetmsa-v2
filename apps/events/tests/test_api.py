"""Event API tests — docs/permissions.md §5.4."""

import pytest
from rest_framework.test import APIClient

from apps.core.constants import (
    ROLE_MEMBER,
    ROLE_ORGANIZING_SECRETARY,
    ROLE_TREASURER,
)
from apps.events.models import Event, EventAttendance
from apps.members.models import Member

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
def event():
    return Event.objects.create(title="AGM 2026", slug="agm-2026")


@pytest.fixture
def member_with_user(make_user):
    user = make_user(ROLE_MEMBER)
    m = Member.objects.create(tsc_number="TSC-1", first_name="Asha", last_name="Otieno", user=user)
    return m, user


E_URL = "/api/v1/events/"


class TestEventPermissions:
    def test_anonymous_lists_public_events(self, event):
        assert APIClient().get(E_URL).status_code == 200

    def test_member_cannot_create_event(self, make_user):
        c = APIClient()
        c.force_authenticate(make_user(ROLE_MEMBER))
        resp = c.post(E_URL, {"title": "X", "slug": "x"}, format="json")
        assert resp.status_code == 403

    def test_treasurer_cannot_create_not_organizer(self, make_user):
        c = APIClient()
        c.force_authenticate(make_user(ROLE_TREASURER))
        resp = c.post(E_URL, {"title": "X", "slug": "x"}, format="json")
        assert resp.status_code == 403

    def test_organizing_secretary_can_create(self, make_user):
        c = APIClient()
        c.force_authenticate(make_user(ROLE_ORGANIZING_SECRETARY))
        resp = c.post(
            E_URL,
            {"title": "Training", "slug": "training", "event_type": "training"},
            format="json",
        )
        assert resp.status_code == 201


class TestRsvp:
    def test_member_can_rsvp_and_cancel(self, event, member_with_user):
        member, user = member_with_user
        c = APIClient()
        c.force_authenticate(user)

        r = c.post(f"{E_URL}{event.slug}/rsvp/", {}, format="json")
        assert r.status_code == 200
        assert r.data["rsvp"] is True
        event.refresh_from_db()
        assert event.rsvp_count == 1

        cancel = c.post(f"{E_URL}{event.slug}/cancel-rsvp/", {}, format="json")
        assert cancel.status_code == 200
        assert EventAttendance.objects.get(event=event, member=member).rsvp is False

    def test_rsvp_requires_member_profile(self, event, make_user):
        c = APIClient()
        c.force_authenticate(make_user(ROLE_MEMBER))  # no Member linked
        resp = c.post(f"{E_URL}{event.slug}/rsvp/", {}, format="json")
        assert resp.status_code == 400

    def test_anonymous_cannot_rsvp(self, event):
        resp = APIClient().post(f"{E_URL}{event.slug}/rsvp/", {}, format="json")
        assert resp.status_code == 401


class TestAttendanceMarking:
    def test_organizer_marks_attendance(self, event, member_with_user, make_user):
        member, _ = member_with_user
        organizer = make_user(ROLE_ORGANIZING_SECRETARY)
        c = APIClient()
        c.force_authenticate(organizer)
        resp = c.post(
            f"{E_URL}{event.slug}/mark-attendance/",
            {"member": member.pk, "attended": True},
            format="json",
        )
        assert resp.status_code == 200
        rec = EventAttendance.objects.get(event=event, member=member)
        assert rec.attended is True
        assert rec.marked_by == organizer

    def test_member_cannot_mark_attendance(self, event, member_with_user):
        member, user = member_with_user
        c = APIClient()
        c.force_authenticate(user)
        resp = c.post(
            f"{E_URL}{event.slug}/mark-attendance/",
            {"member": member.pk},
            format="json",
        )
        assert resp.status_code == 403

    def test_attendee_roster_organizer_only(self, event, member_with_user, make_user):
        member, user = member_with_user
        EventAttendance.objects.create(event=event, member=member, rsvp=True)
        # Member denied.
        c = APIClient()
        c.force_authenticate(user)
        assert c.get(f"{E_URL}{event.slug}/attendees/").status_code == 403
        # Organizer allowed.
        c2 = APIClient()
        c2.force_authenticate(make_user(ROLE_ORGANIZING_SECRETARY))
        ok = c2.get(f"{E_URL}{event.slug}/attendees/")
        assert ok.status_code == 200
