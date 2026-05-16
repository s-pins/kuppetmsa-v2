"""Audit-log registration for projects.

Projects move money (budgets, linked expenses) so changes are tracked.
"""

from auditlog.registry import auditlog

from apps.projects.models import Project

auditlog.register(Project, exclude_fields=["created_at", "updated_at"])
