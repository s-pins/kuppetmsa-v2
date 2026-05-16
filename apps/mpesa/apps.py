from django.apps import AppConfig


class MpesaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mpesa"
    label = "mpesa"
    verbose_name = "M-Pesa integration"

    def ready(self):
        from apps.mpesa import audit  # noqa: F401
