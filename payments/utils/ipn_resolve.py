"""
Pesapal IPN field extraction and payment matching (AzamPay-style resilience).

Primary key: order_tracking_id (saved at checkout).
Secondary: merchant reference (normalized + hyphen-insensitive).
Fallback: paymentId / cartPaymentId embedded in metadata or payload.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import close_old_connections
from django.db.models import Q, Value
from django.db.models.functions import Lower, Replace

from account.models import Payment
from cart_payment.models import CartOrderPayment
from payments.utils.references import normalize_merchant_reference

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PesapalIpnFields:
    order_tracking_id: str
    merchant_reference: str
    notification_type: str
    raw: dict


def _first_nonempty(payload: dict, *keys: str) -> str:
    for key in keys:
        val = payload.get(key)
        if val is None:
            continue
        s = str(val).strip()
        if s:
            return s
    return ""


def extract_pesapal_ipn_fields(payload: dict) -> PesapalIpnFields:
    """Read IPN/callback fields with Pesapal naming variants (GET query or POST JSON)."""
    if not isinstance(payload, dict):
        payload = {}

    merchant = _first_nonempty(
        payload,
        "OrderMerchantReference",
        "orderMerchantReference",
        "order_merchant_reference",
        "merchant_reference",
        "merchantReference",
        "MerchantReference",
        "id",
    )
    if not merchant:
        for key, val in payload.items():
            if not isinstance(key, str) or val is None:
                continue
            nk = key.lower().replace("-", "").replace("_", "")
            if nk in ("ordermerchantreference", "merchantreference", "merchantreferenceid"):
                cand = str(val).strip()
                if cand:
                    merchant = cand
                    break

    tracking = _first_nonempty(
        payload,
        "OrderTrackingId",
        "orderTrackingId",
        "order_tracking_id",
        "orderTrackingID",
        "OrderTrackingID",
    )
    if not tracking:
        for key, val in payload.items():
            if not isinstance(key, str) or val is None:
                continue
            nk = key.lower().replace("-", "").replace("_", "")
            if nk in ("ordertrackingid",):
                cand = str(val).strip()
                if cand:
                    tracking = cand
                    break

    ntype = _first_nonempty(
        payload,
        "OrderNotificationType",
        "orderNotificationType",
        "order_notification_type",
    )

    return PesapalIpnFields(
        order_tracking_id=tracking,
        merchant_reference=merchant,
        notification_type=ntype,
        raw=payload,
    )


def _payment_by_norm_ref(model, merchant_raw: str):
    """Match external_reference_norm or hyphen-stripped external_reference."""
    mer_norm = normalize_merchant_reference(merchant_raw)
    raw_mer = (merchant_raw or "").strip()
    if mer_norm:
        p = (
            model.objects.filter(
                Q(external_reference_norm=mer_norm)
                | Q(external_reference__iexact=raw_mer)
            )
            .order_by("-id")
            .first()
        )
        if p:
            return p
        p = (
            model.objects.exclude(external_reference__isnull=True)
            .exclude(external_reference="")
            .annotate(
                _xref=Lower(
                    Replace(
                        Replace("external_reference", Value("-"), Value("")),
                        Value(" "),
                        Value(""),
                    )
                )
            )
            .filter(_xref=mer_norm)
            .order_by("-id")
            .first()
        )
        if p:
            return p
    return None


def _payment_by_tracking_id(model, tracking: str):
    tid = (tracking or "").strip()
    if not tid:
        return None
    p = model.objects.filter(order_tracking_id=tid).order_by("-id").first()
    if p:
        return p
    p = model.objects.filter(provider_transaction_id=tid).order_by("-id").first()
    if p:
        return p
    return None


def _int_from_payload(payload: dict, *keys: str) -> int | None:
    for key in keys:
        val = payload.get(key)
        if val is None:
            continue
        try:
            return int(val)
        except (TypeError, ValueError):
            continue
    return None


def resolve_partner_payment_from_ipn(
    fields: PesapalIpnFields,
    *,
    status_merchant_reference: str | None = None,
) -> Payment | None:
    """
    Resolve account.Payment for partner giving.

    Order of precedence (AzamPay lesson: gateway id before merchant string):
    1. order_tracking_id
    2. merchant_reference from IPN
    3. merchant_reference from GetTransactionStatus
    4. paymentId in payload / metadata
    """
    close_old_connections()

    pay = _payment_by_tracking_id(Payment, fields.order_tracking_id)
    if pay and pay.partnership_id:
        return pay

    for mer in (fields.merchant_reference, status_merchant_reference or ""):
        if not mer:
            continue
        pay = _payment_by_norm_ref(Payment, mer)
        if pay and pay.partnership_id:
            if mer != (pay.external_reference or ""):
                logger.info(
                    "Pesapal IPN merchant ref %r matched payment_id=%s db_ref=%r via norm",
                    mer,
                    pay.id,
                    pay.external_reference,
                )
            return pay

    pay_pk = _int_from_payload(
        fields.raw,
        "paymentId",
        "payment_id",
        "PaymentId",
    )
    if pay_pk:
        pay = Payment.objects.filter(pk=pay_pk, partnership__isnull=False).first()
        if pay:
            logger.info("Pesapal IPN matched partner payment_id=%s via payload paymentId", pay.id)
            return pay

    meta_pay = _int_from_payload(fields.raw, "payment_id")
    if meta_pay:
        pay = Payment.objects.filter(pk=meta_pay, partnership__isnull=False).first()
        if pay:
            return pay

    return None


def resolve_cart_payment_from_ipn(
    fields: PesapalIpnFields,
    *,
    status_merchant_reference: str | None = None,
) -> CartOrderPayment | None:
    close_old_connections()

    pay = _payment_by_tracking_id(CartOrderPayment, fields.order_tracking_id)
    if pay:
        return pay

    for mer in (fields.merchant_reference, status_merchant_reference or ""):
        if not mer:
            continue
        pay = _payment_by_norm_ref(CartOrderPayment, mer)
        if pay:
            return pay

    cart_pk = _int_from_payload(
        fields.raw, "cartPaymentId", "cart_payment_id", "CartPaymentId"
    )
    if cart_pk:
        pay = CartOrderPayment.objects.filter(pk=cart_pk).first()
        if pay:
            return pay

    order_pk = _int_from_payload(fields.raw, "orderId", "order_id")
    if order_pk:
        pay = (
            CartOrderPayment.objects.filter(order_id=order_pk)
            .order_by("-id")
            .first()
        )
        if pay:
            return pay

    return None


def merchant_reference_from_status_response(raw: dict | None) -> str:
    if not isinstance(raw, dict):
        return ""
    return _first_nonempty(
        raw,
        "merchant_reference",
        "MerchantReference",
        "order_merchant_reference",
    )
