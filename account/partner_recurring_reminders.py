"""
Schedule and deliver push reminders for paid recurring partner giving.
"""
from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from account.models import Partnership

logger = logging.getLogger(__name__)

# Local hour for reminder delivery (Africa/Dar es Salaam when USE_TZ + TIME_ZONE set).
REMINDER_HOUR = 9
REMINDER_MINUTE = 0


def _reminder_time_on(day: date) -> datetime:
    tz = timezone.get_current_timezone()
    return timezone.make_aware(
        datetime.combine(day, time(REMINDER_HOUR, REMINDER_MINUTE)),
        tz,
    )


def _add_months(d: date, months: int = 1) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def _next_1st_or_15th(after: datetime) -> datetime:
    """Next reminder at 1st or 15th of month, strictly after ``after``."""
    cursor = after.date()
    for _ in range(36):
        for day in (1, 15):
            candidate = date(cursor.year, cursor.month, day)
            dt = _reminder_time_on(candidate)
            if dt > after:
                return dt
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return _reminder_time_on(_add_months(after.date(), 1))


def compute_next_reminder_at(
    partnership: Partnership,
    *,
    after: datetime | None = None,
) -> datetime | None:
    """
    Compute the next reminder datetime for a recurring, paid partnership.
    Returns None when reminders should not run.
    """
    if partnership.gift_type != Partnership.GIFT_RECURRING:
        return None
    if not partnership.frequency:
        return None
    if not partnership.paid_at:
        return None

    anchor = after or timezone.now()
    freq = partnership.frequency

    if partnership.start_date:
        start_dt = _reminder_time_on(partnership.start_date)
        if start_dt > anchor:
            return start_dt

    if freq == Partnership.FREQ_WEEKLY:
        return anchor + timedelta(days=7)
    if freq == Partnership.FREQ_EVERY_2_WEEKS:
        return anchor + timedelta(days=14)
    if freq == Partnership.FREQ_MONTHLY:
        return _reminder_time_on(_add_months(anchor.date(), 1))
    if freq == Partnership.FREQ_1ST_15TH:
        return _next_1st_or_15th(anchor)

    logger.warning(
        "Unknown partnership frequency partnership_id=%s frequency=%s",
        partnership.pk,
        freq,
    )
    return None


def sync_partnership_reminder_schedule(partnership: Partnership) -> None:
    """Persist ``next_reminder_at`` from current gift type, frequency, and paid state."""
    if partnership.gift_type != Partnership.GIFT_RECURRING or not partnership.paid_at:
        if partnership.next_reminder_at is not None:
            partnership.next_reminder_at = None
            partnership.save(update_fields=["next_reminder_at"])
        return

    nxt = compute_next_reminder_at(partnership, after=timezone.now())
    if partnership.next_reminder_at == nxt:
        return
    partnership.next_reminder_at = nxt
    partnership.save(update_fields=["next_reminder_at"])
    logger.info(
        "Partner recurring reminder scheduled partnership_id=%s next=%s frequency=%s",
        partnership.pk,
        nxt,
        partnership.frequency,
    )


def frequency_label(frequency: str | None) -> str:
    labels = dict(Partnership.FREQUENCY_CHOICES)
    return labels.get(frequency or "", frequency or "recurring")


def send_recurring_reminder_push(partnership: Partnership) -> bool:
    """Send FCM reminder to the partnership owner. Returns True if any token was targeted."""
    user = partnership.user
    user_id = getattr(user, "pk", None) if user else None
    if not user_id:
        return False

    from notifications.fcm import send_push, user_device_tokens

    tokens = user_device_tokens(user_id)
    if not tokens:
        logger.debug(
            "No device tokens for recurring reminder partnership_id=%s user_id=%s",
            partnership.pk,
            user_id,
        )
        return False

    freq_text = frequency_label(partnership.frequency)
    title = "Partnership giving reminder"
    body = (
        f"Your {freq_text.lower()} gift of {partnership.amount} "
        f"{partnership.currency} is due. Tap to give again."
    )
    data = {
        "type": "partner_recurring_reminder",
        "id": str(partnership.pk),
        "route": "/giving",
        "frequency": partnership.frequency or "",
    }

    try:
        from django_q.tasks import async_task

        async_task(
            "notifications.tasks.deliver_push_task",
            tokens,
            title,
            body,
            data,
        )
        return True
    except Exception:
        logger.exception(
            "Failed to enqueue partner recurring reminder partnership_id=%s",
            partnership.pk,
        )
        return False


def process_due_partner_recurring_reminders() -> int:
    """
    Send reminders for partnerships whose ``next_reminder_at`` has passed,
    then advance the schedule. Returns count processed.
    """
    now = timezone.now()
    due = list(
        Partnership.objects.select_related("partner_type", "user").filter(
            gift_type=Partnership.GIFT_RECURRING,
            paid_at__isnull=False,
            frequency__isnull=False,
            next_reminder_at__isnull=False,
            next_reminder_at__lte=now,
        )[:200]
    )
    processed = 0
    for pship in due:
        send_recurring_reminder_push(pship)
        pship.last_reminder_at = now
        pship.next_reminder_at = compute_next_reminder_at(pship, after=now)
        pship.save(update_fields=["last_reminder_at", "next_reminder_at"])
        processed += 1
    return processed
