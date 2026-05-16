"""Global test configuration.

Guarantees the security-sensitive env vars exist before Django settings
load, so `pytest` works deterministically even if a developer hasn't
exported them. CI exports real values; this is the local-dev safety
net. The encryption key here is test-only and distinct from the JWT /
secret keys so the test suite exercises the "separate key" path that
production uses.
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production-use-only-1234567890")
os.environ.setdefault(
    "DJANGO_JWT_SIGNING_KEY",
    "test-jwt-signing-key-not-for-production-1234567890",
)
os.environ.setdefault(
    "DJANGO_FIELD_ENCRYPTION_KEY",
    "test-field-encryption-key-distinct-not-for-production-1234567890",
)
os.environ.setdefault("DJANGO_DEBUG", "True")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
