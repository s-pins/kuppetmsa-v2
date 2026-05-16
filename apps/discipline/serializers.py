"""Discipline serializers — docs/permissions.md §5.8.

Two audiences, very different exposure:

  Committee  : full case incl. decrypted summary + action notes.
  Subject    : a member may see THAT they have a case and its
               status/outcome, but NEVER the summary, the internal
               investigation notes, or who recorded what. The redacted
               serializer simply does not include those fields — they
               are never serialised toward the subject at all.
"""

from rest_framework import serializers

from apps.discipline.models import DisciplinaryAction, DisciplinaryCase


class DisciplinaryActionSerializer(serializers.ModelSerializer):
    recorded_by_email = serializers.CharField(source="recorded_by.email", read_only=True)

    class Meta:
        model = DisciplinaryAction
        fields = [
            "id",
            "case",
            "action_type",
            "notes",
            "recorded_by",
            "recorded_by_email",
            "created_at",
        ]
        read_only_fields = ["id", "recorded_by", "created_at"]


class DisciplinaryCaseSerializer(serializers.ModelSerializer):
    """Committee full view."""

    subject_name = serializers.CharField(source="subject.full_name", read_only=True)
    actions = DisciplinaryActionSerializer(many=True, read_only=True)

    class Meta:
        model = DisciplinaryCase
        fields = [
            "id",
            "case_number",
            "subject",
            "subject_name",
            "category",
            "summary",
            "status",
            "outcome",
            "opened_by",
            "opened_at",
            "closed_at",
            "actions",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "case_number",
            "opened_by",
            "opened_at",
            "closed_at",
            "created_at",
        ]


class DisciplinaryCaseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisciplinaryCase
        fields = ["id", "subject", "category", "summary"]
        read_only_fields = ["id"]


class MyCaseSummarySerializer(serializers.ModelSerializer):
    """The subject's own redacted view.

    Deliberately omits: summary, actions, opened_by. The subject learns
    a case exists, its category, status and final outcome — nothing of
    the deliberative record. Field-level omission (not blanking) means
    the sensitive data never enters the response payload.
    """

    class Meta:
        model = DisciplinaryCase
        fields = [
            "case_number",
            "category",
            "status",
            "outcome",
            "opened_at",
            "closed_at",
        ]
        read_only_fields = fields
