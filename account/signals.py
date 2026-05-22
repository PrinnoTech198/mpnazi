from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from account.models import Partnership
from account.partner_recurring_reminders import sync_partnership_reminder_schedule


@receiver(post_save, sender=Partnership)
def partnership_recurring_reminder_schedule(sender, instance: Partnership, **kwargs):
    """
    Reschedule push reminders when recurring frequency or start date changes.
    """
    update_fields = kwargs.get("update_fields")
    if update_fields is not None:
        watched = {"gift_type", "frequency", "start_date", "paid_at"}
        if not watched.intersection(set(update_fields)):
            return
    sync_partnership_reminder_schedule(instance)
