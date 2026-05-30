#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys


def main():
    # Pick settings module from DJANGO_ENV env var. This prevents the
    # recurring "manage.py migrate ran against SQLite instead of
    # Postgres" bug on the production VPS:
    #   - VPS sets DJANGO_ENV=prod in /srv/kuppetmsa-v2/.env, loaded
    #     by systemd before gunicorn AND sourced by deploy shells.
    #   - Laptop leaves DJANGO_ENV unset and gets development settings.
    # Either way, `manage.py` chooses the right DB without anyone
    # remembering to `export DJANGO_SETTINGS_MODULE` first.
    _env = os.environ.get("DJANGO_ENV", "dev")
    _settings = "config.settings.production" if _env == "prod" else "config.settings.development"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", _settings)
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
