"""Server-rendered URLs for the accounts app.

Provides the `accounts:reauth` route referenced by RecentAuthRequiredMixin
and DisciplineAccessMixin, then delegates login / logout / signup /
email-verify / password-reset / MFA to allauth.

Note: allauth's own URLs are NOT namespaced (they use names like
`account_login`, `account_signup`). Only `reauth` lives under the
`accounts:` namespace.
"""
from django.urls import include, path

from apps.accounts.auth_views import ReauthView

app_name = 'accounts'

urlpatterns = [
    path('reauth/', ReauthView.as_view(), name='reauth'),
]

# allauth routes are included at the project level (see config/urls.py)
# because they must remain un-namespaced for allauth's reverse() calls.
