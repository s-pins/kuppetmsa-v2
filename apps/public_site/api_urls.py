"""API routes for the public site (all AllowAny, read-only)."""

from django.urls import path

from apps.public_site.views import (
    PublicNewsListView,
    PublicOverviewView,
    PublicProjectListView,
    PublicReportListView,
)

app_name = "public_site"

urlpatterns = [
    path("overview/", PublicOverviewView.as_view(), name="overview"),
    path("projects/", PublicProjectListView.as_view(), name="projects"),
    path("reports/", PublicReportListView.as_view(), name="reports"),
    path("news/", PublicNewsListView.as_view(), name="news"),
]
