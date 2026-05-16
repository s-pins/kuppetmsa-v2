"""Report model with strict upload validation.

docs/PLAN.md NFR + docs/permissions.md §5.6: report uploads must be
extension-whitelisted and size-capped. We validate on the model field
(so admin uploads are checked too, not only API) and we check the real
extension, not just trust the client.

The 10MB cap here is independent of DATA_UPLOAD_MAX_MEMORY_SIZE (5MB,
set in settings) — large reports are streamed to disk, so the field
validator is the effective limit for this file type.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

ALLOWED_REPORT_EXTENSIONS = ["pdf", "doc", "docx"]
MAX_REPORT_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_report_size(f) -> None:
    if f.size and f.size > MAX_REPORT_BYTES:
        raise ValidationError(f"Report exceeds the {MAX_REPORT_BYTES // (1024 * 1024)}MB limit.")


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ReportCategory(models.TextChoices):
    FINANCIAL = "financial", "Financial report"
    AGM = "agm", "AGM minutes"
    AUDIT = "audit", "Audit report"
    ACTIVITY = "activity", "Activity report"
    CIRCULAR = "circular", "Circular / notice"
    OTHER = "other", "Other"


class Report(TimeStampedModel):
    title = models.CharField(max_length=200)
    category = models.CharField(
        max_length=12,
        choices=ReportCategory.choices,
        default=ReportCategory.OTHER,
    )
    year = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    file = models.FileField(
        upload_to="reports/%Y/",
        validators=[
            FileExtensionValidator(ALLOWED_REPORT_EXTENSIONS),
            validate_report_size,
        ],
    )
    is_published = models.BooleanField(
        default=False,
        help_text="Published reports are visible to the public.",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_reports",
    )

    class Meta:
        ordering = ("-year", "-created_at")
        indexes = [models.Index(fields=["is_published", "year"])]

    def __str__(self) -> str:
        return f"{self.title} ({self.year})"
