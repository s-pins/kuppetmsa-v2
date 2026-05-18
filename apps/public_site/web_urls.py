"""Server-rendered public website routes."""

from django.urls import path

from apps.public_site.web_views import (
    HomeView,
    NewsView,
    ProjectsView,
    ReportsView,
    TransparencyView,
)

app_name = "public_site_web"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("transparency/", TransparencyView.as_view(), name="transparency"),
    path("projects/", ProjectsView.as_view(), name="projects"),
    path("reports/", ReportsView.as_view(), name="reports"),
    path("news/", NewsView.as_view(), name="news"),
]
