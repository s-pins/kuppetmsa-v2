"""Public-site tests — the inverse of the discipline suite.

Discipline proved "sensitive data is hidden". This proves "ONLY
explicitly-public data is exposed". Every test that matters here is a
leak-prevention test: it creates a non-public record and asserts it
does NOT appear on the public surface, alongside a public record that
DOES.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.communications.models import (
    Announcement,
    AnnouncementStatus,
    AudienceScope,
)
from apps.core.constants import ROLE_CHAIRPERSON
from apps.members.models import Member
from apps.projects.models import Project
from apps.reports.models import Report

pytestmark = pytest.mark.django_db


@pytest.fixture
def author(django_user_model):
    return django_user_model.objects.create_user(
        email="chair@example.com",
        password="StrongPass-12345",
        role=ROLE_CHAIRPERSON,
    )


def _pdf(name="r.pdf"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, b"%PDF-1.4 minimal", content_type="application/pdf")


PROJECTS = "/api/v1/public/projects/"
REPORTS = "/api/v1/public/reports/"
NEWS = "/api/v1/public/news/"
OVERVIEW = "/api/v1/public/overview/"


class TestPublicAccessIsAnonymous:
    def test_all_endpoints_allow_anonymous(self):
        c = APIClient()
        for url in (PROJECTS, REPORTS, NEWS, OVERVIEW):
            assert c.get(url).status_code == 200, url


class TestProjectLeakPrevention:
    def test_internal_project_not_exposed(self):
        Project.objects.create(
            name="Public Borehole",
            slug="public-borehole",
            budget_kes=Decimal("100000"),
            is_public=True,
        )
        Project.objects.create(
            name="SECRET Internal Restructure",
            slug="secret-internal",
            budget_kes=Decimal("50000"),
            is_public=False,
        )
        resp = APIClient().get(PROJECTS)
        names = [p["name"] for p in resp.data["results"]]
        assert "Public Borehole" in names
        assert "SECRET Internal Restructure" not in names
        assert "SECRET" not in str(resp.data)

    def test_public_project_payload_has_no_internal_fields(self):
        Project.objects.create(
            name="P",
            slug="p",
            budget_kes=Decimal("1000"),
            is_public=True,
        )
        row = APIClient().get(PROJECTS).data["results"][0]
        for forbidden in ("created_by", "id", "is_public", "created_at"):
            assert forbidden not in row


class TestReportLeakPrevention:
    def test_draft_report_not_exposed(self, author):
        Report.objects.create(
            title="Published Audit 2025",
            year=2025,
            file=_pdf(),
            uploaded_by=author,
            is_published=True,
        )
        Report.objects.create(
            title="DRAFT Internal Memo",
            year=2025,
            file=_pdf("d.pdf"),
            uploaded_by=author,
            is_published=False,
        )
        resp = APIClient().get(REPORTS)
        titles = [r["title"] for r in resp.data["results"]]
        assert "Published Audit 2025" in titles
        assert "DRAFT Internal Memo" not in titles

    def test_public_report_has_no_uploader_field(self, author):
        Report.objects.create(
            title="T",
            year=2025,
            file=_pdf(),
            uploaded_by=author,
            is_published=True,
        )
        row = APIClient().get(REPORTS).data["results"][0]
        assert "uploaded_by" not in row


class TestNewsLeakPrevention:
    """The subtlest leak risk: a member announcement is NOT public news.
    Only is_public AND sent appears."""

    def test_member_announcement_not_public_even_when_sent(self, author):
        # Sent to all members, but NOT flagged public -> not news.
        a = Announcement.objects.create(
            title="Internal: dues reminder",
            body="Members only.",
            audience_scope=AudienceScope.ALL_MEMBERS,
            created_by=author,
            is_public=False,
        )
        a.status = AnnouncementStatus.SENT
        a.save(update_fields=["status"])

        resp = APIClient().get(NEWS)
        titles = [n["title"] for n in resp.data["results"]]
        assert "Internal: dues reminder" not in titles

    def test_public_but_unsent_draft_not_shown(self, author):
        # Flagged public but still a DRAFT -> must not leak early.
        Announcement.objects.create(
            title="Embargoed press release",
            body="Not yet.",
            audience_scope=AudienceScope.ALL_MEMBERS,
            created_by=author,
            is_public=True,
            status=AnnouncementStatus.DRAFT,
        )
        resp = APIClient().get(NEWS)
        titles = [n["title"] for n in resp.data["results"]]
        assert "Embargoed press release" not in titles

    def test_public_and_sent_announcement_is_news(self, author):
        a = Announcement.objects.create(
            title="AGM open to the public",
            body="All welcome on Saturday.",
            audience_scope=AudienceScope.ALL_MEMBERS,
            created_by=author,
            is_public=True,
        )
        a.status = AnnouncementStatus.SENT
        a.save(update_fields=["status"])

        resp = APIClient().get(NEWS)
        titles = [n["title"] for n in resp.data["results"]]
        assert "AGM open to the public" in titles
        # And no operational metadata rides along.
        row = resp.data["results"][0]
        for forbidden in (
            "created_by",
            "recipient_count",
            "audience_scope",
            "status",
        ):
            assert forbidden not in row


class TestNoMemberPIIAnywhere:
    def test_member_data_never_on_public_surface(self, author):
        Member.objects.create(
            tsc_number="TSC-SECRET-123",
            first_name="Private",
            last_name="Person",
            phone="0700000000",
        )
        Project.objects.create(name="P", slug="p", budget_kes=Decimal("1"), is_public=True)
        for url in (PROJECTS, REPORTS, NEWS, OVERVIEW):
            blob = str(APIClient().get(url).data)
            assert "TSC-SECRET-123" not in blob
            assert "0700000000" not in blob


class TestOverviewComposition:
    def test_overview_composes_only_public(self, author):
        Project.objects.create(name="Pub", slug="pub", budget_kes=Decimal("1"), is_public=True)
        Project.objects.create(
            name="Hidden",
            slug="hidden",
            budget_kes=Decimal("1"),
            is_public=False,
        )
        a = Announcement.objects.create(
            title="Public news",
            body="x",
            audience_scope=AudienceScope.ALL_MEMBERS,
            created_by=author,
            is_public=True,
        )
        a.status = AnnouncementStatus.SENT
        a.save(update_fields=["status"])

        data = APIClient().get(OVERVIEW).data
        proj_names = [p["name"] for p in data["recent_projects"]]
        assert "Pub" in proj_names
        assert "Hidden" not in proj_names
        assert any(n["title"] == "Public news" for n in data["recent_news"])
