from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
    verbose_name = "Push notifications"

    def ready(self) -> None:
        # Import signal handlers
        from . import signals  # noqa: F401
