"""
DRF permission classes.

These are the only things that should check `user.role` or `user.<flag>`.
Views import these and compose them; they never inspect user attributes
directly. This keeps the permissions matrix and the running code in sync —
if you don't see a permission class for an action, the action isn't permitted.

Composition uses DRF's `&`, `|`, `~` operators on BasePermission subclasses.
Example:
    permission_classes = [
        IsAuthenticated &
        HasAnyRole(FINANCE_WRITE_ROLES) &
        Is2FAEnrolled &
        RecentAuthRequired
    ]
"""
from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from django.utils import timezone
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.core.constants import (
    DISCIPLINE_BASE_ROLES,
    FLAG_DISCIPLINE_COMMITTEE,
    OFFICER_ROLES,
    RECENT_AUTH_WINDOW_SECONDS,
)


def _user_authenticated(request: Request) -> bool:
    user = getattr(request, 'user', None)
    return bool(user and user.is_authenticated)


class HasAnyRole(permissions.BasePermission):
    """Permit users whose `role` is in the supplied set.

    Usage:
        class FooView(APIView):
            permission_classes = [IsAuthenticated, HasAnyRole(LEADERSHIP_ROLES)]

    Note: this returns a *factory* — DRF will instantiate it per request, so
    we wrap it so the configured role set survives instantiation.
    """

    def __new__(cls, allowed_roles: Iterable[str] | None = None):
        if allowed_roles is None:
            # DRF instantiating us at request-time; return a plain instance.
            return super().__new__(cls)
        # Caller is configuring at view-definition time: build a subclass.
        roles = frozenset(allowed_roles)
        subclass = type(
            f'HasAnyRole_{"_".join(sorted(roles))[:60]}',
            (cls,),
            {'_allowed_roles': roles},
        )
        return subclass

    _allowed_roles: frozenset = frozenset()

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not _user_authenticated(request):
            return False
        return request.user.role in self._allowed_roles


class HasFlag(permissions.BasePermission):
    """Permit users whose boolean flag attribute is True."""

    def __new__(cls, flag_name: str | None = None):
        if flag_name is None:
            return super().__new__(cls)
        subclass = type(
            f'HasFlag_{flag_name}',
            (cls,),
            {'_flag_name': flag_name},
        )
        return subclass

    _flag_name: str = ''

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not _user_authenticated(request):
            return False
        return bool(getattr(request.user, self._flag_name, False))


class Is2FAEnrolled(permissions.BasePermission):
    """Permit only users who have completed 2FA enrollment.

    Required for finance writes and the entire discipline module.
    """

    message = '2FA enrollment is required for this action.'

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not _user_authenticated(request):
            return False
        return bool(getattr(request.user, 'is_2fa_enrolled', False))


class RecentAuthRequired(permissions.BasePermission):
    """Permit only requests where the user authenticated recently.

    "Recently" = within RECENT_AUTH_WINDOW_SECONDS. The check reads
    `request.user.last_strong_auth_at`, which is updated on login and
    on explicit re-authentication endpoints.

    For JWT requests, also accepts the token's `iat` claim as a proxy
    if last_strong_auth_at is older — this lets a freshly-issued token
    satisfy the requirement without a separate re-auth step.
    """

    message = 'Recent authentication is required. Please re-enter your password.'

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not _user_authenticated(request):
            return False

        cutoff = timezone.now() - timedelta(seconds=RECENT_AUTH_WINDOW_SECONDS)

        last = getattr(request.user, 'last_strong_auth_at', None)
        if last and last >= cutoff:
            return True

        # Fall back to JWT iat if present.
        auth = getattr(request, 'auth', None)
        if auth is not None:
            iat = getattr(auth, 'payload', {}).get('iat') if hasattr(auth, 'payload') else None
            if iat:
                from datetime import datetime, timezone as dt_tz
                token_issued_at = datetime.fromtimestamp(iat, tz=dt_tz.utc)
                if token_issued_at >= cutoff:
                    return True

        return False


class IsObjectOwner(permissions.BasePermission):
    """Object-level: permit if the object's owner is the request user.

    Subclasses override `owner_attr` to point at the FK chain on the
    object that resolves to a User instance.
    """

    owner_attr = 'user'

    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        if not _user_authenticated(request):
            return False
        owner = obj
        for part in self.owner_attr.split('.'):
            owner = getattr(owner, part, None)
            if owner is None:
                return False
        return owner == request.user


class IsDisciplineCommittee(permissions.BasePermission):
    """
    Composite check for any discipline endpoint.

    Equivalent to: role in DISCIPLINE_BASE_ROLES OR has discipline_committee_member flag,
    AND 2FA enrolled, AND recent auth.

    We bundle the three conditions into one class because they always travel
    together for this module. If any fails, we return False — and the view
    should be wired to render a 404, not a 403, to avoid confirming the
    endpoint's existence to unauthorized callers.
    """

    message = 'Not found.'  # See above — we mask as 404 at the view layer.

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not _user_authenticated(request):
            return False

        user = request.user
        role_ok = user.role in DISCIPLINE_BASE_ROLES or bool(
            getattr(user, FLAG_DISCIPLINE_COMMITTEE, False)
        )
        if not role_ok:
            return False
        if not getattr(user, 'is_2fa_enrolled', False):
            return False

        # Inline RecentAuthRequired check to avoid permission-class composition cost.
        cutoff = timezone.now() - timedelta(seconds=RECENT_AUTH_WINDOW_SECONDS)
        last = getattr(user, 'last_strong_auth_at', None)
        if last and last >= cutoff:
            return True

        auth = getattr(request, 'auth', None)
        if auth is not None and hasattr(auth, 'payload'):
            iat = auth.payload.get('iat')
            if iat:
                from datetime import datetime, timezone as dt_tz
                if datetime.fromtimestamp(iat, tz=dt_tz.utc) >= cutoff:
                    return True

        return False


class IsOfficer(permissions.BasePermission):
    """Gate Swagger UI and other officer-only meta-endpoints."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not _user_authenticated(request):
            return False
        return request.user.role in OFFICER_ROLES
