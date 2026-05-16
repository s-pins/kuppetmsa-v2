"""Member serializers.

Three serializers map to three rows of docs/permissions.md §5.2:

  - PublicMemberSerializer  : directory view, name + school only
  - MemberSerializer        : full record, officers/leadership
  - MemberSelfSerializer    : safe-field self-edit (member editing own profile)
"""

from rest_framework import serializers

from apps.members.models import Member


class PublicMemberSerializer(serializers.ModelSerializer):
    """Anonymous / member directory view. No PII."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Member
        fields = ["id", "full_name", "school", "sub_county"]
        read_only_fields = fields


class MemberSerializer(serializers.ModelSerializer):
    """Full record — officers and leadership only."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Member
        fields = [
            "id",
            "membership_id",
            "tsc_number",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "email",
            "school",
            "sub_county",
            "ward",
            "bio",
            "photo",
            "is_active",
            "joined_on",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["membership_id", "created_at", "updated_at"]


class MemberSelfSerializer(serializers.ModelSerializer):
    """A member editing their own profile.

    Only the safe fields from the matrix: contact, photo, bio. Everything
    else (TSC number, active status, names) is admin-managed.
    """

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Member
        fields = [
            "id",
            "membership_id",
            "full_name",
            "phone",
            "email",
            "bio",
            "photo",
            "school",
            "sub_county",
            "ward",
        ]
        read_only_fields = ["id", "membership_id", "full_name"]
