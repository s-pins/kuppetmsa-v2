"""
Custom schema generation for drf-spectacular.

Two responsibilities:

1. `filter_schema_for_user`: a preprocessing hook that strips endpoint paths
   from the generated OpenAPI schema based on the requesting user's role.
   This is *defence in depth* on top of the permission classes: even if a
   user could reach /api/schema/, they will not see endpoints they cannot
   call. For the discipline module this is the difference between "they
   know cases exist but can't reach them" and "they have no evidence
   cases exist at all".

2. Tagging conventions for grouping endpoints in Swagger UI.

Usage: wired in config/settings/base.py under SPECTACULAR_SETTINGS.
"""
from __future__ import annotations

from typing import Any

from apps.core.constants import (
    DISCIPLINE_BASE_ROLES,
    FLAG_DISCIPLINE_COMMITTEE,
)

# Paths that get stripped if the user is not a discipline-committee member.
DISCIPLINE_PATH_PREFIXES = ('/api/v1/discipline/',)


def _user_can_see_discipline(user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    role_ok = user.role in DISCIPLINE_BASE_ROLES or bool(
        getattr(user, FLAG_DISCIPLINE_COMMITTEE, False)
    )
    return role_ok


def filter_schema_for_user(endpoints, **kwargs):  # noqa: ARG001
    """Preprocessing hook: drop sensitive endpoints from the schema.

    drf-spectacular preprocessing hooks receive a list of
    (path, path_regex, method, callback) tuples and return a (possibly
    filtered) list.

    The request lives in thread-local state during schema generation —
    drf-spectacular sets it on the generator. We pull it out and inspect
    user.role.
    """
    # Lazy import to avoid Django-not-ready issues at module load.
    from drf_spectacular.drainage import get_override  # noqa: F401  (kept for parity)

    request = kwargs.get('request')
    user = getattr(request, 'user', None) if request is not None else None

    if _user_can_see_discipline(user):
        return endpoints

    return [
        (path, path_regex, method, callback)
        for (path, path_regex, method, callback) in endpoints
        if not any(path.startswith(p) for p in DISCIPLINE_PATH_PREFIXES)
    ]
