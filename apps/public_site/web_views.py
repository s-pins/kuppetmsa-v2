"""Server-rendered public website.

Composes the already-public data (projects, reports, news, finance
transparency) into real HTML pages — the site a visitor sees at the
branch domain. All AllowAny, read-only, and subject to the same
leak-prevention as the public API (only is_public / is_published /
sent records are ever queried).

The election notice is injected via context ONLY when one is active;
when campaign mode is off, `election_notice` is None and the templates
render a clean neutral site with zero campaign markup.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.views.generic import TemplateView

from apps.communications.models import Announcement, AnnouncementStatus
from apps.finances.models import Expense, ExpenseStatus, FinancialContribution
from apps.projects.models import Project
from apps.public_site.models import ElectionNotice
from apps.reports.models import Report


class _PublicContextMixin:
    """Shared context: branding + the optional election notice.

    `election_notice` is the ONLY campaign touch-point in the whole
    frontend. None => neutral site.
    """

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["branch_name"] = "KUPPET Mombasa"
        ctx["election_notice"] = ElectionNotice.current()
        ctx["year"] = timezone.now().year
        return ctx


class HomeView(_PublicContextMixin, TemplateView):
    template_name = "public_site/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        contrib_total = FinancialContribution.objects.aggregate(s=Sum("amount_kes"))[
            "s"
        ] or Decimal("0.00")
        approved_total = Expense.objects.filter(status=ExpenseStatus.APPROVED).aggregate(
            s=Sum("amount_kes")
        )["s"] or Decimal("0.00")

        ctx["stats"] = {
            "contributions": contrib_total,
            "expenses": approved_total,
            "net": contrib_total - approved_total,
            "projects": Project.objects.filter(is_public=True).count(),
            "reports": Report.objects.filter(is_published=True).count(),
        }
        ctx["recent_projects"] = Project.objects.filter(is_public=True).order_by(
            "-started_on", "name"
        )[:3]
        ctx["recent_news"] = Announcement.objects.filter(
            is_public=True, status=AnnouncementStatus.SENT
        ).order_by("-sent_at")[:3]

        # Unified "Latest" feed — what makes refreshing the home page
        # rewarding. Each entry is normalised to a small dict so the
        # template renders the strip uniformly regardless of source.
        #
        # Algorithm: ROUND-ROBIN merge. Take the freshest item from
        # each source in turn until we have 6. A naive global sort by
        # date lets a noisier source crowd out the others (seeding
        # reports right after news leaves news with later timestamps
        # and buries it). Per-source cap then sort has the SAME
        # problem — capping only limits, it doesn't guarantee
        # inclusion. Round-robin guarantees mix: one of each, then
        # another of each, until the strip is full.
        from itertools import zip_longest

        def _norm(qs, kind, label, url, date_field):
            out = []
            for obj in qs[:6]:
                out.append(
                    {
                        "kind": kind,
                        "label": label,
                        "title": getattr(obj, "title", None) or obj.name,
                        "summary": getattr(obj, "body", None) or getattr(obj, "description", ""),
                        "url": url,
                        "date": getattr(obj, date_field),
                        "image": getattr(obj, "image", None),
                    }
                )
            return out

        news_items = _norm(
            Announcement.objects.filter(is_public=True, status=AnnouncementStatus.SENT).order_by(
                "-sent_at"
            ),
            "news",
            "News",
            "/news/",
            "sent_at",
        )
        # updated_at on projects so status changes (planned -> active
        # -> completed) bubble a project up the feed.
        project_items = _norm(
            Project.objects.filter(is_public=True).order_by("-updated_at"),
            "project",
            "Project",
            "/projects/",
            "updated_at",
        )
        report_items = _norm(
            Report.objects.filter(is_published=True).order_by("-created_at"),
            "report",
            "Report",
            "/reports/",
            "created_at",
        )

        # Round-robin: news first because a fresh announcement is most
        # time-sensitive ("don't miss this"), then project, then report.
        latest = []
        for triple in zip_longest(news_items, project_items, report_items):
            for item in triple:
                if item is not None:
                    latest.append(item)
                    if len(latest) == 6:
                        break
            if len(latest) == 6:
                break
        ctx["latest"] = latest
        return ctx


class TransparencyView(_PublicContextMixin, TemplateView):
    template_name = "public_site/transparency.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        contrib = FinancialContribution.objects.aggregate(s=Sum("amount_kes"))["s"] or Decimal(
            "0.00"
        )
        approved = Expense.objects.filter(status=ExpenseStatus.APPROVED).aggregate(
            s=Sum("amount_kes")
        )["s"] or Decimal("0.00")

        by_source = list(
            FinancialContribution.objects.values("source")
            .annotate(total=Sum("amount_kes"))
            .order_by("-total")
        )
        monthly = list(
            FinancialContribution.objects.annotate(m=TruncMonth("paid_at"))
            .values("m")
            .annotate(total=Sum("amount_kes"))
            .order_by("m")
        )
        ctx["contrib"] = contrib
        ctx["approved"] = approved
        ctx["net"] = contrib - approved
        ctx["by_source"] = by_source
        ctx["monthly"] = [
            {
                "month": r["m"].strftime("%b %Y") if r["m"] else "—",
                "total": r["total"],
            }
            for r in monthly
        ]
        ctx["projects"] = Project.objects.filter(is_public=True).order_by("-started_on")
        return ctx


class ProjectsView(_PublicContextMixin, TemplateView):
    template_name = "public_site/projects.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["projects"] = Project.objects.filter(is_public=True).order_by("-started_on", "name")
        return ctx


class ReportsView(_PublicContextMixin, TemplateView):
    template_name = "public_site/reports.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["reports"] = Report.objects.filter(is_published=True).order_by("-year", "-created_at")
        return ctx


class NewsView(_PublicContextMixin, TemplateView):
    template_name = "public_site/news.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["news"] = Announcement.objects.filter(
            is_public=True, status=AnnouncementStatus.SENT
        ).order_by("-sent_at")
        return ctx
