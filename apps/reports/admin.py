"""Admin for reports."""

from django.contrib import admin

from apps.reports.models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "year",
        "is_published",
        "uploaded_by",
    )
    list_filter = ("category", "year", "is_published")
    search_fields = ("title", "description")
    readonly_fields = ("uploaded_by", "created_at", "updated_at")
