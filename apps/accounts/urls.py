"""Server-rendered URLs for the accounts app.

Phase 0 ships the namespace and stubs only. Phase 1 wires up:
    - login / logout (django-allauth)
    - password reset
    - 2FA enrollment
    - reauth (named 'accounts:reauth' — referenced by RecentAuthRequiredMixin)
"""
from django.urls import path

app_name = 'accounts'

urlpatterns: list = [
    # Reserved for phase 1.
]
