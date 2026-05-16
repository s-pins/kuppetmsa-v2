"""Development settings — DEBUG, SQLite, no HTTPS enforcement."""

from .base import *
from .base import BASE_DIR, INSTALLED_APPS, MIDDLEWARE

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "testserver"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    },
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Looser CORS for local frontend dev.
CORS_ALLOW_ALL_ORIGINS = True

# Allow django-debug-toolbar if installed locally; optional.
INTERNAL_IPS = ["127.0.0.1"]
