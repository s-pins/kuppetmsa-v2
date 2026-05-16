"""Signal handlers for the accounts app.

Wired in AccountsConfig.ready(). These keep the cached security fields
honest:

  - authenticator added/removed  -> recompute is_2fa_enrolled
  - MFA challenge passed         -> stamp last_strong_auth_at
  - password changed/reset       -> stamp last_strong_auth_at
"""

from __future__ import annotations

from allauth.account.signals import password_changed, password_reset
from allauth.mfa.signals import authenticator_added, authenticator_removed
from django.dispatch import receiver
from django.utils import timezone

from apps.accounts.adapter import AccountAdapter


@receiver(authenticator_added)
def _on_authenticator_added(sender, request, user, authenticator, **kwargs):
    AccountAdapter.refresh_mfa_flag(user)


@receiver(authenticator_removed)
def _on_authenticator_removed(sender, request, user, authenticator, **kwargs):
    AccountAdapter.refresh_mfa_flag(user)


@receiver(password_changed)
def _on_password_changed(sender, request, user, **kwargs):
    user.last_strong_auth_at = timezone.now()
    user.save(update_fields=["last_strong_auth_at"])


@receiver(password_reset)
def _on_password_reset(sender, request, user, **kwargs):
    user.last_strong_auth_at = timezone.now()
    user.save(update_fields=["last_strong_auth_at"])
