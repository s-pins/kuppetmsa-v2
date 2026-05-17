"""Communications tests — docs/permissions.md §5.9.

Headline properties: audience targeting selects exactly the right
members, send is idempotent (Safaricom-retry-style double calls don't
double-notify), and a member's inbox is strictly their own.
"""

import pytest
from rest_framework.test import APIClient

from apps.communications.models import (
    Announcement,
    AudienceScope,
    Notification,
)
from apps.core.constants import (
    ROLE_CHAIRPERSON,
    ROLE_MEMBER,
    ROLE_TREASURER,
)
from apps.members.models import Member

pytestmark = pytest.mark.django_db


@pytest.fixture
def make_user(django_user_model):
    n = {"i": 0}

    def _make(role=ROLE_MEMBER, *, profile=True, sub_county="", active=True):
        n["i"] += 1
        u = django_user_model.objects.create_user(
            email=f"{role}-{n['i']}@example.com",
            password="StrongPass-12345",
            role=role,
        )
        m = None
        if profile:
            m = Member.objects.create(
                tsc_number=f"TSC-{n['i']}",
                first_name=f"F{n['i']}",
                last_name="M",
                user=u,
                sub_county=sub_county,
                is_active=active,
            )
        return u, m

    return _make


def _client(u):
    c = APIClient()
    c.force_authenticate(u)
    return c


ANN = "/api/v1/communications/announcements/"
INBOX = "/api/v1/communications/inbox/"


class TestComposePermissions:
    def test_member_cannot_compose(self, make_user):
        u, _ = make_user(ROLE_MEMBER)
        resp = _client(u).post(ANN, {"title": "X", "body": "Y"}, format="json")
        assert resp.status_code == 403

    def test_treasurer_cannot_compose_not_comms_role(self, make_user):
        u, _ = make_user(ROLE_TREASURER, profile=False)
        resp = _client(u).post(ANN, {"title": "X", "body": "Y"}, format="json")
        assert resp.status_code == 403

    def test_chairperson_can_compose(self, make_user):
        u, _ = make_user(ROLE_CHAIRPERSON, profile=False)
        resp = _client(u).post(
            ANN,
            {
                "title": "AGM Notice",
                "body": "AGM on Saturday.",
                "audience_scope": "all_members",
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["status"] == "draft"


class TestAudienceTargeting:
    def test_active_members_scope_excludes_inactive(self, make_user):
        author, _ = make_user(ROLE_CHAIRPERSON, profile=False)
        _u1, _m1 = make_user(ROLE_MEMBER, active=True)
        _u2, _m2 = make_user(ROLE_MEMBER, active=True)
        _u3, _m3 = make_user(ROLE_MEMBER, active=False)  # inactive

        ann = Announcement.objects.create(
            title="T",
            body="B",
            audience_scope=AudienceScope.ACTIVE_MEMBERS,
            created_by=author,
        )
        count = ann.send()
        assert count == 2  # the inactive member excluded
        assert Notification.objects.count() == 2

    def test_sub_county_scope_targets_only_that_sub_county(self, make_user):
        author, _ = make_user(ROLE_CHAIRPERSON, profile=False)
        make_user(ROLE_MEMBER, sub_county="mvita")
        make_user(ROLE_MEMBER, sub_county="mvita")
        make_user(ROLE_MEMBER, sub_county="nyali")

        ann = Announcement.objects.create(
            title="Mvita meeting",
            body="B",
            audience_scope=AudienceScope.SUB_COUNTY,
            audience_sub_county="mvita",
            created_by=author,
        )
        assert ann.send() == 2

    def test_sub_county_scope_without_sub_county_refused(self, make_user):
        from django.core.exceptions import ValidationError

        author, _ = make_user(ROLE_CHAIRPERSON, profile=False)
        ann = Announcement.objects.create(
            title="T",
            body="B",
            audience_scope=AudienceScope.SUB_COUNTY,
            created_by=author,
        )
        with pytest.raises(ValidationError):
            ann.send()


class TestIdempotentSend:
    def test_double_send_refused(self, make_user):
        from django.core.exceptions import ValidationError

        author, _ = make_user(ROLE_CHAIRPERSON, profile=False)
        make_user(ROLE_MEMBER)
        ann = Announcement.objects.create(
            title="T",
            body="B",
            audience_scope=AudienceScope.ALL_MEMBERS,
            created_by=author,
        )
        ann.send()
        with pytest.raises(ValidationError):
            ann.send()
        # Still exactly one notification — no double fan-out.
        assert Notification.objects.count() == 1

    def test_send_via_api_then_retry_400(self, make_user):
        author, _ = make_user(ROLE_CHAIRPERSON, profile=False)
        make_user(ROLE_MEMBER)
        created = _client(author).post(
            ANN,
            {
                "title": "T",
                "body": "B",
                "audience_scope": "all_members",
            },
            format="json",
        )
        aid = created.data["id"]
        first = _client(author).post(f"{ANN}{aid}/send/", {}, format="json")
        assert first.status_code == 200
        retry = _client(author).post(f"{ANN}{aid}/send/", {}, format="json")
        assert retry.status_code == 400
        assert Notification.objects.count() == 1


class TestInboxIsolation:
    def test_member_sees_only_own_notifications(self, make_user):
        author, _ = make_user(ROLE_CHAIRPERSON, profile=False)
        ua, _ma = make_user(ROLE_MEMBER)
        _ub, _mb = make_user(ROLE_MEMBER)
        ann = Announcement.objects.create(
            title="All",
            body="B",
            audience_scope=AudienceScope.ALL_MEMBERS,
            created_by=author,
        )
        ann.send()  # both members notified

        resp = _client(ua).get(INBOX)
        assert resp.status_code == 200
        # A sees exactly one row (their own), not B's.
        assert len(resp.data["results"]) == 1

    def test_mark_read_only_affects_own(self, make_user):
        author, _ = make_user(ROLE_CHAIRPERSON, profile=False)
        ua, _ma = make_user(ROLE_MEMBER)
        _ub, mb = make_user(ROLE_MEMBER)
        ann = Announcement.objects.create(
            title="All",
            body="B",
            audience_scope=AudienceScope.ALL_MEMBERS,
            created_by=author,
        )
        ann.send()
        b_notif = Notification.objects.get(member=mb)
        # A tries to mark B's notification read -> 404 (not theirs).
        resp = _client(ua).post(f"{INBOX}{b_notif.pk}/read/", {}, format="json")
        assert resp.status_code == 404
        b_notif.refresh_from_db()
        assert b_notif.is_read is False

    def test_member_marks_own_read(self, make_user):
        author, _ = make_user(ROLE_CHAIRPERSON, profile=False)
        ua, ma = make_user(ROLE_MEMBER)
        ann = Announcement.objects.create(
            title="All",
            body="B",
            audience_scope=AudienceScope.ALL_MEMBERS,
            created_by=author,
        )
        ann.send()
        notif = Notification.objects.get(member=ma)
        resp = _client(ua).post(f"{INBOX}{notif.pk}/read/", {}, format="json")
        assert resp.status_code == 200
        notif.refresh_from_db()
        assert notif.is_read is True

    def test_account_without_profile_denied_inbox(self, make_user):
        u, _ = make_user(ROLE_TREASURER, profile=False)
        assert _client(u).get(INBOX).status_code == 403
