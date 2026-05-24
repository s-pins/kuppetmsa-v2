"""Seed realistic demo data for visualising the public site.

DEV/DEMO ONLY. Safe to re-run: it removes the demo records it creates
(tagged by known demo values) before re-creating them, so you never get
duplicates. It refuses to run unless DEBUG is True, so it can never be
pointed at production data by accident.

    python manage.py seed_demo
    python manage.py seed_demo --no-election   # neutral site (no modal)
    python manage.py seed_demo --clear         # remove demo data, stop

What it creates:
  - 1 chairperson account (demo.chair@kuppetmombasa.co.ke / DemoPass!2026)
  - an active bank account + ~12 reconciled M-Pesa contributions
  - 2 approved expenses (so the transparency net position is realistic)
  - 4 public projects across statuses, 3 published reports, 3 public news
  - 1 ACTIVE ElectionNotice with the campaign poster (unless --no-election)

The election poster: if a file exists at the path given by
--poster (default: the uploaded campaign image), it is attached;
otherwise the notice is still created without an image so the modal
still demonstrably pops.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

DEMO_TAG = "[DEMO]"
DEMO_CHAIR_EMAIL = "demo.chair@kuppetmombasa.co.ke"
# Intentional, well-known demo credential. This command refuses to run
# unless DEBUG is True, so this account can never exist in production.
# The S105 suppression below is correct — a fixture password, not a secret.
DEMO_CHAIR_PASSWORD = "DemoPass!2026"  # noqa: S105

# Bundled fixture poster — ships in the repo so seeding works on any
# machine without the operator hunting for an image file. Override
# with --poster /path/to/your.png if you want a different one.
DEFAULT_POSTER = str(Path(__file__).resolve().parents[2] / "fixtures" / "campaign_poster.png")


class Command(BaseCommand):
    help = "Seed demo data for visualising the public site (DEBUG only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-election",
            action="store_true",
            help="Skip the election notice (neutral site preview).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Only remove existing demo data, then exit.",
        )
        parser.add_argument(
            "--poster",
            default=DEFAULT_POSTER,
            help="Path to the campaign poster image.",
        )

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError(
                "Refusing to seed demo data while DEBUG is False. "
                "This command is for local/demo use only."
            )

        from apps.accounts.models import User
        from apps.communications.models import (
            Announcement,
            AnnouncementStatus,
            AudienceScope,
        )
        from apps.finances.models import (
            BankAccount,
            Expense,
            ExpenseStatus,
            FinancialContribution,
        )
        from apps.members.models import Member
        from apps.projects.models import Project
        from apps.public_site.models import ElectionNotice
        from apps.reports.models import Report

        # --- clear prior demo data (idempotency) ------------------------
        self.stdout.write("Removing any existing demo data…")
        Announcement.objects.filter(title__startswith=DEMO_TAG).delete()
        Report.objects.filter(title__startswith=DEMO_TAG).delete()
        Project.objects.filter(name__startswith=DEMO_TAG).delete()
        Expense.objects.filter(description__startswith=DEMO_TAG).delete()
        FinancialContribution.objects.filter(mpesa_ref__startswith="DEMO").delete()
        Member.objects.filter(tsc_number__startswith="DEMO-").delete()
        ElectionNotice.objects.all().delete()
        User.objects.filter(email=DEMO_CHAIR_EMAIL).delete()

        if opts["clear"]:
            self.stdout.write(self.style.SUCCESS("Demo data cleared. Done."))
            return

        # --- chairperson ------------------------------------------------
        chair = User.objects.create_user(
            email=DEMO_CHAIR_EMAIL,
            password=DEMO_CHAIR_PASSWORD,
            role="chairperson",
        )
        self.stdout.write(f"Created demo chairperson: {DEMO_CHAIR_EMAIL} / {DEMO_CHAIR_PASSWORD}")

        # --- bank account + members + contributions ---------------------
        account, _ = BankAccount.objects.get_or_create(
            name="KUPPET Mombasa Main Account",
            defaults={"paybill": "600100", "is_active": True},
        )
        if not account.is_active:
            account.is_active = True
            account.save(update_fields=["is_active"])

        members = []
        sample = [
            ("Asha", "Otieno", "mvita"),
            ("Brian", "Kamau", "nyali"),
            ("Cynthia", "Wanjiru", "kisauni"),
            ("David", "Mwangi", "changamwe"),
            ("Esther", "Achieng", "likoni"),
            ("Felix", "Onyango", "jomvu"),
        ]
        for i, (fn, ln, sc) in enumerate(sample, start=1):
            members.append(
                Member.objects.create(
                    tsc_number=f"DEMO-{i:04d}",
                    first_name=fn,
                    last_name=ln,
                    sub_county=sc,
                    is_active=True,
                )
            )

        now = timezone.now()
        amounts = [
            "1500",
            "2000",
            "1200",
            "3000",
            "2500",
            "1800",
            "2200",
            "1600",
            "2800",
            "1400",
            "3200",
            "1900",
        ]
        sources = [
            "mpesa_c2b",
            "mpesa_stk",
            "mpesa_c2b",
            "bank_transfer",
        ]
        for idx, amt in enumerate(amounts):
            FinancialContribution.objects.create(
                member=members[idx % len(members)],
                bank_account=account,
                amount_kes=Decimal(amt),
                source=sources[idx % len(sources)],
                mpesa_ref=f"DEMO{idx:05d}",
                paid_at=now - datetime.timedelta(days=idx * 9),
                reconciled=True,
                recorded_by=chair,
            )
        self.stdout.write(f"Created {len(amounts)} contributions.")

        # --- a couple of approved expenses ------------------------------
        for desc, amt in [
            (f"{DEMO_TAG} Borehole drilling — phase 1", "180000"),
            (f"{DEMO_TAG} Office renovation final payment", "95000"),
        ]:
            Expense.objects.create(
                bank_account=account,
                amount_kes=Decimal(amt),
                description=desc,
                status=ExpenseStatus.APPROVED,
                created_by=chair,
                approved_by=chair,
                decided_at=now,
            )
        self.stdout.write("Created 2 approved expenses.")

        # --- projects ---------------------------------------------------
        projects = [
            (
                "Kongowea Borehole Project",
                "kongowea-borehole",
                "Clean water access for teachers' residences in "
                "Kongowea ward — drilling, pump and storage tank.",
                "active",
                "500000",
                "120 teachers",
                datetime.date(2026, 1, 15),
                None,
            ),
            (
                "Branch Office Renovation",
                "branch-office-renovation",
                "Refurbishment of the Mombasa branch office for improved member services.",
                "completed",
                "300000",
                "All branch members",
                datetime.date(2025, 8, 1),
                datetime.date(2026, 2, 28),
            ),
            (
                "Member Laptop Support Scheme",
                "laptop-support-scheme",
                "Subsidised laptops for members pursuing further studies.",
                "planned",
                "750000",
                "60 teachers (first cohort)",
                None,
                None,
            ),
            (
                "Coast Teachers Wellness Camp",
                "wellness-camp-2026",
                "Annual health screening and wellness camp for members and dependants.",
                "active",
                "220000",
                "300+ attendees expected",
                datetime.date(2026, 3, 10),
                None,
            ),
        ]
        for (
            name,
            slug,
            desc,
            status,
            budget,
            benef,
            start,
            end,
        ) in projects:
            Project.objects.create(
                name=f"{DEMO_TAG} {name}",
                slug=slug,
                description=desc,
                status=status,
                budget_kes=Decimal(budget),
                beneficiaries=benef,
                started_on=start,
                ended_on=end,
                is_public=True,
            )
        self.stdout.write(f"Created {len(projects)} public projects.")

        # --- reports ----------------------------------------------------
        reports = [
            (
                "Audited Accounts FY2025",
                "financial",
                2025,
                "Independently audited branch financial statements for the 2025 financial year.",
            ),
            (
                "Annual General Meeting Minutes 2025",
                "agm",
                2025,
                "Minutes and resolutions of the 2025 AGM.",
            ),
            (
                "Branch Activity Report 2025",
                "activity",
                2025,
                "Summary of branch activities, projects and member services delivered in 2025.",
            ),
        ]
        for title, cat, yr, desc in reports:
            r = Report(
                title=f"{DEMO_TAG} {title}",
                category=cat,
                year=yr,
                description=desc,
                is_published=True,
                uploaded_by=chair,
            )
            r.file.save(
                f"demo_{cat}_{yr}.pdf",
                File(_tiny_pdf(), name=f"demo_{cat}_{yr}.pdf"),
                save=False,
            )
            r.save()
        self.stdout.write(f"Created {len(reports)} published reports.")

        # --- public news ------------------------------------------------
        # 4-tuple: (title, body, image_filename_or_None, image_alt).
        # image_filename is resolved against apps/public_site/fixtures/
        # so seed works on any machine.
        news = [
            (
                "Change from Agency to Full Membership on T-Pay",
                "About 220 teachers in Mombasa were listed under "
                "Agency status in the December 2025 register and were "
                "therefore unable to vote in branch elections. The "
                "graphic above walks you through the 7-step T-Pay "
                "process to switch your status to Full Membership. "
                "Affected colleagues are encouraged to act before the "
                "registration window closes.",
                "registration_guide.png",
                "7-step visual guide for switching from Agency to "
                "Full Membership on the TSC T-Pay portal: log in, "
                "select Send Payslip(s), choose SWA, pick "
                "KUPPET Union Dues, send, confirm OTP, await "
                "approval.",
            ),
            (
                "Q1 Welfare Disbursements Complete",
                "The branch completed Q1 welfare disbursements "
                "totalling KES 1.2M across 38 members. A full "
                "breakdown is available in the transparency portal.",
                None,
                "",
            ),
            (
                "Kongowea Borehole Reaches Phase 1",
                "Drilling for the Kongowea borehole is complete and "
                "the pump installation has begun. Expected "
                "completion within the quarter.",
                None,
                "",
            ),
            (
                "AGM 2026 — Save the Date",
                "The 2026 Annual General Meeting will be held in "
                "April. Formal notice and agenda to follow.",
                None,
                "",
            ),
        ]
        fixtures_dir = Path(__file__).resolve().parents[2] / "fixtures"
        for title, body, img_name, img_alt in news:
            a = Announcement(
                title=f"{DEMO_TAG} {title}",
                body=body,
                audience_scope=AudienceScope.ALL_MEMBERS,
                created_by=chair,
                is_public=True,
                image_alt=img_alt,
            )
            if img_name:
                img_path = fixtures_dir / img_name
                if img_path.is_file():
                    with img_path.open("rb") as fh:
                        a.image.save(img_name, File(fh, name=img_name), save=False)
                else:
                    self.stdout.write(
                        self.style.WARNING(f"News image fixture not found: {img_path}")
                    )
            a.save()
            a.status = AnnouncementStatus.SENT
            a.sent_at = now
            a.save(update_fields=["status", "sent_at"])
        self.stdout.write(
            f"Created {len(news)} public news items "
            f"({sum(1 for _, _, n, _ in news if n)} with images)."
        )

        # --- election notice -------------------------------------------
        if opts["no_election"]:
            self.stdout.write(
                "Skipped election notice (--no-election): the site previews in neutral mode."
            )
        else:
            notice = ElectionNotice(
                title="Branch Elections 2026 — A Vote for Transparency",
                body=(
                    "Team Reforms SKS, led by Edwin Shireku, is "
                    "committed to running KUPPET Mombasa in the open. "
                    "This system — public accounts, audited reports, "
                    "member welfare tracking — is what transparent "
                    "leadership looks like."
                ),
                learn_more_url="https://example.org/team-reforms-sks",
                learn_more_label="About Team Reforms SKS",
                is_active=True,
            )
            poster_path = Path(opts["poster"])
            if poster_path.is_file():
                with poster_path.open("rb") as fh:
                    notice.poster.save(
                        "campaign_poster.png",
                        File(fh, name="campaign_poster.png"),
                        save=False,
                    )
                self.stdout.write(f"Attached campaign poster from {poster_path}.")
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Poster not found at {poster_path} — notice "
                        "created without an image (modal still pops)."
                    )
                )
            notice.save()
            self.stdout.write(
                self.style.SUCCESS(
                    "Created ACTIVE election notice — the modal will pop on the public site."
                )
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Demo seed complete. Start the server and open "
                "http://127.0.0.1:8000/ — the election modal pops on "
                "first load (dismiss persists for the browser session)."
            )
        )


def _tiny_pdf():
    """Smallest valid-ish PDF so report downloads are real files."""
    import io

    return io.BytesIO(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>"
        b"endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
    )
