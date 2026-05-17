"""API routes for the communications app."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.communications.views import (
    AnnouncementViewSet,
    MarkNotificationReadView,
    MyInboxView,
)

app_name = "communications"

router = DefaultRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")

urlpatterns = [
    path("inbox/", MyInboxView.as_view(), name="inbox"),
    path(
        "inbox/<int:pk>/read/",
        MarkNotificationReadView.as_view(),
        name="mark-read",
    ),
    *router.urls,
]
