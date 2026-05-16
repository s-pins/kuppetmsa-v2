"""Audit-log registration for reports."""

from auditlog.registry import auditlog

from apps.reports.models import Report

auditlog.register(Report, exclude_fields=["created_at", "updated_at"])
