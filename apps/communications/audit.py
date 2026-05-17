"""Audit-log registration for communications.

Announcements are an official record of what the branch told members
and when. Notifications are high-volume per-member rows — not audited
individually (the announcement + recipient_count is the trail).
"""

from auditlog.registry import auditlog

from apps.communications.models import Announcement

auditlog.register(Announcement, exclude_fields=["created_at", "updated_at"])
