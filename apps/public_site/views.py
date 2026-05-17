"""Public-site API — the unauthenticated outward face.

Every view here is AllowAny and READ-ONLY. The single security concern
is leak prevention: a non-public record (draft report, internal/
non-public project, member PII, unsent or non-public announcement) must
never appear. Defence is at the queryset level — each queryset starts
from the most restrictive filter, never the full table.

This app owns no models; it composes the already-public surfaces
(finances transparency from Phase 2, projects, reports) plus the
explicitly-public announcements added in Phase 9.
"""

from __future__ import annotations

from rest_framework import generics, permissions, response, views

from apps.communications.models import Announcement, AnnouncementStatus
from apps.projects.models import Project
from apps.public_site.serializers import (
    PublicAnnouncementSerializer,
    PublicProjectSerializer,
    PublicReportSerializer,
)
from apps.reports.models import Report


class PublicProjectListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PublicProjectSerializer

    def get_queryset(self):
        # Only is_public projects. Never the full table.
        return Project.objects.filter(is_public=True).order_by("-started_on", "name")


class PublicReportListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PublicReportSerializer
    filterset_fields = ["category", "year"]

    def get_queryset(self):
        # Only published reports. Drafts never surface.
        return Report.objects.filter(is_published=True).order_by("-year", "-created_at")


class PublicNewsListView(generics.ListAPIView):
    """Public news = announcements explicitly opted public AND sent.

    Both conditions are required and AND-ed at the queryset level:
    is_public was a conscious comms-officer choice, and SENT means it
    actually went out (no leaking drafts).
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = PublicAnnouncementSerializer

    def get_queryset(self):
        return Announcement.objects.filter(
            is_public=True,
            status=AnnouncementStatus.SENT,
        ).order_by("-sent_at")


class PublicOverviewView(views.APIView):
    """A single composite for the public landing page.

    Pure read aggregation over the already-public surfaces. No new data
    is exposed here that isn't independently available on the dedicated
    public endpoints; this is a convenience composition only.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        projects = Project.objects.filter(is_public=True).order_by("-started_on")[:5]
        reports = Report.objects.filter(is_published=True).order_by("-year")[:5]
        news = Announcement.objects.filter(is_public=True, status=AnnouncementStatus.SENT).order_by(
            "-sent_at"
        )[:5]

        return response.Response(
            {
                "recent_projects": PublicProjectSerializer(projects, many=True).data,
                "recent_reports": PublicReportSerializer(reports, many=True).data,
                "recent_news": PublicAnnouncementSerializer(news, many=True).data,
            }
        )
