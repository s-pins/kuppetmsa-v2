"""API routes for the events app."""

from rest_framework.routers import DefaultRouter

from apps.events.views import EventViewSet

app_name = "events"

router = DefaultRouter()
router.register("events", EventViewSet, basename="event")

urlpatterns = router.urls
