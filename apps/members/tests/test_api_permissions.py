"""Member API tests — enforce docs/permissions.md §5.2.

One test (or small cluster) per matrix row. If the matrix and these tests
disagree, the matrix wins and the code/tests get fixed.
"""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.constants import (
    ROLE_CHAIRPERSON,
    ROLE_MEMBER,
    ROLE_ORGANIZING_SECRETARY,
    ROLE_TREASURER,
)
from apps.members.models import Member

pytestmark = pytest.mark.django_db


@pytest.fixture
def make_user(django_user_model):
    n = {'i': 0}

    def _make(role=ROLE_MEMBER):
        n['i'] += 1
        return django_user_model.objects.create_user(
            email=f'{role}-{n["i"]}@example.com',
            password='StrongPass-12345',
            role=role,
        )
    return _make


@pytest.fixture
def member():
    return Member.objects.create(
        tsc_number='TSC-100', first_name='Asha', last_name='Otieno',
        school='Coast Academy', sub_county='mvita', phone='0700000000',
    )


def _client(user=None):
    c = APIClient()
    if user:
        c.force_authenticate(user=user)
    return c


LIST_URL = '/api/v1/members/'


class TestDirectoryView:
    """Row: 'View public member directory' — any authenticated user."""

    def test_anonymous_denied(self, member):
        resp = _client().get(LIST_URL)
        assert resp.status_code == 401

    def test_member_sees_directory_minimal_fields(self, make_user, member):
        resp = _client(make_user(ROLE_MEMBER)).get(LIST_URL)
        assert resp.status_code == 200
        row = resp.data['results'][0]
        # Minimal serializer: no PII.
        assert set(row.keys()) == {'id', 'full_name', 'school', 'sub_county'}
        assert 'tsc_number' not in row
        assert 'phone' not in row

    def test_officer_sees_full_record(self, make_user, member):
        resp = _client(make_user(ROLE_ORGANIZING_SECRETARY)).get(LIST_URL)
        assert resp.status_code == 200
        row = resp.data['results'][0]
        assert 'tsc_number' in row
        assert 'phone' in row


class TestCreateMember:
    """Row: 'Create member' — leadership only."""

    def test_member_cannot_create(self, make_user):
        resp = _client(make_user(ROLE_MEMBER)).post(LIST_URL, {
            'tsc_number': 'TSC-X', 'first_name': 'A', 'last_name': 'B',
        }, format='json')
        assert resp.status_code == 403

    def test_organizing_secretary_cannot_create(self, make_user):
        """Officer but NOT leadership -> denied (matrix is explicit)."""
        resp = _client(make_user(ROLE_ORGANIZING_SECRETARY)).post(LIST_URL, {
            'tsc_number': 'TSC-X', 'first_name': 'A', 'last_name': 'B',
        }, format='json')
        assert resp.status_code == 403

    def test_chairperson_can_create(self, make_user):
        resp = _client(make_user(ROLE_CHAIRPERSON)).post(LIST_URL, {
            'tsc_number': 'TSC-X', 'first_name': 'A', 'last_name': 'B',
        }, format='json')
        assert resp.status_code == 201
        assert resp.data['membership_id'] == 'M00001'


class TestEditDeactivate:
    """Rows: 'Edit member (admin fields)' / 'Deactivate' — leadership."""

    def test_member_cannot_edit(self, make_user, member):
        resp = _client(make_user(ROLE_MEMBER)).patch(
            f'{LIST_URL}{member.pk}/', {'is_active': False}, format='json',
        )
        assert resp.status_code == 403

    def test_chairperson_can_deactivate(self, make_user, member):
        resp = _client(make_user(ROLE_CHAIRPERSON)).patch(
            f'{LIST_URL}{member.pk}/', {'is_active': False}, format='json',
        )
        assert resp.status_code == 200
        member.refresh_from_db()
        assert member.is_active is False


class TestSelfService:
    """Rows: 'View/Edit own (safe fields)' — the member themselves."""

    def test_me_requires_linked_profile(self, make_user):
        # User with no linked Member.
        resp = _client(make_user(ROLE_MEMBER)).get(f'{LIST_URL}me/')
        assert resp.status_code == 404

    def test_member_can_view_and_edit_own_safe_fields(
        self, make_user, member,
    ):
        user = make_user(ROLE_MEMBER)
        member.user = user
        member.save()
        client = _client(user)

        get = client.get(f'{LIST_URL}me/')
        assert get.status_code == 200
        assert get.data['membership_id'] == member.membership_id

        patch = client.patch(
            f'{LIST_URL}me/', {'phone': '0712345678', 'bio': 'Teacher'},
            format='json',
        )
        assert patch.status_code == 200
        member.refresh_from_db()
        assert member.phone == '0712345678'
        assert member.bio == 'Teacher'

    def test_self_edit_cannot_touch_admin_fields(self, make_user, member):
        """tsc_number / is_active are not in the self serializer, so even
        if posted they must not change.
        """
        user = make_user(ROLE_MEMBER)
        member.user = user
        member.save()
        _client(user).patch(
            f'{LIST_URL}me/',
            {'tsc_number': 'HACKED', 'is_active': False},
            format='json',
        )
        member.refresh_from_db()
        assert member.tsc_number == 'TSC-100'
        assert member.is_active is True


class TestExport:
    """Row: 'Export member list' — leadership only."""

    def test_member_cannot_export(self, make_user, member):
        resp = _client(make_user(ROLE_MEMBER)).get(f'{LIST_URL}export/')
        assert resp.status_code == 403

    def test_treasurer_cannot_export(self, make_user, member):
        """Treasurer is finance, not leadership -> denied per matrix."""
        resp = _client(make_user(ROLE_TREASURER)).get(f'{LIST_URL}export/')
        assert resp.status_code == 403

    def test_chairperson_can_export(self, make_user, member):
        resp = _client(make_user(ROLE_CHAIRPERSON)).get(f'{LIST_URL}export/')
        assert resp.status_code == 200
        assert resp.data['count'] == 1
