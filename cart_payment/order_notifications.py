"""
Customer email notifications for marketplace orders (payment + fulfillment).

Sending uses ``account.email``; failures are logged only.
"""
from __future__ import annotations

import logging

from django.db import transaction

from account.email import send_cart_order_paid_confirmation, send_marketplace_order_email
from account.models import Order

from .models import CartOrderFulfillment, CartOrderPayment

logger = logging.getLogger(__name__)

_FULFILLMENT_NOTIFY_STATUSES = frozenset(
    {
        CartOrderFulfillment.ST_SENT_TO_REP,
        CartOrderFulfillment.ST_AT_REP,
        CartOrderFulfillment.ST_READY,
        CartOrderFulfillment.ST_COMPLETED,
    }
)


def _customer_email(order: Order) -> str | None:
    user = order.user
    if not user or not user.is_active:
        return None
    email = (getattr(user, "email", None) or "").strip()
    if not email:
        return None
    return email


def _rep_line(order: Order) -> str:
    from django.utils.html import escape

    rep = order.representative
    if not rep:
        return ""
    name = escape((rep.full_name or "").strip())
    if not name:
        return ""
    return f'<p style="margin-bottom:0;">Your representative: <strong>{name}</strong></p>'


def notify_order_payment_completed(
    order: Order, *, payment: CartOrderPayment | None = None
) -> None:
    """
    Send cart payment confirmation (idempotent per ``CartOrderPayment`` when provided).
    """
    order = (
        Order.objects.select_related("user", "representative")
        .filter(pk=order.pk)
        .first()
    )
    if not order:
        return
    if not _customer_email(order):
        logger.info("Skip payment-complete email: no address order_id=%s", order.pk)
        return

    if payment is not None:
        with transaction.atomic():
            pay = CartOrderPayment.objects.select_for_update().get(pk=payment.pk)
            meta = dict(pay.metadata or {})
            if meta.get("confirmation_email_sent"):
                logger.info(
                    "Skip duplicate cart payment email payment_id=%s order_id=%s",
                    pay.id,
                    order.pk,
                )
                return
            meta["confirmation_email_sent"] = True
            pay.metadata = meta
            pay.save(update_fields=["metadata"])
            payment = pay

    try:
        send_cart_order_paid_confirmation(order=order, payment=payment)
    except Exception:
        logger.exception("notify_order_payment_completed failed order_id=%s", order.pk)


def maybe_notify_fulfillment_status_change(
    order: Order, *, previous: str | None, current: str
) -> None:
    if order.status != Order.STATUS_PAID:
        return
    if current not in _FULFILLMENT_NOTIFY_STATUSES:
        return
    if previous == current:
        return
    to = _customer_email(order)
    if not to:
        logger.info(
            "Skip fulfillment email: no address order_id=%s status=%s",
            order.pk,
            current,
        )
        return

    from django.utils.html import escape

    labels = {
        CartOrderFulfillment.ST_SENT_TO_REP: (
            "Order sent to your representative",
            "Your order has been sent to your representative and is on the way.",
        ),
        CartOrderFulfillment.ST_AT_REP: (
            "Order arrived at your representative",
            "Your order has arrived with your representative.",
        ),
        CartOrderFulfillment.ST_READY: (
            "Ready for pickup",
            "Your order is ready for pickup. Please coordinate with your representative in the app.",
        ),
        CartOrderFulfillment.ST_COMPLETED: (
            "Order completed",
            "Your order is marked as completed. Thank you for using Mpanzi.",
        ),
    }
    title, lead = labels[current]
    oid = order.pk
    status_label = dict(CartOrderFulfillment.STATUS_CHOICES).get(current, current)
    paras = [
        f'<p style="margin-top:0;">{escape(lead)}</p>',
        f"<p>Order <strong>#{oid}</strong> — <strong>{escape(status_label)}</strong>.</p>",
        _rep_line(order),
    ]
    try:
        send_marketplace_order_email(
            to,
            subject=f"{title} — Mpanzi order #{oid}",
            page_title=title,
            inner_html_paragraphs=[p for p in paras if p],
        )
    except Exception:
        logger.exception(
            "maybe_notify_fulfillment_status_change failed order_id=%s status=%s",
            oid,
            current,
        )
