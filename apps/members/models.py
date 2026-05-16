"""Member model.

Matches the MEMBERS entity in docs/erd.md §1:

  - optional 1-to-1 to a User account (a member may never log in)
  - unique membership_id and tsc_number
  - PROTECT from contributions/expenses is declared on those FKs (phase 2),
    not here.

Membership-id generation is deliberately NOT `count()+1` (the v1 bug). We
use a zero-padded sequence derived from the max existing numeric suffix,
inside the same transaction as the insert, with a retry on collision.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models, transaction


class TimeStampedModel(models.Model):
    """Abstract base: created_at / updated_at on every domain model."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SubCounty(models.TextChoices):
    """Mombasa County sub-counties (wards live as free text for now)."""

    CHANGAMWE = 'changamwe', 'Changamwe'
    JOMVU = 'jomvu', 'Jomvu'
    KISAUNI = 'kisauni', 'Kisauni'
    NYALI = 'nyali', 'Nyali'
    LIKONI = 'likoni', 'Likoni'
    MVITA = 'mvita', 'Mvita'


class MemberQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def with_account(self):
        return self.exclude(user__isnull=True)


class MembershipCounter(models.Model):
    """Single-row durable allocator for membership numbers.

    Scanning existing rows for max(id) reuses numbers after a delete (the
    exact v1 bug). A standalone monotonic counter never goes backwards,
    so a deleted member's number is retired forever.
    """

    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'membership counter'

    @classmethod
    def allocate(cls) -> int:
        """Atomically increment and return the next value.

        select_for_update serialises concurrent allocations; the caller is
        expected to be inside a transaction (Member.save provides one).
        """
        row, _ = cls.objects.select_for_update().get_or_create(pk=1)
        row.last_value += 1
        row.save(update_fields=['last_value'])
        return row.last_value


class Member(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='member_profile',
        help_text='Optional login account. A member may exist without one.',
    )

    membership_id = models.CharField(max_length=12, unique=True, editable=False)
    tsc_number = models.CharField(
        max_length=20,
        unique=True,
        help_text='Teachers Service Commission number.',
    )

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    school = models.CharField(max_length=200, blank=True)
    sub_county = models.CharField(
        max_length=20,
        choices=SubCounty.choices,
        blank=True,
    )
    ward = models.CharField(max_length=100, blank=True)

    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='members/photos/', blank=True, null=True)

    is_active = models.BooleanField(
        default=True,
        help_text='Paid-up / in good standing. Deactivate rather than delete.',
    )
    joined_on = models.DateField(null=True, blank=True)

    objects = MemberQuerySet.as_manager()

    class Meta:
        ordering = ('last_name', 'first_name')
        indexes = [
            models.Index(fields=['is_active', 'sub_county']),
            models.Index(fields=['school']),
        ]

    def __str__(self) -> str:
        return f'{self.full_name} ({self.membership_id})'

    @property
    def full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'.strip()

    # ------------------------------------------------------------------
    # Membership-id generation — race-safe, gap-tolerant.
    # ------------------------------------------------------------------

    _ID_PREFIX = 'M'
    _ID_WIDTH = 5

    def save(self, *args, **kwargs):
        if self.membership_id:
            return super().save(*args, **kwargs)

        # Allocate from the durable counter inside one transaction with the
        # insert. The counter only ever increases, so a later delete cannot
        # cause a number to be reused.
        with transaction.atomic():
            n = MembershipCounter.allocate()
            self.membership_id = f'{self._ID_PREFIX}{n:0{self._ID_WIDTH}d}'
            return super().save(*args, **kwargs)
