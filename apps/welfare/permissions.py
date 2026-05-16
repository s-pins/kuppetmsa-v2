"""Welfare permissions.

docs/permissions.md §5.7 defines a reviewer as: role in
WELFARE_REVIEWER_ROLES (== leadership) OR the welfare_officer flag.
Centralised here so the OR is implemented once.
"""

from __future__ import annotations

from rest_framework import permissions

from apps.core.constants import (
    FLAG_WELFARE_OFFICER,
    WELFARE_REVIEWER_ROLES,
)


class IsWelfareReviewer(permissions.BasePermission):
    message = "Welfare reviewer access (leadership or welfare officer) required."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False
        if user.role in WELFARE_REVIEWER_ROLES:
            return True
        return bool(getattr(user, FLAG_WELFARE_OFFICER, False))
