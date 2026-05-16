"""
View mixins for server-rendered Django views.

These cover the same ground as apps.core.permissions but for class-based
generic views. Same source of truth (apps.core.constants), two delivery
surfaces (DRF + Django views).

For function-based views, see apps.core.decorators.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils import timezone

from apps.core.constants import (
    DISCIPLINE_BASE_ROLES,
    FLAG_DISCIPLINE_COMMITTEE,
    RECENT_AUTH_WINDOW_SECONDS,
)


class RoleRequiredMixin(LoginRequiredMixin):
    """
    Require the user's role to be in `allowed_roles`.

    Subclasses set `allowed_roles` to a constant set from apps.core.constants.
    Never write a literal there.

    Usage:
        class MembersListView(RoleRequiredMixin, ListView):
            allowed_roles = LEADERSHIP_ROLES
    """

    allowed_roles: Iterable[str] = frozenset()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role not in self.allowed_roles:
            raise PermissionDenied('Your role does not have access to this page.')
        return super().dispatch(request, *args, **kwargs)


class FlagRequiredMixin(LoginRequiredMixin):
    """Require a boolean flag on the user."""

    required_flag: str = ''

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not getattr(request.user, self.required_flag, False):
            raise PermissionDenied('You do not have this capability enabled.')
        return super().dispatch(request, *args, **kwargs)


class TwoFactorRequiredMixin(LoginRequiredMixin):
    """Require completed 2FA enrollment."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not getattr(request.user, 'is_2fa_enrolled', False):
            raise PermissionDenied('2FA enrollment is required for this section.')
        return super().dispatch(request, *args, **kwargs)


class RecentAuthRequiredMixin(LoginRequiredMixin):
    """
    Require strong authentication within the last RECENT_AUTH_WINDOW_SECONDS.

    On miss, redirects to a re-auth view that re-prompts for password and
    returns the user here. (URL name 'accounts:reauth' assumed; wire in
    accounts/urls.py.)
    """

    reauth_url_name = 'accounts:reauth'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        cutoff = timezone.now() - timedelta(seconds=RECENT_AUTH_WINDOW_SECONDS)
        last = getattr(request.user, 'last_strong_auth_at', None)
        if last is None or last < cutoff:
            from django.shortcuts import redirect
            from django.urls import reverse
            return redirect(f"{reverse(self.reauth_url_name)}?next={request.path}")

        return super().dispatch(request, *args, **kwargs)


class DisciplineAccessMixin(LoginRequiredMixin):
    """
    Composite mixin for the entire discipline module.

    On miss: raises Http404, not PermissionDenied. We do not confirm to the
    caller that the page exists. Matches the IsDisciplineCommittee DRF
    permission's behaviour.

    Stacks: role-or-flag check, 2FA, recent auth.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            # For unauthenticated users we still 404 — never leak that the
            # discipline section exists.
            raise Http404()

        user = request.user
        role_ok = user.role in DISCIPLINE_BASE_ROLES or bool(
            getattr(user, FLAG_DISCIPLINE_COMMITTEE, False)
        )
        if not role_ok:
            raise Http404()

        if not getattr(user, 'is_2fa_enrolled', False):
            raise Http404()

        cutoff = timezone.now() - timedelta(seconds=RECENT_AUTH_WINDOW_SECONDS)
        last = getattr(user, 'last_strong_auth_at', None)
        if last is None or last < cutoff:
            # Authorized in principle but session is stale — redirect to reauth
            # rather than 404, since the user already has the role.
            from django.shortcuts import redirect
            from django.urls import reverse
            try:
                target = reverse('accounts:reauth')
                return redirect(f"{target}?next={request.path}")
            except Exception:
                raise Http404()

        return super().dispatch(request, *args, **kwargs)
