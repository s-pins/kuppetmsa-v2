"""Production settings — Postgres, HTTPS, Sentry."""

from decouple import config

from .base import *

DEBUG = False

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        # Empty defaults so settings IMPORT for collectstatic / check
        # before the DB is provisioned. Any command that actually
        # touches the DB (migrate, runserver) will fail clearly on
        # connection if these are unset — that is the correct, visible
        # failure, unlike an opaque import-time crash.
        "NAME": config("DJANGO_DB_NAME", default=""),
        "USER": config("DJANGO_DB_USER", default=""),
        "PASSWORD": config("DJANGO_DB_PASSWORD", default=""),
        "HOST": config("DJANGO_DB_HOST", default="localhost"),
        "PORT": config("DJANGO_DB_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"sslmode": config("DJANGO_DB_SSLMODE", default="prefer")},
    },
}

# ---------------------------------------------------------------------------
# HTTPS hardening — production only
# ---------------------------------------------------------------------------

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# Sessions & CSRF cookie settings
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = config(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default="https://kuppetmsa.co.ke,https://www.kuppetmsa.co.ke",
    cast=lambda s: [x.strip() for x in s.split(",") if x.strip()],
)

# ---------------------------------------------------------------------------
# Email (real SMTP)
# ---------------------------------------------------------------------------

# Email (real SMTP).
# These have placeholder defaults so production settings can be IMPORTED
# for collectstatic / migrate / check_deploy before SMTP is wired. They
# are intentionally non-functional defaults — `check_deploy` FAILs if
# email is still unconfigured, and email verification will visibly not
# work until real values are set. This trades an opaque import-time
# UndefinedValueError for a clear, actionable check.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("DJANGO_EMAIL_HOST", default="")
EMAIL_PORT = config("DJANGO_EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("DJANGO_EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("DJANGO_EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("DJANGO_EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config(
    "DJANGO_DEFAULT_FROM_EMAIL",
    default="noreply@kuppetmsa.co.ke",
)

# ---------------------------------------------------------------------------
# Sentry
# ---------------------------------------------------------------------------

SENTRY_DSN = config("DJANGO_SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment=config("DJANGO_SENTRY_ENV", default="production"),
    )
