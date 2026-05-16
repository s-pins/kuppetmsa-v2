"""DRF serializers for the accounts app."""
from rest_framework import serializers

from apps.accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'role',
            'discipline_committee_member',
            'welfare_officer',
            'manifesto_editor',
            'is_2fa_enrolled',
        ]
        read_only_fields = [
            'id',
            'email',
            'role',
            'discipline_committee_member',
            'welfare_officer',
            'manifesto_editor',
            'is_2fa_enrolled',
        ]

    def get_full_name(self, obj) -> str:
        return obj.get_full_name()
