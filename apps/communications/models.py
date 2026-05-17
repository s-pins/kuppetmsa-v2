"""Communications models.

Matches docs/erd.md §3. Two models:

  Announcement  — composed by a comms officer; carries an audience
                  filter spec. Draft until explicitly sent; sending is
                  a one-way transition that fans out Notifications.
  Notification  — per-member delivery row with its own read state. A
                  member only ever sees their own.

Recipient resolution happens AT SEND TIME (not at compose), so an
announcement targeted at "active members in Mvita" reflects membership
as it stands when sent, not when drafted. Fan-out is idempotent: a
second send is refused (status check), so a retried request cannot
double-notify.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AnnouncementStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SENT = "sent", "Sent"


class AudienceScope(models.TextChoices):
    ALL_MEMBERS = "all_members", "All members"
    ACTIVE_MEMBERS = "active_members", "Active members only"
    SUB_COUNTY = "sub_county", "Members in a sub-county"


class Announcement(TimeStampedModel):
    title = models.CharField(max_length=200)
    body = models.TextField()

    audience_scope = models.CharField(
        max_length=16,
        choices=AudienceScope.choices,
        default=AudienceScope.ACTIVE_MEMBERS,
    )
    # Only meaningful when audience_scope == SUB_COUNTY.
    audience_sub_county = models.CharField(max_length=20, blank=True)

    status = models.CharField(
        max_length=8,
        choices=AnnouncementStatus.choices,
        default=AnnouncementStatus.DRAFT,
    )
    # Opt-in public visibility. Default False is deliberate: an
    # announcement's audience_scope targets MEMBERS (all/active/
    # sub-county) — none of those imply "show this to the world".
    # Phase 9's public news endpoint shows ONLY announcements where a
    # comms officer explicitly set is_public AND that have been sent.
    # This makes public exposure a conscious, auditable act, not an
    # inference from an audience scope that never meant "public".
    is_public = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="announcements",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    recipient_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["is_public", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} [{self.status}]"

    def _recipients(self):
        """Resolve target Members at call time."""
        from apps.members.models import Member

        qs = Member.objects.all()
        if self.audience_scope == AudienceScope.ALL_MEMBERS:
            return qs
        if self.audience_scope == AudienceScope.ACTIVE_MEMBERS:
            return qs.filter(is_active=True)
        if self.audience_scope == AudienceScope.SUB_COUNTY:
            return qs.filter(
                is_active=True,
                sub_county=self.audience_sub_county,
            )
        return qs.none()

    @transaction.atomic
    def send(self) -> int:
        """Fan out to Notifications. Idempotent: refuses a second send."""
        if self.status == AnnouncementStatus.SENT:
            raise ValidationError("Announcement has already been sent.")
        if self.audience_scope == AudienceScope.SUB_COUNTY and not self.audience_sub_county:
            raise ValidationError("Sub-county scope requires audience_sub_county.")

        members = list(self._recipients().select_related("user"))
        notifications = [Notification(announcement=self, member=m) for m in members]
        Notification.objects.bulk_create(notifications)

        self.status = AnnouncementStatus.SENT
        self.sent_at = timezone.now()
        self.recipient_count = len(notifications)
        self.save(
            update_fields=[
                "status",
                "sent_at",
                "recipient_count",
                "updated_at",
            ]
        )
        return self.recipient_count


class Notification(TimeStampedModel):
    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    member = models.ForeignKey(
        "members.Member",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        unique_together = ("announcement", "member")
        indexes = [models.Index(fields=["member", "is_read"])]

    def __str__(self) -> str:
        return (
            f"{self.announcement.title} -> {self.member} ({'read' if self.is_read else 'unread'})"
        )

    def mark_read(self) -> None:
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at", "updated_at"])
