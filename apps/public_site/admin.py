"""Admin for the public site.

Only the ElectionNotice is editable here — the campaign content the
client controls. The `is_active` master switch is the one-click
decommission at officialisation.
"""

from django.contrib import admin

from apps.public_site.models import ElectionNotice


@admin.register(ElectionNotice)
class ElectionNoticeAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "updated_at")
    list_filter = ("is_active",)
    fields = (
        "is_active",
        "title",
        "body",
        "election_date",
        "poster",
        "campaign_portrait",
        "campaign_portrait_caption",
        "learn_more_url",
        "learn_more_label",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields
