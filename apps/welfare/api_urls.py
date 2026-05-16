"""API routes for the welfare app."""

from rest_framework.routers import DefaultRouter

from apps.welfare.views import WelfareClaimViewSet, WelfareReviewViewSet

app_name = "welfare"

router = DefaultRouter()
router.register("claims", WelfareClaimViewSet, basename="claim")
router.register("review", WelfareReviewViewSet, basename="review")

urlpatterns = router.urls
