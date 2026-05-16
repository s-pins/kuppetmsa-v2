"""
Custom User model.

Email-as-username, role-driven authorization, capability flags layered on top.
This is the schema; permission *logic* lives in apps.core.permissions and
apps.core.mixins, never as methods on this model.
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.constants import (
    ROLE_CHOICES,
    ROLE_MEMBER,
)


class UserManager(BaseUserManager):
    """Email-based user manager."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Email is required.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Email-login user with role + flags.

    Note: there is intentionally NO `is_chairperson` etc. property. Permission
    checks happen through apps.core.permissions and apps.core.mixins, which
    read .role and the flag fields directly. Keeping the model dumb makes
    drift between matrix and code easier to spot.
    """

    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    role = models.CharField(
        max_length=40,
        choices=ROLE_CHOICES,
        default=ROLE_MEMBER,
        db_index=True,
    )

    # Capability flags — additive on top of role.
    # See docs/permissions.md §3.
    discipline_committee_member = models.BooleanField(default=False)
    welfare_officer = models.BooleanField(default=False)
    manifesto_editor = models.BooleanField(default=False)

    # 2FA enrollment marker. The actual TOTP secret is managed by allauth-mfa
    # (or whichever 2FA app we wire in phase 0). This boolean is a cached
    # convenience for permission checks — kept in sync via a signal.
    is_2fa_enrolled = models.BooleanField(default=False)

    # Tracks the most recent strong authentication (password or TOTP).
    # Used by RecentAuthRequired permission/mixin.
    last_strong_auth_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ('email',)
        indexes = [
            models.Index(fields=['role', 'is_active']),
        ]

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'.strip() or self.email

    def get_short_name(self) -> str:
        return self.first_name or self.email
