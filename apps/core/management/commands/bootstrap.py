"""Bootstrap a fresh KUPPET MSA deployment.

Idempotent first-run setup. Safe to re-run: every step checks for
existing state before creating, so a second invocation is a no-op
rather than a duplicate or an error. This is the single command an
operator runs after `migrate` on a clean database.

Usage:
    python manage.py bootstrap \
        --admin-email chair.it@kuppetmsa.co.ke \
        --admin-password '<from-password-manager>' \
        --bank-name 'KUPPET Mombasa Main' \
        --paybill 600100

What it does (each step skipped if already present):
  1. Creates the initial admin superuser (role=admin, is_staff,
     is_superuser). This account exists only to create the real
     officer accounts through the admin/API; it is NOT a day-to-day
     login.
  2. Creates the default active BankAccount that M-Pesa reconciliation
     and welfare disbursement credit/debit. Without an active account,
     inbound payments land UNMATCHED (Phase 3) — so this must exist
     before go-live.

It deliberately does NOT seed members, fake contributions, or demo
data: a production branch database must start empty of domain data.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Idempotent first-run setup for a fresh deployment."

    def add_arguments(self, parser):
        parser.add_argument("--admin-email", required=True)
        parser.add_argument(
            "--admin-password",
            required=True,
            help="Use a strong value from the branch password manager.",
        )
        parser.add_argument(
            "--bank-name",
            default="KUPPET Mombasa Main Account",
        )
        parser.add_argument(
            "--paybill",
            default="",
            help="Branch-owned M-Pesa Paybill short code (optional now, "
            "required before live payments).",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()
        email = opts["admin_email"].strip().lower()
        password = opts["admin_password"]

        if len(password) < 12:
            raise CommandError("Refusing to set an admin password under 12 characters.")

        # --- 1. initial admin -------------------------------------------
        if User.objects.filter(email=email).exists():
            self.stdout.write(f"Admin {email} already exists — skipped.")
            admin_created = False
        else:
            User.objects.create_superuser(email=email, password=password)
            admin_created = True
            self.stdout.write(self.style.SUCCESS(f"Created admin superuser {email}."))

        # --- 2. default bank account ------------------------------------
        # Imported here so the command still loads if finances migrations
        # are pending (it will then fail clearly on .objects use).
        from apps.finances.models import BankAccount

        if BankAccount.objects.filter(is_active=True).exists():
            self.stdout.write("An active bank account already exists — skipped.")
            bank_created = False
        else:
            BankAccount.objects.create(
                name=opts["bank_name"],
                paybill=opts["paybill"],
                is_active=True,
            )
            bank_created = True
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created active bank account "
                    f"'{opts['bank_name']}'"
                    + (
                        f" (paybill {opts['paybill']})."
                        if opts["paybill"]
                        else " (no paybill yet — set before go-live)."
                    )
                )
            )

        # --- summary ----------------------------------------------------
        if not (admin_created or bank_created):
            self.stdout.write("Nothing to do — deployment already bootstrapped.")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Bootstrap complete. Next: log in to /admin/, "
                    "create the real officer accounts, then run the "
                    "go-live checklist (docs/DEPLOYMENT.md)."
                )
            )
