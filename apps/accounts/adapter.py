"""Custom allauth adapter.

Bridges allauth's auth lifecycle to the two cached fields the Phase 0
permission classes rely on:

  - `is_2fa_enrolled`  — kept true while the user has an active TOTP authenticator
  - `last_strong_auth_at` — stamped every time the user proves their identity
                            (login, password re-entry, MFA challenge)

Without this bridge, RecentAuthRequired / IsDisciplineCommittee would never
see a fresh timestamp and would lock everyone out.
"""

from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from django.utils import timezone


class AccountAdapter(DefaultAccountAdapter):
    def login(self, request, user):
        super().login(request, user)
        # A successful login is strong auth.
        self._stamp_strong_auth(user)

    def _stamp_strong_auth(self, user) -> None:
        user.last_strong_auth_at = timezone.now()
        user.save(update_fields=["last_strong_auth_at"])

    @staticmethod
    def refresh_mfa_flag(user) -> None:
        """Recompute is_2fa_enrolled from the user's authenticators.

        Called by the MFA signal handlers in apps.accounts.signals. Kept
        here so the truth-source logic lives in one module.
        """
        from allauth.mfa.models import Authenticator

        has_totp = Authenticator.objects.filter(
            user=user,
            type=Authenticator.Type.TOTP,
        ).exists()
        if user.is_2fa_enrolled != has_totp:
            user.is_2fa_enrolled = has_totp
            user.save(update_fields=["is_2fa_enrolled"])
