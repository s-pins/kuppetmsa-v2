"""Project serializers.

The public serializer intentionally includes spent_kes / variance_kes —
budget transparency is the whole point of exposing projects publicly
(docs/permissions.md §5.5).
"""

from rest_framework import serializers

from apps.projects.models import Project


class ProjectSerializer(serializers.ModelSerializer):
    spent_kes = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    variance_kes = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
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
            "is_public",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
