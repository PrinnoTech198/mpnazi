from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import close_old_connections
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


def _admin_recipients():
    return list(
        User.objects.filter(is_active=True, is_staff=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def notify_admin_new_prayer_task(prayer_request_id: int) -> None:
    close_old_connections()
    try:
        from .models import PrayerAdminNotification, PrayerRequest

        prayer = PrayerRequest.objects.get(pk=prayer_request_id)
        message = (
            f"New {prayer.get_category_display()} request from {prayer.country} — "
            f"{prayer.display_name}"
        )
        PrayerAdminNotification.objects.create(
            prayer_request=prayer,
            message=message,
        )

        recipients = _admin_recipients()
        if recipients:
            ctx = {
                "prayer": prayer,
                "dashboard_url": getattr(
                    settings, "ADMIN_DASHBOARD_URL", "https://mpnazi-production.up.railway.app"
                ),
            }
            html = render_to_string("emails/new_prayer_admin.html", ctx)
            text = render_to_string("emails/new_prayer_admin.txt", ctx)
            send_mail(
                subject=f"[New Prayer] {prayer.get_category_display()} from {prayer.country}",
                message=text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                html_message=html,
                fail_silently=False,
            )

        from .broadcast import broadcast_new_prayer

        broadcast_new_prayer(prayer)
    except Exception:
        logger.exception("notify_admin_new_prayer_task failed prayer_id=%s", prayer_request_id)
        raise
    finally:
        close_old_connections()


def send_admin_reply_email_task(prayer_request_id: int, reply_text: str, admin_user_id: int) -> None:
    close_old_connections()
    try:
        from .models import PrayerRequest

        prayer = PrayerRequest.objects.get(pk=prayer_request_id)
        if not prayer.email:
            return

        admin = User.objects.filter(pk=admin_user_id).first()
        ctx = {
            "prayer": prayer,
            "reply_text": reply_text,
            "admin_name": (admin.get_full_name() or admin.username) if admin else "Mpanzi Team",
            "organization": "Mpanzi Ministries",
        }
        html = render_to_string("emails/admin_reply_requester.html", ctx)
        text = render_to_string("emails/admin_reply_requester.txt", ctx)
        send_mail(
            subject="A personal response to your prayer request",
            message=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[prayer.email],
            html_message=html,
            fail_silently=False,
        )

        prayer.admin_reply = reply_text
        prayer.admin_reply_sent_at = timezone.now()
        prayer.admin_replied_by_id = admin_user_id
        prayer.save(
            update_fields=["admin_reply", "admin_reply_sent_at", "admin_replied_by", "updated_at"]
        )
    except Exception:
        logger.exception("send_admin_reply_email_task failed prayer_id=%s", prayer_request_id)
        raise
    finally:
        close_old_connections()
