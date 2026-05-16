from django.apps import AppConfig


class FinancesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.finances"
    label = "finances"
    verbose_name = "Finances"

    def ready(self):
        # Register models with django-auditlog. Import here so the app
        # registry is fully loaded.
        from apps.finances import audit  # noqa: F401
