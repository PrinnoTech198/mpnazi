"""
Orchestrates checkout initiation, IPN processing, and status verification.
"""
from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

from django.db import close_old_connections, transaction
from django.utils import timezone

from account.models import Order, Partnership, Payment
from cart_payment.models import CartOrderFulfillment, CartOrderPayment
from cart_payment.order_notifications import notify_order_payment_completed
from payments.models import PaymentWebhookLog, TransactionHistory
from payments.providers.pesapal import PesapalConfigurationError, PesapalProvider
from payments.utils.ipn_resolve import (
    extract_pesapal_ipn_fields,
    merchant_reference_from_status_response,
    resolve_cart_payment_from_ipn,
    resolve_partner_payment_from_ipn,
)
from payments.utils.references import partnership_currency_iso

from .gateway import get_default_provider

logger = logging.getLogger(__name__)

IPN_LOOKUP_ATTEMPTS = 24
IPN_LOOKUP_SLEEP_SEC = 0.5

TERMINAL_PARTNER = (Payment.STATUS_SUCCESS, Payment.STATUS_FAILED)
TERMINAL_CART = (CartOrderPayment.STATUS_SUCCESS, CartOrderPayment.STATUS_FAILED)


def _iso_currency(code: str | None) -> str:
    c = (code or "").upper().strip()
    if c == "TSH":
        return "TZS"
    return c


def _amounts_match_for_payment(
    expected: Decimal,
    actual: Decimal | None,
    payment_currency: str,
    pesapal_currency: str | None,
) -> bool:
    """Lenient compare — do not fail completed Pesapal tx on TSH/TZS label or rounding."""
    if actual is None:
        return True
    if _iso_currency(payment_currency) != _iso_currency(pesapal_currency):
        logger.warning(
            "Pesapal currency %s vs payment %s — skipping strict amount check",
            pesapal_currency,
            payment_currency,
        )
        return True
    return abs(expected - actual) <= Decimal("0.05")


def _complete_cart_payment_success(
    pay: CartOrderPayment,
    order: Order,
    *,
    tracking: str = "",
) -> None:
    """Mark order paid, advance fulfillment, queue itemized confirmation email."""
    order.status = Order.STATUS_PAID
    update_fields = ["status"]
    if tracking:
        order.transaction_id = tracking[:255]
        update_fields.append("transaction_id")
    order.save(update_fields=update_fields)

    ff, _ = CartOrderFulfillment.objects.get_or_create(
        order=order,
        defaults={"status": CartOrderFulfillment.ST_PENDING},
    )
    if ff.status == CartOrderFulfillment.ST_PENDING:
        ff.status = CartOrderFulfillment.ST_PROCESSING
        ff.save(update_fields=["status", "updated_at"])
    order.fulfillment_status = ff.status
    order.save(update_fields=["fulfillment_status"])

    order_id = order.pk
    pay_id = pay.pk

    def _send_confirmation_email() -> None:
        try:
            order_ref = Order.objects.select_related("user", "representative").get(
                pk=order_id
            )
            pay_ref = CartOrderPayment.objects.get(pk=pay_id)
            notify_order_payment_completed(order_ref, payment=pay_ref)
        except Exception:
            logger.exception(
                "Cart payment confirmation email failed order_id=%s payment_id=%s",
                order_id,
                pay_id,
            )

    transaction.on_commit(_send_confirmation_email)


def _notify_partner_payment_success(payment: Payment) -> None:
    """Mark partnership paid + send receipt email (idempotent)."""
    if not payment.partnership_id:
        return
    pship = (
        Partnership.objects.select_related("partner_type", "user")
        .filter(pk=payment.partnership_id)
        .first()
    )
    if not pship:
        return
    if not pship.paid_at:
        pship.paid_at = timezone.now()
        pship.save(update_fields=["paid_at"])
    try:
        from account.partner_recurring_reminders import sync_partnership_reminder_schedule

        sync_partnership_reminder_schedule(pship)
    except Exception:
        logger.exception(
            "Partner recurring reminder schedule failed payment_id=%s partnership_id=%s",
            payment.id,
            payment.partnership_id,
        )
    try:
        from account import email as account_email

        account_email.send_partner_giving_paid_confirmation(
            partnership=pship, payment=payment
        )
    except Exception:
        logger.exception(
            "Partner confirmation email failed payment_id=%s partnership_id=%s",
            payment.id,
            payment.partnership_id,
        )


