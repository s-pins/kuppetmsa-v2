"""Pre-go-live deployment self-audit.

Turns the operational warnings accumulated across phases into an
automated gate. Run this on the target host before opening the system
to officers. It reports PASS/WARN/FAIL per check and exits non-zero if
any FAIL, so it can be wired into a deploy script.

Checks (each maps to a real risk raised during the build):
  - DEBUG must be off in production.
  - The field-encryption key must be set AND distinct from SECRET_KEY
    (Phase 7: if it equals SECRET_KEY, a routine SECRET_KEY rotation
    silently destroys every disciplinary record).
  - An active BankAccount must exist (Phase 3: otherwise inbound M-Pesa
    is all UNMATCHED).
  - At least one admin account must exist (so the system is reachable).
  - ALLOWED_HOSTS must not be empty/`*` in production.
  - The two policy thresholds are reported for human confirmation
    (Phases 2 & 6: these are placeholders until the chairperson signs
    off against branch financial/welfare regulations).
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Audit deployment readiness; non-zero exit if any check FAILs."

    def _line(self, level, msg):
        style = {
            "PASS": self.style.SUCCESS,
            "WARN": self.style.WARNING,
            "FAIL": self.style.ERROR,
            "INFO": lambda s: s,
        }[level]
        self.stdout.write(style(f"[{level}] {msg}"))

    def handle(self, *args, **opts):
        fails = 0
        warns = 0

        # --- DEBUG ------------------------------------------------------
        if settings.DEBUG:
            self._line("FAIL", "DEBUG is True — must be False in production.")
            fails += 1
        else:
            self._line("PASS", "DEBUG is off.")

        # --- encryption key distinct from SECRET_KEY --------------------
        crypto = getattr(settings, "CRYPTOGRAPHY_KEY", None)
        if not crypto:
            self._line("FAIL", "CRYPTOGRAPHY_KEY is not set.")
            fails += 1
        elif crypto == settings.SECRET_KEY:
            self._line(
                "FAIL",
                "CRYPTOGRAPHY_KEY equals SECRET_KEY. Rotating "
                "SECRET_KEY would permanently destroy all disciplinary "
                "records. Set a distinct DJANGO_FIELD_ENCRYPTION_KEY.",
            )
            fails += 1
        else:
            self._line(
                "PASS",
                "Field-encryption key is set and distinct from SECRET_KEY.",
            )

        # --- ALLOWED_HOSTS ----------------------------------------------
        hosts = settings.ALLOWED_HOSTS
        if not hosts:
            self._line("FAIL", "ALLOWED_HOSTS is empty.")
            fails += 1
        elif "*" in hosts:
            self._line(
                "WARN",
                "ALLOWED_HOSTS contains '*' — acceptable only behind a trusted proxy.",
            )
            warns += 1
        else:
            self._line("PASS", f"ALLOWED_HOSTS restricted to {hosts}.")

        # --- active bank account ----------------------------------------
        from apps.finances.models import BankAccount

        active = BankAccount.objects.filter(is_active=True)
        if not active.exists():
            self._line(
                "FAIL",
                "No active BankAccount — inbound M-Pesa would all be "
                "UNMATCHED. Run `bootstrap` or create one.",
            )
            fails += 1
        else:
            acct = active.first()
            if not acct.paybill:
                self._line(
                    "WARN",
                    f"Active account '{acct.name}' has no paybill set "
                    "— live C2B will not reconcile until it does.",
                )
                warns += 1
            else:
                self._line(
                    "PASS",
                    f"Active bank account present (paybill {acct.paybill}).",
                )

        # --- an admin exists --------------------------------------------
        User = get_user_model()
        if not User.objects.filter(is_superuser=True).exists():
            self._line(
                "FAIL",
                "No superuser account — the system would be unreachable for setup.",
            )
            fails += 1
        else:
            self._line("PASS", "At least one admin account exists.")

        # --- policy thresholds (human confirmation) ---------------------
        from apps.core import constants

        self._line(
            "INFO",
            "Confirm with the chairperson against branch regulations: "
            f"LARGE_EXPENSE_THRESHOLD_KES="
            f"{constants.LARGE_EXPENSE_THRESHOLD_KES}, "
            f"WELFARE_AUTO_APPROVE_THRESHOLD_KES="
            f"{constants.WELFARE_AUTO_APPROVE_THRESHOLD_KES}. "
            "Changing these after data exists needs a migration.",
        )

        # --- verdict ----------------------------------------------------
        self.stdout.write("")
        if fails:
            self._line(
                "FAIL",
                f"{fails} blocking issue(s), {warns} warning(s). NOT ready for go-live.",
            )
            raise SystemExit(1)
        if warns:
            self._line(
                "WARN",
                f"0 blocking issues, {warns} warning(s). Review warnings before go-live.",
            )
        else:
            self._line("PASS", "All deployment checks passed.")
