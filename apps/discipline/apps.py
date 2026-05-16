from django.apps import AppConfig


class DisciplineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.discipline"
    label = "discipline"
    verbose_name = "Disciplinary records"

    def ready(self):
        from apps.discipline import audit  # noqa: F401
