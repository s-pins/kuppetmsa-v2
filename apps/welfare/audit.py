"""Audit-log registration for welfare.

Welfare claims move money. Every status transition (submit -> review ->
decide -> pay) and the reviewer/expense links are part of the trail.
"""

from auditlog.registry import auditlog

from apps.welfare.models import WelfareClaim

auditlog.register(WelfareClaim, exclude_fields=["created_at", "updated_at"])
