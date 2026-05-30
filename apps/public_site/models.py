"""Election notice — a deliberately self-contained, removable module.

Design intent (agreed with the client): this is the campaign wrapper
around an otherwise-neutral transparency system. When Team Reforms SKS
wins and officialises this as the branch's system, the entire campaign
layer must switch off in ONE action with zero archaeology — so it lives
in a single model with a single master flag, and the poster is an
uploaded image the client controls, never a hardcoded asset.

To decommission at officialisation: set `is_active = False` (or delete
the row). Nothing else in the system references campaign content; the
public site simply stops rendering the modal. This file and its
template are the complete footprint. Fields cover the campaign
content (title, body, poster, portrait), the campaign date/CTA
(election_date, learn_more_url, learn_more_label), and the
master switch (is_active).
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models


class ElectionNotice(models.Model):
    """A single, dismissable campaign notice shown on the public site.

    Intentionally a singleton-ish model: typically one active row. The
    public view picks the most recent active one.
    """

    title = models.CharField(
        max_length=160,
        help_text="Headline shown at the top of the notice modal.",
    )
    body = models.TextField(
        help_text="Short message. Plain text; keep it brief and factual.",
    )
    election_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date of the branch election. Drives the countdown "
        "widget on the public home page. Leave blank to hide the "
        "countdown entirely.",
    )
    poster = models.ImageField(
        upload_to="election_notices/",
        blank=True,
        null=True,
        help_text="Optional campaign poster image (client-supplied).",
    )
    campaign_portrait = models.ImageField(
        upload_to="election_notices/",
        blank=True,
        null=True,
        help_text="Optional candidate portrait shown alongside the body "
        "text in the modal. Different visual role from poster.",
    )
    campaign_portrait_caption = models.CharField(
        max_length=160,
        blank=True,
        help_text="Short caption under the portrait (e.g. name and "
        "candidacy). Only shown if the portrait is set.",
    )
    learn_more_url = models.URLField(
        blank=True,
        help_text="Optional external link (e.g. the campaign's own "
        "channel). Campaign material should live there, not here.",
    )
    learn_more_label = models.CharField(
        max_length=60,
        blank=True,
        default="Learn more",
    )

    # THE master switch. False (or no active row) => the public site is
    # a clean, neutral transparency tool with no campaign content.
    is_active = models.BooleanField(
        default=False,
        help_text="Master switch. Turn OFF at officialisation to make "
        "this a neutral branch system with one click.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        verbose_name = "election notice"
        verbose_name_plural = "election notices"

    def __str__(self) -> str:
        state = "ACTIVE" if self.is_active else "inactive"
        return f"{self.title} [{state}]"

    def clean(self):
        if self.learn_more_url and not self.learn_more_label:
            raise ValidationError("Provide a label for the learn-more link.")

    @classmethod
    def current(cls) -> ElectionNotice | None:
        """The notice to show, or None if campaign mode is off.

        One query, used by the public site. If this returns None the
        site renders with no campaign content at all.
        """
        return cls.objects.filter(is_active=True).first()
