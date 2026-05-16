"""Resolve AzamPay webhook payloads to `CartOrderPayment` rows (cart checkout only)."""
from __future__ import annotations

import json

from django.db.models import Q

from .models import CartOrderPayment


def _normalize_identifier(value: str | None) -> str:
    if not value:
        return ""
    return "".join(c for c in str(value).strip().lower() if c.isalnum())


def _first_nonempty_str(payload: dict, *keys: str) -> str:
    for k in keys:
        v = payload.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def merchant_external_id_from_webhook(payload: dict) -> str:
    s = _first_nonempty_str(
        payload,
        "externalreference",
        "externalReference",
        "ExternalReference",
        "external_reference",
        "external_id",
        "externalId",
    )
    if s:
        return s
    for key, val in payload.items():
        if not isinstance(key, str) or val is None:
            continue
        norm_key = key.lower().replace("-", "").replace("_", "")
        if norm_key in ("externalreference", "externalid"):
            cand = str(val).strip()
            if cand:
                return cand
    return ""


def gateway_transaction_id_from_webhook(payload: dict) -> str:
    return _first_nonempty_str(
        payload,
        "transid",
        "transId",
        "mnoreference",
        "mnoReference",
        "transactionId",
        "transaction_id",
        "pgTransactionId",
        "reference",
        "Reference",
    )


def resolve_cart_payment_for_webhook(
    merchant_external_raw: str, gateway_tx_raw: str
) -> CartOrderPayment | None:
    mer_norm = _normalize_identifier(merchant_external_raw)
    raw_mer = (merchant_external_raw or "").strip()
    gid = (gateway_tx_raw or "").strip()

    if mer_norm:
        p = (
            CartOrderPayment.objects.filter(
                Q(external_reference_norm=mer_norm)
                | Q(external_reference__iexact=raw_mer)
            )
            .order_by("-id")
            .first()
        )
        if p:
            return p

    if gid:
        p = (
            CartOrderPayment.objects.filter(provider_transaction_id=gid)
            .order_by("-id")
            .first()
        )
        if p:
            return p
        gnorm = _normalize_identifier(gid)
        if gnorm and gnorm != mer_norm:
            p = (
                CartOrderPayment.objects.filter(
                    Q(external_reference_norm=gnorm)
                    | Q(external_reference__iexact=gid)
                )
                .order_by("-id")
                .first()
            )
            if p:
                return p

    return None


def _additional_properties_dict(payload: dict) -> dict | None:
    """AzamPay may echo `additionalProperties` as dict or JSON string (any casing)."""
    raw = payload.get("additionalProperties")
    if raw is None:
        raw = payload.get("additionalproperties")
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    if isinstance(raw, dict):
        return raw
    return None


def _resolve_via_additional_properties(payload: dict) -> CartOrderPayment | None:
    """Match checkout `additionalProperties` (cartPaymentId / orderId) echoed on webhooks."""
    addl = _additional_properties_dict(payload)
    if not addl:
        return None
    cpid = addl.get("cartPaymentId") or addl.get("cart_payment_id")
    if cpid is not None:
        try:
            p = CartOrderPayment.objects.filter(pk=int(cpid)).first()
            if p:
                return p
        except (TypeError, ValueError):
            pass
    kind = (addl.get("kind") or "").strip().lower()
    oid = addl.get("orderId") or addl.get("order_id")
    if kind == "marketplace_cart" and oid is not None:
        try:
            oid_int = int(oid)
            return (
                CartOrderPayment.objects.filter(
                    order_id=oid_int,
                    status=CartOrderPayment.STATUS_PENDING,
                )
                .order_by("-id")
                .first()
            )
        except (TypeError, ValueError):
            pass
    return None


def resolve_cart_payment_from_payload(payload: dict) -> CartOrderPayment | None:
    """Resolve cart payment using additionalProperties, external id, trans id, and `reference`."""
    p = _resolve_via_additional_properties(payload)
    if p:
        return p

    mer = merchant_external_id_from_webhook(payload)
    gw = gateway_transaction_id_from_webhook(payload)
    p = resolve_cart_payment_for_webhook(mer, gw)
    if p:
        return p
    ref = _first_nonempty_str(payload, "reference", "Reference")
    if not ref:
        return None
    r = ref.strip()
    rn = _normalize_identifier(r)
    return (
        CartOrderPayment.objects.filter(
            Q(external_reference_norm=rn)
            | Q(external_reference__iexact=r)
            | Q(provider_transaction_id=r)
        )
        .order_by("-id")
        .first()
    )
