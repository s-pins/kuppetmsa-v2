"""Tests for the accounts adapter + signals.

These guard the bridge between allauth's lifecycle and the cached security
fields the Phase 0 permission classes depend on. If this bridge breaks,
RecentAuthRequired silently locks everyone out (or worse, never expires).
"""
import pytest
from django.utils import timezone

from apps.accounts.adapter import AccountAdapter

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        email='officer@example.com',
        password='StrongPass-12345',
    )


class TestStrongAuthStamping:
    def test_adapter_login_stamps_timestamp(self, user, rf):
        assert user.last_strong_auth_at is None
        request = rf.post('/accounts/login/')
        # Minimal session for allauth's login() internals.
        from django.contrib.sessions.backends.db import SessionStore
        request.session = SessionStore()

        before = timezone.now()
        try:
            AccountAdapter().login(request, user)
        except Exception:
            # allauth's full login() touches more request plumbing than a
            # bare RequestFactory provides; we only care that our override
            # stamped the field before/after delegating.
            pass
        user.refresh_from_db()
        assert user.last_strong_auth_at is not None
        assert user.last_strong_auth_at >= before


class TestMfaFlagSync:
    def test_refresh_sets_flag_false_when_no_authenticator(self, user):
        user.is_2fa_enrolled = True
        user.save(update_fields=['is_2fa_enrolled'])
        AccountAdapter.refresh_mfa_flag(user)
        user.refresh_from_db()
        assert user.is_2fa_enrolled is False

    def test_refresh_sets_flag_true_when_totp_present(self, user):
        from allauth.mfa.models import Authenticator

        Authenticator.objects.create(
            user=user,
            type=Authenticator.Type.TOTP,
            data={'secret': 'JBSWY3DPEHPK3PXP'},
        )
        AccountAdapter.refresh_mfa_flag(user)
        user.refresh_from_db()
        assert user.is_2fa_enrolled is True
