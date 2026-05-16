"""Event models.

Matches docs/erd.md §2. EventAttendance is an explicit through-model,
NOT an implicit M2M table, because the domain needs the
RSVP-vs-actually-attended distinction plus a timestamp on each — "said
they'd come", "came", "came without RSVPing" are all different states
the organising secretary cares about.

Event.starts_at is nullable on purpose: the gallery use case ("we held
an event, exact time isn't recorded") must work (v1 parity, noted in
docs/erd.md §2).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class EventType(models.TextChoices):
    MEETING = "meeting", "Meeting"
    AGM = "agm", "Annual general meeting"
    TRAINING = "training", "Training / workshop"
    WELFARE = "welfare", "Welfare event"
    SOCIAL = "social", "Social"
    OTHER = "other", "Other"


class Event(TimeStampedModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    event_type = models.CharField(
        max_length=12,
        choices=EventType.choices,
        default=EventType.MEETING,
    )
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    image = models.ImageField(upload_to="events/images/", blank=True, null=True)
    is_public = models.BooleanField(default=True)

    attendees = models.ManyToManyField(
        "members.Member",
        through="events.EventAttendance",
        related_name="events",
        blank=True,
    )

    class Meta:
        ordering = ("-starts_at", "-created_at")
        indexes = [models.Index(fields=["is_public", "starts_at"])]

    def __str__(self) -> str:
        return self.title

    @property
    def rsvp_count(self) -> int:
        return self.attendance_records.filter(rsvp=True).count()

    @property
    def attended_count(self) -> int:
        return self.attendance_records.filter(attended=True).count()


class EventAttendance(TimeStampedModel):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    member = models.ForeignKey(
        "members.Member",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    rsvp = models.BooleanField(default=False)
    attended = models.BooleanField(default=False)
    rsvp_at = models.DateTimeField(null=True, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_attendances",
        help_text="Officer who recorded attendance (null if self-RSVP).",
    )

    class Meta:
        unique_together = ("event", "member")
        ordering = ("-rsvp_at",)

    def __str__(self) -> str:
        state = []
        if self.rsvp:
            state.append("RSVP")
        if self.attended:
            state.append("attended")
        return f"{self.member} @ {self.event} ({', '.join(state) or 'none'})"
