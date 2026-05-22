import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AccountConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "account"

    def ready(self) -> None:
        import account.signals  # noqa: F401

        self._ensure_recurring_reminder_schedule()

    def _ensure_recurring_reminder_schedule(self) -> None:
        """Hourly Django-Q task to deliver due partner recurring reminders."""
        try:
            from django_q.models import Schedule

            name = "partner_recurring_reminders_hourly"
            if Schedule.objects.filter(name=name).exists():
                return
            Schedule.objects.create(
                name=name,
                func="account.partner_recurring_reminders.process_due_partner_recurring_reminders",
                schedule_type=Schedule.HOURLY,
                repeats=-1,
            )
            logger.info("Registered Django-Q schedule: %s", name)
        except Exception:
            logger.debug(
                "Could not register partner recurring reminder schedule (django_q may be unavailable)",
                exc_info=True,
            )
