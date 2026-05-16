"""Smoke tests for auth flow and Swagger officer-gating.

These are integration tests against the actual URL conf to make sure
the pieces are wired correctly, not just unit-tested in isolation.
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.constants import ROLE_CHAIRPERSON, ROLE_MEMBER

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# JWT token obtain / refresh
# ---------------------------------------------------------------------------


class TestJWTAuth:
    def test_obtain_token_with_valid_credentials(self, django_user_model):
        django_user_model.objects.create_user(
            email="member@example.com",
            password="ValidPass-123-secure",
            role=ROLE_MEMBER,
        )
        client = APIClient()
        resp = client.post(
            reverse("api_v1:token_obtain"),
            {"email": "member@example.com", "password": "ValidPass-123-secure"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        assert "access" in resp.data
        assert "refresh" in resp.data

    def test_obtain_token_rejects_bad_password(self, django_user_model):
        django_user_model.objects.create_user(
            email="member@example.com",
            password="ValidPass-123-secure",
            role=ROLE_MEMBER,
        )
        client = APIClient()
        resp = client.post(
            reverse("api_v1:token_obtain"),
            {"email": "member@example.com", "password": "wrong-password"},
            format="json",
        )
        assert resp.status_code == 401

    def test_me_endpoint_requires_auth(self):
        client = APIClient()
        resp = client.get(reverse("api_v1:accounts:me"))
        assert resp.status_code == 401

    def test_me_endpoint_returns_current_user(self, django_user_model):
        user = django_user_model.objects.create_user(
            email="member@example.com",
            password="ValidPass-123-secure",
            role=ROLE_MEMBER,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(reverse("api_v1:accounts:me"))
        assert resp.status_code == 200
        assert resp.data["email"] == "member@example.com"
        assert resp.data["role"] == ROLE_MEMBER


# ---------------------------------------------------------------------------
# Swagger / schema gating
# ---------------------------------------------------------------------------


class TestSwaggerGating:
    def test_anonymous_blocked_from_schema(self):
        client = APIClient()
        resp = client.get(reverse("api_v1:schema"))
        assert resp.status_code in (401, 403)

    def test_anonymous_blocked_from_swagger(self):
        client = APIClient()
        resp = client.get(reverse("api_v1:swagger"))
        assert resp.status_code in (401, 403)

    def test_member_blocked_from_swagger(self, django_user_model):
        user = django_user_model.objects.create_user(
            email="member@example.com",
            password="ValidPass-123-secure",
            role=ROLE_MEMBER,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(reverse("api_v1:swagger"))
        assert resp.status_code == 403

    def test_officer_can_reach_swagger(self, django_user_model):
        user = django_user_model.objects.create_user(
            email="chair@example.com",
            password="ValidPass-123-secure",
            role=ROLE_CHAIRPERSON,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(reverse("api_v1:swagger"))
        assert resp.status_code == 200
