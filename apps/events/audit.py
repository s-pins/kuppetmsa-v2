"""Audit-log registration for events."""

from auditlog.registry import auditlog

from apps.events.models import Event, EventAttendance

auditlog.register(Event, exclude_fields=["created_at", "updated_at"])
auditlog.register(EventAttendance, exclude_fields=["created_at", "updated_at"])