def _record_history(
    *,
    payment_kind: str,
    payment_id: int,
    provider: str,
    from_status: str,
    to_status: str,
    merchant_reference: str = "",
    order_tracking_id: str = "",
    amount: Decimal | None = None,
    currency: str = "",
    note: str = "",
    raw: dict | None = None,
) -> None:
    """
    Upsert a single TransactionHistory row per (payment_kind, payment_id).
    ``from_status`` is set once at creation (initial state); later updates only change ``to_status``.
    """
    if from_status == to_status:
        return

    tx = (
        TransactionHistory.objects.filter(
            payment_kind=payment_kind,
            payment_id=payment_id,
        )
        .order_by("pk")
        .first()
    )
    if tx is None:
        TransactionHistory.objects.create(
            payment_kind=payment_kind,
            payment_id=payment_id,
            provider=provider,
            from_status=from_status,
            to_status=to_status,
            merchant_reference=merchant_reference[:255],
            order_tracking_id=order_tracking_id[:255],
            amount=amount,
            currency=currency[:3] if currency else "",
            note=note[:255],
            raw_provider_response=raw,
        )
        return

    update_fields = ["to_status", "provider", "note", "updated_at"]
    tx.to_status = to_status
    tx.provider = provider
    tx.note = note[:255]
    if merchant_reference:
        tx.merchant_reference = merchant_reference[:255]
        update_fields.append("merchant_reference")
    if order_tracking_id:
        tx.order_tracking_id = order_tracking_id[:255]
        update_fields.append("order_tracking_id")
    if amount is not None:
        tx.amount = amount
        update_fields.append("amount")
    if currency:
        tx.currency = currency[:3]
        update_fields.append("currency")
    if raw is not None:
        tx.raw_provider_response = raw
        update_fields.append("raw_provider_response")
    tx.save(update_fields=update_fields)


def _webhook_outcome_rank(outcome: str) -> int:
    """Higher = terminal / preferred display outcome when merging IPN + poll logs."""
    o = (outcome or "").strip().lower()
    if o == "success":
        return 100
    if o == "failed":
        return 90
    if o.startswith("status_error"):
        return 85
    if o == "still_pending":
        return 50
    if o in ("idempotent_skip", "idempotent_skip_locked"):
        return 40
    if o.startswith("matched:"):
        return 25
    if o == "received":
        return 15
    if o == "missing_tracking_id":
        return 10
    return 20


def _merge_webhook_payload(existing: Any, incoming: dict) -> dict:
    base = dict(existing) if isinstance(existing, dict) else {}
    for key, val in incoming.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            base[key] = {**base[key], **val}
        else:
            base[key] = val
    return base


def _upsert_webhook_log(
    *,
    payment_kind: str,
    payment_id: int,
    source: str,
    outcome: str,
    payload: dict,
    merchant_reference: str = "",
    order_tracking_id: str = "",
    http_status: int = 200,
) -> PaymentWebhookLog:
    """One PaymentWebhookLog per (payment_kind, payment_id); merge IPN + poll events."""
    lookup: dict[str, Any] = {"payment_kind": payment_kind}
    create_fields: dict[str, Any] = {
        "source": source,
        "payment_kind": payment_kind,
        "payload": payload,
        "merchant_reference": merchant_reference[:255],
        "order_tracking_id": order_tracking_id[:255],
        "outcome": outcome[:120],
        "http_status_returned": http_status,
    }
    if payment_kind == PaymentWebhookLog.KIND_PARTNERSHIP:
        lookup["matched_payment_id"] = payment_id
        create_fields["matched_payment_id"] = payment_id
    else:
        lookup["matched_cart_payment_id"] = payment_id
        create_fields["matched_cart_payment_id"] = payment_id

    log = PaymentWebhookLog.objects.filter(**lookup).order_by("pk").first()
    if log is None:
        return PaymentWebhookLog.objects.create(**create_fields)

    update_fields = ["updated_at"]
    log.payload = _merge_webhook_payload(log.payload, payload)
    update_fields.append("payload")

    if _webhook_outcome_rank(outcome) >= _webhook_outcome_rank(log.outcome or ""):
        log.outcome = outcome[:120]
        update_fields.append("outcome")
    if source == PaymentWebhookLog.SOURCE_PESAPAL_IPN:
        log.source = source
        update_fields.append("source")
    elif log.source != PaymentWebhookLog.SOURCE_PESAPAL_IPN:
        log.source = source
        update_fields.append("source")

    if merchant_reference:
        log.merchant_reference = merchant_reference[:255]
        update_fields.append("merchant_reference")
    if order_tracking_id:
        log.order_tracking_id = order_tracking_id[:255]
        update_fields.append("order_tracking_id")
    log.http_status_returned = http_status
    update_fields.append("http_status_returned")
    log.save(update_fields=update_fields)
    return log


def _save_webhook_log(
    log: PaymentWebhookLog,
    *,
    outcome: str,
    source: str | None = None,
    payload_patch: dict | None = None,
    http_status: int | None = None,
) -> PaymentWebhookLog:
    """Update webhook log row; upserts when payment is matched."""
    payment_id = None
    if log.payment_kind == PaymentWebhookLog.KIND_PARTNERSHIP and log.matched_payment_id:
        payment_id = log.matched_payment_id
    elif log.payment_kind == PaymentWebhookLog.KIND_CART and log.matched_cart_payment_id:
        payment_id = log.matched_cart_payment_id

    if payment_id:
        return _upsert_webhook_log(
            payment_kind=log.payment_kind,
            payment_id=payment_id,
            source=source or log.source,
            outcome=outcome,
            payload=payload_patch or (log.payload if isinstance(log.payload, dict) else {}),
            merchant_reference=log.merchant_reference or "",
            order_tracking_id=log.order_tracking_id or "",
            http_status=http_status if http_status is not None else log.http_status_returned,
        )

    log.outcome = outcome[:120]
    uf = ["outcome", "updated_at"]
    if payload_patch is not None:
        log.payload = _merge_webhook_payload(log.payload, payload_patch)
        uf.append("payload")
    if source:
        log.source = source
        uf.append("source")
    if http_status is not None:
        log.http_status_returned = http_status
        uf.append("http_status_returned")
    log.save(update_fields=uf)
    return log


