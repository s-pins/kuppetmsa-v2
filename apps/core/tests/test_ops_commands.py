"""Tests for the operational commands.

bootstrap must be idempotent (re-running is safe) and check_deploy must
actually FAIL on the conditions the runbook says it guards.
"""

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.finances.models import BankAccount

pytestmark = pytest.mark.django_db


class TestBootstrap:
    def test_creates_admin_and_bank_account(self):
        out = io.StringIO()
        call_command(
            "bootstrap",
            "--admin-email",
            "Admin@KUPPETMSA.co.ke",
            "--admin-password",
            "StrongBootstrapPass-2026",
            "--paybill",
            "600100",
            stdout=out,
        )
        User = get_user_model()
        admin = User.objects.get(email="admin@kuppetmsa.co.ke")
        assert admin.is_superuser is True
        assert admin.role == "admin"
        acct = BankAccount.objects.get()
        assert acct.is_active is True
        assert acct.paybill == "600100"

    def test_is_idempotent(self):
        args = [
            "bootstrap",
            "--admin-email",
            "admin@kuppetmsa.co.ke",
            "--admin-password",
            "StrongBootstrapPass-2026",
        ]
        call_command(*args, stdout=io.StringIO())
        # Second run must not duplicate or error.
        out = io.StringIO()
        call_command(*args, stdout=out)
        User = get_user_model()
        assert User.objects.filter(email="admin@kuppetmsa.co.ke").count() == 1
        assert BankAccount.objects.count() == 1
        assert "already bootstrapped" in out.getvalue()

    def test_rejects_weak_password(self):
        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            call_command(
                "bootstrap",
                "--admin-email",
                "a@b.ke",
                "--admin-password",
                "short",
                stdout=io.StringIO(),
            )


class TestCheckDeploy:
    def test_fails_when_no_bank_account_or_admin(self, settings):
        # Clean DB: no admin, no bank account -> must exit non-zero.
        settings.DEBUG = False
        with pytest.raises(SystemExit) as exc:
            call_command("check_deploy", stdout=io.StringIO())
        assert exc.value.code == 1

    def test_fails_when_encryption_key_equals_secret_key(self, settings):
        settings.DEBUG = False
        settings.CRYPTOGRAPHY_KEY = settings.SECRET_KEY
        with pytest.raises(SystemExit):
            call_command("check_deploy", stdout=io.StringIO())

    def test_passes_when_properly_configured(self, settings):
        settings.DEBUG = False
        settings.CRYPTOGRAPHY_KEY = "a-distinct-key-not-the-secret-key"
        settings.ALLOWED_HOSTS = ["kuppetmsa.co.ke"]
        User = get_user_model()
        User.objects.create_superuser(
            email="admin@kuppetmsa.co.ke",
            password="StrongPass-12345",
        )
        BankAccount.objects.create(name="Main", paybill="600100", is_active=True)
        out = io.StringIO()
        # Should NOT raise SystemExit.
        call_command("check_deploy", stdout=out)
        assert "All deployment checks passed" in out.getvalue()

    def test_warns_but_passes_without_paybill(self, settings):
        settings.DEBUG = False
        settings.CRYPTOGRAPHY_KEY = "a-distinct-key-not-the-secret-key"
        settings.ALLOWED_HOSTS = ["kuppetmsa.co.ke"]
        User = get_user_model()
        User.objects.create_superuser(
            email="admin@kuppetmsa.co.ke",
            password="StrongPass-12345",
        )
        BankAccount.objects.create(name="Main", paybill="", is_active=True)
        out = io.StringIO()
        call_command("check_deploy", stdout=out)  # no SystemExit
        assert "no paybill" in out.getvalue()
