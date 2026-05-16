"""API routes for the member portal.

No router — these are singular, self-scoped views, not a CRUD resource
collection.
"""

from django.urls import path

from apps.portal.views import (
    DashboardView,
    MyContributionsView,
    MyEventsView,
)

app_name = "portal"

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path(
        "my-contributions/",
        MyContributionsView.as_view(),
        name="my-contributions",
    ),
    path("my-events/", MyEventsView.as_view(), name="my-events"),
]