def _record_status_sync_audit(
    *,
    payment_kind: str,
    payment_id: int,
    provider: str,
    from_status: str,
    to_status: str,
    outcome: str,
    merchant_reference: str = "",
    order_tracking_id: str = "",
    amount: Decimal | None = None,
    currency: str = "",
    note: str = "",
    raw: dict | None = None,
) -> None:
    """
    Record status transition from Pesapal GetTransactionStatus (status poll / sync API).
    Updates both TransactionHistory and PaymentWebhookLog in the payments app.
    """
    if from_status == to_status:
        return

    _record_history(
        payment_kind=payment_kind,
        payment_id=payment_id,
        provider=provider,
        from_status=from_status,
        to_status=to_status,
        merchant_reference=merchant_reference,
        order_tracking_id=order_tracking_id,
        amount=amount,
        currency=currency,
        note=note,
        raw=raw,
    )

    _upsert_webhook_log(
        payment_kind=payment_kind,
        payment_id=payment_id,
        source=PaymentWebhookLog.SOURCE_PESAPAL_STATUS_SYNC,
        outcome=outcome,
        payload={
            "sync_type": "status_poll",
            "from_status": from_status,
            "to_status": to_status,
            "provider_response": raw or {},
        },
        merchant_reference=merchant_reference,
        order_tracking_id=order_tracking_id,
        http_status=200,
    )


def _billing_from_request(data: dict, user=None, partnership: Partnership | None = None) -> dict[str, Any]:
    email = (data.get("email") or data.get("email_address") or "").strip()
    phone = (data.get("phone_number") or data.get("phone") or "").strip()
    if partnership and not email:
        if partnership.user_id and partnership.user:
            email = getattr(partnership.user, "email", "") or ""
        elif partnership.guest_email:
            email = partnership.guest_email
    if user and not email:
        email = getattr(user, "email", "") or ""
    billing: dict[str, Any] = {}
    if email:
        billing["email_address"] = email
    if phone:
        billing["phone_number"] = phone
    for key in ("first_name", "middle_name", "last_name", "country_code", "line_1", "city"):
        val = data.get(key)
        if val:
            billing[key] = str(val).strip()
    if partnership:
        if partnership.street and "line_1" not in billing:
            billing["line_1"] = partnership.street
        if partnership.district and "city" not in billing:
            billing["city"] = partnership.district
    if not billing.get("email_address") and not billing.get("phone_number"):
        billing["email_address"] = email or "customer@mpanzi.local"
    billing.setdefault("country_code", "TZ")
    return billing


