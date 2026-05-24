"""Public-site serializers.

Every serializer here is a deliberately NARROW projection. The design
rule for Phase 9 is the inverse of the discipline module: instead of
"hide what's sensitive", it is "expose ONLY an explicit allowlist of
fields, never a model's full field set". Field-omission (not blanking)
guarantees nothing internal can ride along on the public surface even
if a model later grows new fields.
"""

from rest_framework import serializers

from apps.communications.models import Announcement
from apps.projects.models import Project
from apps.reports.models import Report


class PublicProjectSerializer(serializers.ModelSerializer):
    spent_kes = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    variance_kes = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Project
        # No internal notes, no created_by, no audit fields.
        fields = [
            "name",
            "slug",
            "description",
            "status",
            "budget_kes",
            "spent_kes",
            "variance_kes",
            "started_on",
            "ended_on",
            "beneficiaries",
        ]
        read_only_fields = fields


class PublicReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        # No uploaded_by, no internal flags beyond what's needed.
        fields = ["title", "category", "year", "description", "file"]
        read_only_fields = fields


class PublicAnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        # Title/body/image/date only. Image is OPT-IN per the Phase 9
        # allowlist pattern — added consciously because instructional
        # graphics are content the public should see. No created_by, no
        # audience spec, no recipient_count.
        fields = ["title", "body", "image", "image_alt", "sent_at"]
        read_only_fields = fields
