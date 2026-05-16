"""API routes for the members app."""
from rest_framework.routers import DefaultRouter

from apps.members.views import MemberViewSet

app_name = 'members'

router = DefaultRouter()
router.register('members', MemberViewSet, basename='member')

urlpatterns = router.urls
