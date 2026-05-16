"""Portal access primitives.

Every portal endpoint must resolve to *the caller's own* member profile
and nothing else. Centralising that here means there is exactly one
place to audit for the "a member can only see their own data" invariant
(docs/permissions.md §5.2/§5.3/§5.4 "self" rows), rather than repeating
the check in every view.

The portal is a pure composition layer — it owns no models. It reads
data created/owned by the members, finances, events and reports apps,
always filtered to request.user.member_profile.
"""

from __future__ import annotations

from rest_framework import permissions
from rest_framework.exceptions import NotFound


class IsMemberWithProfile(permissions.BasePermission):
    """Authenticated AND linked to a Member row.

    An officer-only account with no member_profile is legitimately not a
    portal user; they get a clear 403 rather than a confusing empty
    dashboard.
    """

    message = "This account is not linked to a member profile."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False
        return getattr(user, "member_profile", None) is not None


class PortalScopedMixin:
    """Resolve the caller's own Member, or 404.

    404 (not 403) when the profile is missing on an otherwise-permitted
    path is deliberate: the resource being addressed is "my data", and
    if there is no member behind the account there is genuinely nothing
    at that address. Permission-level rejection is handled by
    IsMemberWithProfile on endpoints that require it.
    """

    permission_classes = [IsMemberWithProfile]

    @property
    def member(self):
        m = getattr(self.request.user, "member_profile", None)
        if m is None:
            raise NotFound("No member profile linked to this account.")
        return m
