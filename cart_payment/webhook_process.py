"""
Cart-only AzamPay webhook handling (extracted for reuse).

`process_cart_azampay_webhook` returns a DRF Response when this payload belongs to a
`CartOrderPayment`; returns None when it does not (caller may treat as partner/other).
"""
from __future__ import annotations

import logging
import time
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.response import Response

from account.models import Order

from .models import CartOrderFulfillment, CartOrderPayment, CartPaymentWebhookLog
from .webhook_resolve import (
    gateway_transaction_id_from_webhook,
    merchant_external_id_from_webhook,
    resolve_cart_payment_from_payload,
)

logger = logging.getLogger(__name__)

WEBHOOK_LOOKUP_ATTEMPTS = 24
WEBHOOK_LOOKUP_SLEEP_SEC = 0.5


def _webhook_ok(body: dict, code: int = 200):
    return Response(body, status=code)


def process_cart_azampay_webhook(
    payload: dict, *, relaxed_lookup: bool = True
) -> Response | None:
    """
    If `payload` matches a marketplace `CartOrderPayment`, apply idempotent updates
    and return a JSON Response (always HTTP 200 for AzamPay).

    Returns None when no cart payment matches — caller may continue with partner logic.

    ``relaxed_lookup`` (default True): retry lookup for the cart webhook URL so callbacks
    that arrive before the DB commit can still match.

    When ``relaxed_lookup`` is False (e.g. handoff from the partner webhook URL), use a
    short bounded wait so legitimate partner webhooks are not delayed by many sleeps.
    """
    max_attempts = WEBHOOK_LOOKUP_ATTEMPTS if relaxed_lookup else 12

    log: CartPaymentWebhookLog | None = None
    if relaxed_lookup:
        log = CartPaymentWebhookLog.objects.create(
            payload=payload,
            outcome="received",
        )

    merchant = merchant_external_id_from_webhook(payload)
    gw_tx = gateway_transaction_id_from_webhook(payload)

    pay = None
    for attempt in range(max_attempts):
        pay = resolve_cart_payment_from_payload(payload)
        if pay:
            if attempt > 0:
                logger.info(
                    "Cart AzamPay webhook matched payment_id=%s after %s attempts",
                    pay.id,
                    attempt + 1,
                )
            break
        if attempt < max_attempts - 1:
            time.sleep(WEBHOOK_LOOKUP_SLEEP_SEC)

    if not pay:
        if log:
            log.outcome = "no_cart_payment_match"
            log.save(update_fields=["outcome"])
        logger.info(
            "Cart webhook: no CartOrderPayment for merchant=%r gateway_tx=%r",
            merchant,
            gw_tx,
        )
        return None

    if log is None:
        log = CartPaymentWebhookLog.objects.create(
            payload=payload,
            outcome="received",
        )

    log.matched_payment_id = pay.id
    log.outcome = "matched"
    log.save(update_fields=["matched_payment_id", "outcome"])

    if pay.status == CartOrderPayment.STATUS_SUCCESS:
        return _webhook_ok({"success": True, "message": "already processed"}, 200)

    tx_status = (payload.get("transactionstatus") or payload.get("transactionStatus") or "").lower()
    pay.raw_last_webhook = payload
    pay.provider_transaction_id = (gw_tx or pay.provider_transaction_id) or pay.provider_transaction_id
    util = payload.get("utilityref") or payload.get("utilityRef")
    if util:
        pay.utility_reference = str(util)[:255]

    try:
        webhook_amt = Decimal(str(payload.get("amount") or "0"))
        if webhook_amt != pay.amount:
            logger.error(
                "Cart payment amount mismatch payment_id=%s expected=%s got=%s",
                pay.id,
                pay.amount,
                webhook_amt,
            )
            pay.save(
                update_fields=[
                    "raw_last_webhook",
                    "provider_transaction_id",
                    "utility_reference",
                ]
            )
            return _webhook_ok({"success": True, "message": "amount mismatch logged"}, 200)
    except Exception:
        pass

    order = pay.order
    if tx_status == "success":
        with transaction.atomic():
            pay.status = CartOrderPayment.STATUS_SUCCESS
            pay.completed_at = timezone.now()
            pay.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "raw_last_webhook",
                    "provider_transaction_id",
                    "utility_reference",
                ]
            )
            order.status = Order.STATUS_PAID
            if gw_tx:
                order.transaction_id = str(gw_tx)[:255]
            order.fulfillment_status = CartOrderFulfillment.ST_PROCESSING
            order.save(update_fields=["status", "transaction_id", "fulfillment_status"])
            CartOrderFulfillment.objects.update_or_create(
                order=order,
                defaults={
                    "status": CartOrderFulfillment.ST_PROCESSING,
                },
            )
        try:
            from .order_notifications import notify_order_payment_completed

            notify_order_payment_completed(order)
        except Exception:
            logger.exception(
                "notify_order_payment_completed failed order_id=%s", order.pk
            )
    elif tx_status == "failed":
        pay.status = CartOrderPayment.STATUS_FAILED
        pay.completed_at = timezone.now()
        pay.save(
            update_fields=[
                "status",
                "completed_at",
                "raw_last_webhook",
                "provider_transaction_id",
                "utility_reference",
            ]
        )
        order.status = Order.STATUS_FAILED
        order.save(update_fields=["status"])
    else:
        pay.save(
            update_fields=[
                "raw_last_webhook",
                "provider_transaction_id",
                "utility_reference",
            ]
        )

    return _webhook_ok({"success": True, "message": "ok"}, 200)
