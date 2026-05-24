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

    def test_announcement_image_appears_on_public_news(self, author):
        """An instructional / poster announcement carries its image
        and alt text to the public news payload."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        # 1x1 valid PNG so ImageField accepts the upload in tests
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
            b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0"
            b"\x00\x00\x00\x03\x00\x01\x86\x14\x9b\xb0\x00\x00\x00"
            b"\x00IEND\xaeB`\x82"
        )
        a = Announcement.objects.create(
            title="How to switch to full membership",
            body="Follow these steps.",
            audience_scope=AudienceScope.ALL_MEMBERS,
            created_by=author,
            is_public=True,
            image=SimpleUploadedFile("guide.png", png_bytes, content_type="image/png"),
            image_alt="Step-by-step T-Pay membership switch",
        )
        a.status = AnnouncementStatus.SENT
        a.save(update_fields=["status"])

        row = APIClient().get(NEWS).data["results"][0]
        # Image URL and alt are present on the public payload.
        assert row.get("image"), "image url missing on public news"
        assert "guide" in row["image"]
        assert row["image_alt"] == "Step-by-step T-Pay membership switch"

    def test_text_only_announcement_has_null_image(self, author):
        """A text announcement (no image uploaded) returns a null image
        field on the public payload — the absence of an image is itself
        information for clients deciding whether to render a figure."""
        a = Announcement.objects.create(
            title="Plain text notice",
            body="Just words.",
            audience_scope=AudienceScope.ALL_MEMBERS,
            created_by=author,
            is_public=True,
        )
        a.status = AnnouncementStatus.SENT
        a.save(update_fields=["status"])
        row = APIClient().get(NEWS).data["results"][0]
        assert row.get("image") in (None, "")


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


class TestHomeLatestStrip:
    """The home page's Latest strip uses round-robin merge so a noisier
    source can't crowd out the others. This is what makes refreshing
    the home page reward the visitor with fresh content of every kind."""

    def test_round_robin_guarantees_mix(self, author):
        from apps.public_site.models import ElectionNotice

        # Suppress the modal for this test — we just want home content.
        ElectionNotice.objects.all().delete()

        # 6 reports + 6 projects all created AFTER 6 news, so a naive
        # date-sort would put zero news in the top 6.
        for i in range(6):
            a = Announcement.objects.create(
                title=f"News {i}",
                body="x",
                audience_scope=AudienceScope.ALL_MEMBERS,
                created_by=author,
                is_public=True,
            )
            a.status = AnnouncementStatus.SENT
            a.save(update_fields=["status"])
        for i in range(6):
            Project.objects.create(
                name=f"Project {i}",
                slug=f"p{i}",
                budget_kes=Decimal("1"),
                is_public=True,
            )
        for i in range(6):
            Report.objects.create(
                title=f"Report {i}",
                year=2026,
                file=_pdf(f"r{i}.pdf"),
                uploaded_by=author,
                is_published=True,
            )

        resp = APIClient().get("/")
        assert resp.status_code == 200
        body = resp.content.decode()
        # All three kinds must appear in the Latest strip. Use the
        # latest-grid container as the anchor (less brittle than the
        # outer section's class string, which is "band latest-band").
        import re

        m = re.search(r'latest-grid".*?</section>', body, re.S)
        assert m, "latest strip not found in rendered home"
        strip = m.group(0)
        assert 'class="latest-label">News' in strip, "no News in Latest"
        assert 'class="latest-label">Project' in strip, "no Project in Latest"
        assert 'class="latest-label">Report' in strip, "no Report in Latest"


class TestElectionNoticeVersionedDismiss:
    """The modal's session-dismiss key is built from notice.id +
    updated_at, so editing the notice invalidates prior dismissals.
    A user who dismissed v1 will see v2 pop on next page load."""

    def test_version_changes_on_edit(self, author):
        from apps.public_site.models import ElectionNotice

        n = ElectionNotice.objects.create(title="v1", body="b", is_active=True)
        body1 = APIClient().get("/").content.decode()
        import re

        v1 = re.search(r'var noticeVersion = "([^"]+)"', body1)
        assert v1, "noticeVersion missing on render"
        v1_key = v1.group(1)

        # Editing the notice bumps updated_at (model has auto_now=True).
        import time

        time.sleep(1.1)
        n.title = "v2"
        n.save()

        body2 = APIClient().get("/").content.decode()
        v2 = re.search(r'var noticeVersion = "([^"]+)"', body2)
        assert v2
        v2_key = v2.group(1)
        assert v1_key != v2_key, (
            "noticeVersion should change after edit so a dismissed "
            "key is invalidated and the modal re-pops"
        )