class PaymentService:
    def __init__(self, provider: PesapalProvider | None = None) -> None:
        self.provider = provider or get_default_provider()

    def initiate_partnership_payment(
        self,
        partnership: Partnership,
        billing_data: dict | None = None,
    ) -> tuple[Payment, dict[str, Any]]:
        from payments.utils.references import new_merchant_reference

        billing_data = billing_data or {}
        external_ref = new_merchant_reference("PG")
        currency = partnership_currency_iso(partnership.currency)

        with transaction.atomic():
            payment = Payment.objects.create(
                partnership=partnership,
                amount=partnership.amount,
                external_reference=external_ref,
                status=Payment.STATUS_PENDING,
                provider=Payment.PROVIDER_PESAPAL,
                currency=currency,
            )

        description = (
            f"Partner giving — {partnership.partner_type.name if partnership.partner_type_id else 'Gift'}"
        )[:100]

        try:
            result = self.provider.create_checkout(
                merchant_reference=external_ref,
                amount=partnership.amount,
                currency=currency,
                description=description,
                callback_url="",  # uses settings default
                billing_address=_billing_from_request(billing_data, partnership=partnership),
                metadata={
                    "partnershipId": partnership.id,
                    "paymentId": payment.id,
                    "kind": "partnership",
                },
            )
        except PesapalConfigurationError:
            payment.status = Payment.STATUS_FAILED
            payment.save(update_fields=["status"])
            raise

        if not result.success:
            payment.status = Payment.STATUS_FAILED
            payment.raw_response = result.raw_response
            payment.save(update_fields=["status", "raw_response"])
            return payment, {
                "success": False,
                "payment_id": payment.id,
                "detail": result.error_message or "Checkout failed",
            }

        pesapal_merchant_ref = (
            (result.raw_response or {}).get("merchant_reference")
            or result.merchant_reference
            or external_ref
        )
        if pesapal_merchant_ref and pesapal_merchant_ref != payment.external_reference:
            payment.external_reference = str(pesapal_merchant_ref)[:255]
            logger.info(
                "Pesapal submit merchant_reference=%r stored on payment_id=%s (sent id=%r)",
                pesapal_merchant_ref,
                payment.id,
                external_ref,
            )

        payment.provider_transaction_id = result.order_tracking_id
        payment.checkout_url = result.redirect_url
        payment.order_tracking_id = result.order_tracking_id
        payment.raw_response = result.raw_response
        payment.metadata = {
            "kind": "partnership",
            "paymentId": payment.id,
            "partnershipId": partnership.id,
            "submit_id": external_ref,
            "pesapal_merchant_reference": pesapal_merchant_ref,
        }
        payment.save(
            update_fields=[
                "external_reference",
                "provider_transaction_id",
                "checkout_url",
                "order_tracking_id",
                "raw_response",
                "metadata",
            ]
        )
        _record_history(
            payment_kind=TransactionHistory.KIND_PARTNERSHIP,
            payment_id=payment.id,
            provider=Payment.PROVIDER_PESAPAL,
            from_status=Payment.STATUS_PENDING,
            to_status=Payment.STATUS_PROCESSING,
            merchant_reference=payment.external_reference or external_ref,
            order_tracking_id=result.order_tracking_id or "",
            amount=partnership.amount,
            currency=currency,
            note="checkout_created",
        )
        payment.status = Payment.STATUS_PROCESSING
        payment.save(update_fields=["status"])

        return payment, {
            "success": True,
            "payment_id": payment.id,
            "partnership_id": partnership.id,
            "external_reference": external_ref,
            "checkout_url": result.redirect_url,
            "redirect_url": result.redirect_url,
            "order_tracking_id": result.order_tracking_id,
            "status": "PROCESSING",
            "message": "Redirect to Pesapal to complete payment.",
        }

    def initiate_cart_payment(
        self,
        order: Order,
        user,
        billing_data: dict | None = None,
    ) -> tuple[CartOrderPayment, dict[str, Any]]:
        from payments.utils.references import new_merchant_reference

        billing_data = billing_data or {}
        external_ref = new_merchant_reference("CT")

        pay = CartOrderPayment.objects.create(
            order=order,
            amount=order.total_amount,
            currency="TZS",
            status=CartOrderPayment.STATUS_PENDING,
            external_reference=external_ref,
            provider=CartOrderPayment.PROVIDER_PESAPAL,
        )

        description = f"Mpanzi marketplace order #{order.id}"[:100]

        try:
            result = self.provider.create_checkout(
                merchant_reference=external_ref,
                amount=order.total_amount,
                currency="TZS",
                description=description,
                callback_url="",
                billing_address=_billing_from_request(billing_data, user=user),
                metadata={
                    "cartPaymentId": pay.id,
                    "orderId": order.id,
                    "kind": "marketplace_cart",
                },
            )
        except PesapalConfigurationError:
            pay.delete()
            raise

        if not result.success:
            pay.status = CartOrderPayment.STATUS_FAILED
            pay.raw_initiate_response = result.raw_response
            pay.save(update_fields=["status", "raw_initiate_response"])
            return pay, {
                "success": False,
                "payment_id": pay.id,
                "detail": result.error_message or "Checkout failed",
            }

        pay.provider_transaction_id = result.order_tracking_id
        pay.checkout_url = result.redirect_url
        pay.order_tracking_id = result.order_tracking_id
        pesapal_merchant_ref = (
            (result.raw_response or {}).get("merchant_reference")
            or result.merchant_reference
            or external_ref
        )
        if pesapal_merchant_ref and pesapal_merchant_ref != pay.external_reference:
            pay.external_reference = str(pesapal_merchant_ref)[:255]

        pay.raw_initiate_response = result.raw_response
        pay.status = CartOrderPayment.STATUS_PROCESSING
        pay.metadata = {
            "kind": "marketplace_cart",
            "cartPaymentId": pay.id,
            "orderId": order.id,
            "submit_id": external_ref,
            "pesapal_merchant_reference": pesapal_merchant_ref,
        }
        pay.save(
            update_fields=[
                "external_reference",
                "provider_transaction_id",
                "checkout_url",
                "order_tracking_id",
                "raw_initiate_response",
                "status",
                "metadata",
            ]
        )

        order.status = Order.STATUS_PROCESSING
        order.payment_method = Order.PAYMENT_CARD
        # Order.external_reference is max 100 chars (CartOrderPayment allows 255).
        order.external_reference = str(pesapal_merchant_ref or external_ref)[:100]
        order.save(update_fields=["status", "payment_method", "external_reference"])

        _record_history(
            payment_kind=TransactionHistory.KIND_CART,
            payment_id=pay.id,
            provider=CartOrderPayment.PROVIDER_PESAPAL,
            from_status=CartOrderPayment.STATUS_PENDING,
            to_status=CartOrderPayment.STATUS_PROCESSING,
            merchant_reference=external_ref,
            order_tracking_id=result.order_tracking_id or "",
            amount=order.total_amount,
            currency="TZS",
            note="checkout_created",
        )

        return pay, {
            "success": True,
            "payment_id": pay.id,
            "order_id": order.id,
            "external_reference": external_ref,
            "checkout_url": result.redirect_url,
            "redirect_url": result.redirect_url,
            "order_tracking_id": result.order_tracking_id,
            "status": "PROCESSING",
            "message": "Redirect to Pesapal to complete payment.",
        }

    def process_ipn_payload(self, payload: dict) -> dict[str, Any]:
        """
        Handle Pesapal IPN (GET query or POST JSON).
        Always returns dict suitable for HTTP 200 JSON response to Pesapal.
        """
        close_old_connections()
        fields = extract_pesapal_ipn_fields(payload if isinstance(payload, dict) else {})

        logger.info(
            "Pesapal IPN reconcile tracking=%r merchant=%r type=%r",
            fields.order_tracking_id or "(empty)",
            fields.merchant_reference or "(empty)",
            fields.notification_type or "(empty)",
        )

        status_merchant_ref = ""
        pay = None
        cart_pay = None

        for attempt in range(1, IPN_LOOKUP_ATTEMPTS + 1):
            close_old_connections()
            pay = resolve_partner_payment_from_ipn(
                fields, status_merchant_reference=status_merchant_ref
            )
            cart_pay = resolve_cart_payment_from_ipn(
                fields, status_merchant_reference=status_merchant_ref
            )
            if pay or cart_pay:
                if attempt > 1:
                    logger.info(
                        "Pesapal IPN matched after %s attempts payment=%s cart=%s",
                        attempt,
                        getattr(pay, "id", None),
                        getattr(cart_pay, "id", None),
                    )
                break
            if attempt < IPN_LOOKUP_ATTEMPTS:
                time.sleep(IPN_LOOKUP_SLEEP_SEC)

        # AzamPay pattern: IPN may arrive before initiate commit — keep retrying above.
        # If still no match but we have tracking id, ask Pesapal for merchant_reference.
        if not pay and not cart_pay and fields.order_tracking_id:
            close_old_connections()
            try:
                status_result = self.provider.get_transaction_status(
                    fields.order_tracking_id
                )
                status_merchant_ref = merchant_reference_from_status_response(
                    status_result.raw_response
                )
                logger.info(
                    "Pesapal IPN fallback GetTransactionStatus tracking=%r merchant=%r",
                    fields.order_tracking_id,
                    status_merchant_ref or "(empty)",
                )
                pay = resolve_partner_payment_from_ipn(
                    fields, status_merchant_reference=status_merchant_ref
                )
                cart_pay = resolve_cart_payment_from_ipn(
                    fields, status_merchant_reference=status_merchant_ref
                )
            except Exception:
                logger.exception(
                    "Pesapal IPN fallback status lookup failed tracking=%r",
                    fields.order_tracking_id,
                )

        if cart_pay:
            tracking = fields.order_tracking_id or cart_pay.order_tracking_id or ""
            log = _upsert_webhook_log(
                payment_kind=PaymentWebhookLog.KIND_CART,
                payment_id=cart_pay.id,
                source=PaymentWebhookLog.SOURCE_PESAPAL_IPN,
                outcome=(
                    f"matched:payment_ref={cart_pay.external_reference!r} "
                    f"ipn_merchant={fields.merchant_reference!r}"
                )[:120],
                payload={"ipn": fields.raw},
                merchant_reference=(fields.merchant_reference or cart_pay.external_reference or ""),
                order_tracking_id=tracking,
            )
            return self._finalize_cart_ipn(cart_pay, tracking, log)

        if pay:
            tracking = fields.order_tracking_id or pay.order_tracking_id or ""
            log = _upsert_webhook_log(
                payment_kind=PaymentWebhookLog.KIND_PARTNERSHIP,
                payment_id=pay.id,
                source=PaymentWebhookLog.SOURCE_PESAPAL_IPN,
                outcome=(
                    f"matched:payment_ref={pay.external_reference!r} "
                    f"ipn_merchant={fields.merchant_reference!r}"
                )[:120],
                payload={"ipn": fields.raw},
                merchant_reference=(fields.merchant_reference or pay.external_reference or ""),
                order_tracking_id=tracking,
            )
            return self._finalize_partner_ipn(pay, tracking, log)

        PaymentWebhookLog.objects.create(
            source=PaymentWebhookLog.SOURCE_PESAPAL_IPN,
            payload=fields.raw,
            merchant_reference=(fields.merchant_reference or "")[:255],
            order_tracking_id=(fields.order_tracking_id or "")[:255],
            outcome="no_match",
        )
        logger.warning(
            "Pesapal IPN: no payment match ipn_merchant=%r ipn_tracking=%r "
            "status_merchant=%r payload_keys=%s",
            fields.merchant_reference,
            fields.order_tracking_id,
            status_merchant_ref,
            list(fields.raw.keys()),
        )
        return {
            "orderNotificationType": fields.notification_type or "IPNCHANGE",
            "orderTrackingId": fields.order_tracking_id,
            "orderMerchantReference": fields.merchant_reference,
            "status": 200,
        }

    def _finalize_partner_ipn(
        self, payment: Payment, order_tracking_id: str, log: PaymentWebhookLog
    ) -> dict[str, Any]:
        close_old_connections()
        tracking = order_tracking_id or payment.order_tracking_id or payment.provider_transaction_id
        if not tracking:
            _save_webhook_log(log, outcome="missing_tracking_id")
            return self._ipn_response(tracking, payment.external_reference or "", 200)

        if payment.status == Payment.STATUS_SUCCESS:
            _save_webhook_log(
                log,
                outcome="success",
                payload_patch={"ipn_note": "idempotent_skip"},
            )
            return self._ipn_response(tracking, payment.external_reference or "", 200)

        try:
            status_result = self.provider.get_transaction_status(tracking)
        except Exception as e:
            logger.exception("Pesapal status check failed payment_id=%s", payment.id)
            _save_webhook_log(log, outcome=f"status_error:{e}", http_status=500)
            return self._ipn_response(tracking, payment.external_reference or "", 500)

        # Reconcile if GetTransactionStatus merchant_reference differs from IPN payload.
        status_mer = merchant_reference_from_status_response(status_result.raw_response)
        if status_mer:
            alt = resolve_partner_payment_from_ipn(
                extract_pesapal_ipn_fields(
                    {
                        "OrderTrackingId": tracking,
                        "OrderMerchantReference": status_mer,
                    }
                ),
                status_merchant_reference=status_mer,
            )
            if alt and alt.pk != payment.pk:
                logger.warning(
                    "Pesapal IPN payment_id=%s superseded by alt payment_id=%s "
                    "via status merchant_reference=%r",
                    payment.id,
                    alt.id,
                    status_mer,
                )
                payment = alt

        with transaction.atomic():
            pay = Payment.objects.select_for_update().get(pk=payment.pk)
            if pay.status == Payment.STATUS_SUCCESS:
                _save_webhook_log(
                    log,
                    outcome="success",
                    payload_patch={"ipn_note": "idempotent_skip_locked"},
                )
                return self._ipn_response(tracking, pay.external_reference or "", 200)

            prev = pay.status
            raw_merge = {**(pay.raw_response or {}), "ipn_status": status_result.raw_response}
            pay.raw_response = raw_merge
            pay.order_tracking_id = tracking
            pay.provider_transaction_id = tracking

            if status_result.payment_method:
                pay.payment_method = str(status_result.payment_method)[:64]

            if status_result.status == "completed" and not _amounts_match_for_payment(
                pay.amount,
                status_result.amount,
                pay.currency or partnership_currency_iso(
                    Partnership.objects.filter(pk=pay.partnership_id)
                    .values_list("currency", flat=True)
                    .first()
                    or ""
                ),
                status_result.currency,
            ):
                logger.error(
                    "Partner payment amount mismatch payment_id=%s expected=%s got=%s — "
                    "still marking SUCCESS (Pesapal completed)",
                    pay.id,
                    pay.amount,
                    status_result.amount,
                )
                meta = pay.metadata or {}
                meta["amount_mismatch_review"] = True
                pay.metadata = meta

            if status_result.status == "completed":
                pay.status = Payment.STATUS_SUCCESS
                pay.completed_at = timezone.now()
                pay.save(
                    update_fields=[
                        "status",
                        "completed_at",
                        "raw_response",
                        "order_tracking_id",
                        "provider_transaction_id",
                        "payment_method",
                        "metadata",
                    ]
                )
                _notify_partner_payment_success(pay)
                _record_history(
                    payment_kind="partnership",
                    payment_id=pay.id,
                    provider=pay.provider,
                    from_status=prev,
                    to_status=pay.status,
                    merchant_reference=pay.external_reference or "",
                    order_tracking_id=tracking,
                    amount=status_result.amount,
                    currency=status_result.currency or "",
                    note="ipn_completed",
                    raw=status_result.raw_response,
                )
                _save_webhook_log(
                    log,
                    outcome="success",
                    payload_patch={"ipn_status": status_result.raw_response},
                )
                return self._ipn_response(tracking, pay.external_reference or "", 200)

            if self._provider_confirmed_failure(status_result):
                pay.status = Payment.STATUS_FAILED
                pay.save(
                    update_fields=[
                        "status",
                        "raw_response",
                        "order_tracking_id",
                        "provider_transaction_id",
                        "payment_method",
                    ]
                )
                _record_history(
                    payment_kind="partnership",
                    payment_id=pay.id,
                    provider=pay.provider,
                    from_status=prev,
                    to_status=pay.status,
                    note="ipn_provider_failed",
                    raw=status_result.raw_response,
                )
                _save_webhook_log(log, outcome="failed")
                return self._ipn_response(tracking, pay.external_reference or "", 200)

            if pay.status not in (Payment.STATUS_SUCCESS, Payment.STATUS_FAILED):
                pay.status = Payment.STATUS_PROCESSING
            pay.save(
                update_fields=[
                    "status",
                    "raw_response",
                    "order_tracking_id",
                    "provider_transaction_id",
                    "payment_method",
                ]
            )
            _save_webhook_log(log, outcome="still_pending")
            return self._ipn_response(tracking, pay.external_reference or "", 200)

    def _finalize_cart_ipn(
        self, payment: CartOrderPayment, order_tracking_id: str, log: PaymentWebhookLog
    ) -> dict[str, Any]:
        close_old_connections()
        tracking = order_tracking_id or payment.order_tracking_id or payment.provider_transaction_id
        if not tracking:
            _save_webhook_log(log, outcome="missing_tracking_id")
            return self._ipn_response(tracking, payment.external_reference, 200)

        if payment.status == CartOrderPayment.STATUS_SUCCESS:
            _save_webhook_log(
                log,
                outcome="success",
                payload_patch={"ipn_note": "idempotent_skip"},
            )
            return self._ipn_response(tracking, payment.external_reference, 200)

        try:
            status_result = self.provider.get_transaction_status(tracking)
        except Exception as e:
            logger.exception("Pesapal cart status check failed payment_id=%s", payment.id)
            _save_webhook_log(log, outcome=f"status_error:{e}", http_status=500)
            return self._ipn_response(tracking, payment.external_reference, 500)

        with transaction.atomic():
            pay = CartOrderPayment.objects.select_for_update().get(pk=payment.pk)
            order = Order.objects.select_for_update().get(pk=pay.order_id)

            if pay.status == CartOrderPayment.STATUS_SUCCESS:
                _save_webhook_log(
                    log,
                    outcome="success",
                    payload_patch={"ipn_note": "idempotent_skip_locked"},
                )
                return self._ipn_response(tracking, pay.external_reference, 200)

            prev = pay.status
            pay.raw_last_webhook = status_result.raw_response
            pay.order_tracking_id = tracking
            pay.provider_transaction_id = tracking
            if status_result.payment_method:
                pay.payment_method = str(status_result.payment_method)[:64]

            if status_result.status == "completed":
                pay.status = CartOrderPayment.STATUS_SUCCESS
                pay.completed_at = timezone.now()
                pay.save(
                    update_fields=[
                        "status",
                        "completed_at",
                        "raw_last_webhook",
                        "order_tracking_id",
                        "provider_transaction_id",
                        "payment_method",
                    ]
                )
                _complete_cart_payment_success(pay, order, tracking=tracking)

                _record_history(
                    payment_kind="cart",
                    payment_id=pay.id,
                    provider=pay.provider,
                    from_status=prev,
                    to_status=pay.status,
                    merchant_reference=pay.external_reference,
                    order_tracking_id=tracking,
                    amount=status_result.amount,
                    currency=status_result.currency or pay.currency,
                    note="ipn_completed",
                    raw=status_result.raw_response,
                )
                _save_webhook_log(
                    log,
                    outcome="success",
                    payload_patch={"ipn_status": status_result.raw_response},
                )
                return self._ipn_response(tracking, pay.external_reference, 200)

            if self._provider_confirmed_failure(status_result):
                pay.status = CartOrderPayment.STATUS_FAILED
                pay.save(
                    update_fields=[
                        "status",
                        "raw_last_webhook",
                        "order_tracking_id",
                        "provider_transaction_id",
                        "payment_method",
                    ]
                )
                if order.status not in (Order.STATUS_PAID,):
                    order.status = Order.STATUS_FAILED
                    order.save(update_fields=["status"])
                _record_history(
                    payment_kind="cart",
                    payment_id=pay.id,
                    provider=pay.provider,
                    from_status=prev,
                    to_status=pay.status,
                    note="ipn_provider_failed",
                    raw=status_result.raw_response,
                )
                _save_webhook_log(log, outcome="failed")
                return self._ipn_response(tracking, pay.external_reference, 200)

            if pay.status not in (
                CartOrderPayment.STATUS_SUCCESS,
                CartOrderPayment.STATUS_FAILED,
            ):
                pay.status = CartOrderPayment.STATUS_PROCESSING
            pay.save(
                update_fields=[
                    "status",
                    "raw_last_webhook",
                    "order_tracking_id",
                    "provider_transaction_id",
                    "payment_method",
                ]
            )
            _save_webhook_log(log, outcome="still_pending")
            return self._ipn_response(tracking, pay.external_reference, 200)

    @staticmethod
    def _ipn_response(order_tracking_id: str, merchant_ref: str, status: int) -> dict:
        return {
            "orderNotificationType": "IPNCHANGE",
            "orderTrackingId": order_tracking_id or "",
            "orderMerchantReference": merchant_ref or "",
            "status": status,
        }

    def verify_and_sync_partner_payment(self, payment: Payment) -> Payment:
        """Poll Pesapal and update partner payment (status poll / recovery after late IPN)."""
        tracking = payment.order_tracking_id or payment.provider_transaction_id
        if not tracking:
            return payment
        if payment.status == Payment.STATUS_SUCCESS:
            return payment
        status_result = self.provider.get_transaction_status(tracking)
        self._apply_partner_status(payment, status_result)
        return Payment.objects.select_related("partnership").get(pk=payment.pk)

    def verify_and_sync_cart_payment(self, payment: CartOrderPayment) -> CartOrderPayment:
        tracking = payment.order_tracking_id or payment.provider_transaction_id
        if not tracking:
            return payment
        if payment.status == CartOrderPayment.STATUS_SUCCESS:
            return payment
        status_result = self.provider.get_transaction_status(tracking)
        self._apply_cart_status(payment, status_result)
        return CartOrderPayment.objects.select_related("order").get(pk=payment.pk)

    def _apply_partner_status(self, payment: Payment, status_result) -> None:
        with transaction.atomic():
            pay = Payment.objects.select_for_update().get(pk=payment.pk)
            if pay.status == Payment.STATUS_SUCCESS:
                return

            prev = pay.status
            tracking = pay.order_tracking_id or pay.provider_transaction_id or ""
            raw_merge = {**(pay.raw_response or {}), "status_poll": status_result.raw_response}
            pay.raw_response = raw_merge
            if status_result.payment_method:
                pay.payment_method = str(status_result.payment_method)[:64]

            if status_result.status == "completed":
                pay.status = Payment.STATUS_SUCCESS
                pay.completed_at = timezone.now()
                pay.save(
                    update_fields=[
                        "status",
                        "completed_at",
                        "raw_response",
                        "payment_method",
                    ]
                )
                _record_status_sync_audit(
                    payment_kind=TransactionHistory.KIND_PARTNERSHIP,
                    payment_id=pay.id,
                    provider=pay.provider,
                    from_status=prev,
                    to_status=pay.status,
                    outcome="success",
                    merchant_reference=pay.external_reference or "",
                    order_tracking_id=tracking,
                    amount=status_result.amount,
                    currency=status_result.currency or pay.currency or "",
                    note="status_poll_completed",
                    raw=status_result.raw_response,
                )
                transaction.on_commit(lambda: _notify_partner_payment_success(pay))
            elif self._provider_confirmed_failure(status_result):
                if pay.status != Payment.STATUS_SUCCESS:
                    pay.status = Payment.STATUS_FAILED
                    pay.save(update_fields=["status", "raw_response", "payment_method"])
                    _record_status_sync_audit(
                        payment_kind=TransactionHistory.KIND_PARTNERSHIP,
                        payment_id=pay.id,
                        provider=pay.provider,
                        from_status=prev,
                        to_status=pay.status,
                        outcome="failed",
                        merchant_reference=pay.external_reference or "",
                        order_tracking_id=tracking,
                        amount=status_result.amount,
                        currency=status_result.currency or pay.currency or "",
                        note="status_poll_failed",
                        raw=status_result.raw_response,
                    )
            else:
                if pay.status not in (Payment.STATUS_SUCCESS, Payment.STATUS_FAILED):
                    pay.status = Payment.STATUS_PROCESSING
                    pay.save(update_fields=["status", "raw_response", "payment_method"])
                    if prev != pay.status:
                        _record_status_sync_audit(
                            payment_kind=TransactionHistory.KIND_PARTNERSHIP,
                            payment_id=pay.id,
                            provider=pay.provider,
                            from_status=prev,
                            to_status=pay.status,
                            outcome="still_pending",
                            merchant_reference=pay.external_reference or "",
                            order_tracking_id=tracking,
                            note="status_poll_processing",
                            raw=status_result.raw_response,
                        )

    @staticmethod
    def _provider_confirmed_failure(status_result) -> bool:
        from payments.services.status_api import pesapal_is_confirmed_failure

        return pesapal_is_confirmed_failure(status_result)

    def _apply_cart_status(self, payment: CartOrderPayment, status_result) -> None:
        with transaction.atomic():
            pay = CartOrderPayment.objects.select_for_update().get(pk=payment.pk)
            order = Order.objects.select_for_update().get(pk=pay.order_id)
            if pay.status == CartOrderPayment.STATUS_SUCCESS:
                return

            prev = pay.status
            tracking = pay.order_tracking_id or pay.provider_transaction_id or ""

            if status_result.status == "completed":
                pay.status = CartOrderPayment.STATUS_SUCCESS
                pay.completed_at = timezone.now()
                pay.save(
                    update_fields=[
                        "status",
                        "completed_at",
                    ]
                )
                _complete_cart_payment_success(pay, order, tracking=tracking)
                _record_status_sync_audit(
                    payment_kind=TransactionHistory.KIND_CART,
                    payment_id=pay.id,
                    provider=pay.provider,
                    from_status=prev,
                    to_status=pay.status,
                    outcome="success",
                    merchant_reference=pay.external_reference or "",
                    order_tracking_id=tracking,
                    amount=status_result.amount,
                    currency=status_result.currency or pay.currency,
                    note="status_poll_completed",
                    raw=status_result.raw_response,
                )
            elif self._provider_confirmed_failure(status_result):
                pay.status = CartOrderPayment.STATUS_FAILED
                pay.save(update_fields=["status"])
                if order.status != Order.STATUS_PAID:
                    order.status = Order.STATUS_FAILED
                    order.save(update_fields=["status"])
                _record_status_sync_audit(
                    payment_kind=TransactionHistory.KIND_CART,
                    payment_id=pay.id,
                    provider=pay.provider,
                    from_status=prev,
                    to_status=pay.status,
                    outcome="failed",
                    merchant_reference=pay.external_reference or "",
                    order_tracking_id=tracking,
                    amount=status_result.amount,
                    currency=status_result.currency or pay.currency,
                    note="status_poll_failed",
                    raw=status_result.raw_response,
                )
            elif pay.status not in (
                CartOrderPayment.STATUS_SUCCESS,
                CartOrderPayment.STATUS_FAILED,
            ):
                pay.status = CartOrderPayment.STATUS_PROCESSING
                pay.save(update_fields=["status"])
                if prev != pay.status:
                    _record_status_sync_audit(
                        payment_kind=TransactionHistory.KIND_CART,
                        payment_id=pay.id,
                        provider=pay.provider,
                        from_status=prev,
                        to_status=pay.status,
                        outcome="still_pending",
                        merchant_reference=pay.external_reference or "",
                        order_tracking_id=tracking,
                        note="status_poll_processing",
                        raw=status_result.raw_response,
                    )
