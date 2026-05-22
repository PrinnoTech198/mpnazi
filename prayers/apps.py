from django.apps import AppConfig


class PrayersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "prayers"
    verbose_name = "Prayer requests"

    def ready(self):
        import prayers.signals  # noqa: F401
