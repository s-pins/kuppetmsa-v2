"""Report API tests — docs/permissions.md §5.6 + upload validation."""

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.core.constants import (
    ROLE_CHAIRPERSON,
    ROLE_MEMBER,
    ROLE_ORGANIZING_SECRETARY,
)
from apps.reports.models import Report, validate_report_size

pytestmark = pytest.mark.django_db


@pytest.fixture
def make_user(django_user_model):
    n = {"i": 0}

    def _make(role=ROLE_MEMBER):
        n["i"] += 1
        return django_user_model.objects.create_user(
            email=f"{role}-{n['i']}@example.com",
            password="StrongPass-12345",
            role=role,
        )

    return _make


def _pdf(name="r.pdf", size=1024):
    return SimpleUploadedFile(name, b"%PDF-1.4\n" + b"0" * size, content_type="application/pdf")


R_URL = "/api/v1/reports/"


class TestReportVisibility:
    def test_anonymous_sees_only_published(self, make_user):
        officer = make_user(ROLE_ORGANIZING_SECRETARY)
        Report.objects.create(title="Draft", year=2026, file=_pdf(), uploaded_by=officer)
        Report.objects.create(
            title="Live",
            year=2026,
            file=_pdf(),
            uploaded_by=officer,
            is_published=True,
        )
        resp = APIClient().get(R_URL)
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["title"] == "Live"

    def test_officer_sees_own_drafts(self, make_user):
        officer = make_user(ROLE_ORGANIZING_SECRETARY)
        Report.objects.create(title="MyDraft", year=2026, file=_pdf(), uploaded_by=officer)
        c = APIClient()
        c.force_authenticate(officer)
        assert c.get(R_URL).data["count"] == 1


class TestReportUploadAndPublish:
    def test_member_cannot_upload(self, make_user):
        c = APIClient()
        c.force_authenticate(make_user(ROLE_MEMBER))
        resp = c.post(
            R_URL,
            {"title": "X", "year": 2026, "file": _pdf()},
            format="multipart",
        )
        assert resp.status_code == 403

    def test_officer_can_upload_but_not_publish(self, make_user):
        officer = make_user(ROLE_ORGANIZING_SECRETARY)
        c = APIClient()
        c.force_authenticate(officer)
        created = c.post(
            R_URL,
            {"title": "Activity", "year": 2026, "file": _pdf()},
            format="multipart",
        )
        assert created.status_code == 201
        assert created.data["is_published"] is False
        rid = created.data["id"]
        # Officer cannot publish (leadership only).
        pub = c.post(f"{R_URL}{rid}/publish/", {}, format="json")
        assert pub.status_code == 403

    def test_chairperson_can_publish(self, make_user):
        officer = make_user(ROLE_ORGANIZING_SECRETARY)
        chair = make_user(ROLE_CHAIRPERSON)
        r = Report.objects.create(title="Audit", year=2026, file=_pdf(), uploaded_by=officer)
        c = APIClient()
        c.force_authenticate(chair)
        resp = c.post(f"{R_URL}{r.pk}/publish/", {}, format="json")
        assert resp.status_code == 200
        r.refresh_from_db()
        assert r.is_published is True


class TestFileValidation:
    def test_size_validator_rejects_oversize(self):
        big = SimpleUploadedFile("big.pdf", b"x")
        big.size = 11 * 1024 * 1024  # 11MB
        with pytest.raises(ValidationError):
            validate_report_size(big)

    def test_size_validator_accepts_normal(self):
        ok = SimpleUploadedFile("ok.pdf", b"x")
        ok.size = 1024
        validate_report_size(ok)  # no raise

    def test_bad_extension_rejected_on_full_clean(self, make_user):
        officer = make_user(ROLE_ORGANIZING_SECRETARY)
        bad = SimpleUploadedFile("evil.exe", b"MZ", content_type="application/octet-stream")
        report = Report(title="X", year=2026, file=bad, uploaded_by=officer)
        with pytest.raises(ValidationError):
            report.full_clean()
