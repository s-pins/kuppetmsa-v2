from django.apps import AppConfig


class WelfareConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.welfare"
    label = "welfare"
    verbose_name = "Welfare claims"

    def ready(self):
        from apps.welfare import audit  # noqa: F401
