"""
Partner giving + AzamPay: initiate MNO checkout, webhook, status polling.

Webhook reconciliation uses `external_reference_norm`, annotated `external_reference`,
`provider_transaction_id`, and a short bounded wait so callbacks that arrive before
the initiate request commits still match once the row is visible.
"""
from __future__ import annotations

import json
import logging
import os
import time
from decimal import Decimal
from uuid import uuid4

from django.db import close_old_connections, transaction
from django.db.models import Q, Value
from django.db.models.functions import Lower, Replace
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from requests.exceptions import (
    ChunkedEncodingError,
    ConnectionError as RequestsConnectionError,
    ReadTimeout,
    RequestException,
)

from .models import Partnership, Payment
from .services.azampay import AzamPayClient, AzamPayConfigurationError, format_amount_string, normalize_tz_msisdn

logger = logging.getLogger(__name__)

VALID_MNO_PROVIDERS = frozenset({"Mpesa", "Tigo", "Airtel", "Halopesa", "Azampesa"})

# Webhook can arrive before the Payment row is committed from initiate (different thread / AzamPay fast path).
WEBHOOK_PAYMENT_LOOKUP_ATTEMPTS = 24
WEBHOOK_PAYMENT_LOOKUP_SLEEP_SEC = 0.5


def _normalize_identifier(value: str | None) -> str:
    """Lowercase alphanumeric only — matches AzamPay echo of externalId / trans ids."""
    if not value:
        return ""
    return "".join(c for c in str(value).strip().lower() if c.isalnum())


def _webhook_first_nonempty_str(payload: dict, *keys: str) -> str:
    for k in keys:
        v = payload.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _webhook_merchant_external_id(payload: dict) -> str:
    """
    Merchant reference sent as checkout `externalId`.
    Do not use `reference` here — AzamPay uses that for an internal reference, not our externalId.
    """
    s = _webhook_first_nonempty_str(
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


def _webhook_gateway_transaction_id(payload: dict) -> str:
    """
    AzamPay may label the gateway/operator transaction id as transid, mnoreference, or reference.
    First non-empty wins (AzamPay field inconsistency).
    """
    return _webhook_first_nonempty_str(
        payload,
        "transid",
        "transId",
        "mnoreference",
        "mnoReference",
        "MnoReference",
        "transactionId",
        "transaction_id",
        "tx_id",
        "pgTransactionId",
        "reference",
        "Reference",
    )


def _webhook_ok(body: dict, status: int = 200):
    return Response(body, status=status)


def resolve_payment_for_webhook(merchant_external_raw: str, gateway_tx_raw: str) -> Payment | None:
    """
    Resolve Payment by merchant external id and/or gateway transaction id.

    Uses indexed `external_reference_norm` when set, plus ORM fallbacks on
    `external_reference` (hyphen-insensitive) for older rows or partial saves.
    Then exact / normalized `provider_transaction_id`.
    """
    mer_norm = _normalize_identifier(merchant_external_raw)
    raw_mer = (merchant_external_raw or "").strip()
    gid = (gateway_tx_raw or "").strip()
    gnorm = _normalize_identifier(gateway_tx_raw)

    if mer_norm:
        p = (
            Payment.objects.filter(
                Q(external_reference_norm=mer_norm)
                | Q(external_reference__iexact=raw_mer)
            )
            .order_by("-id")
            .first()
        )
        if p:
            return p

        p = (
            Payment.objects.exclude(external_reference__isnull=True)
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

    if gid:
        p = Payment.objects.filter(provider_transaction_id=gid).order_by("-id").first()
        if p:
            return p

    if gnorm:
        p = (
            Payment.objects.exclude(provider_transaction_id__isnull=True)
            .exclude(provider_transaction_id="")
            .annotate(
                _txnorm=Lower(
                    Replace(
                        Replace("provider_transaction_id", Value("-"), Value("")),
                        Value(" "),
                        Value(""),
                    )
                )
            )
            .filter(_txnorm=gnorm)
            .order_by("-id")
            .first()
        )
        if p:
            return p

    return None


def _webhook_additional_properties(payload: dict) -> dict:
    addl = payload.get("additionalProperties") or payload.get("additionalproperties")
    if isinstance(addl, str) and addl.strip():
        try:
            parsed = json.loads(addl)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            return {}
    if isinstance(addl, dict):
        return addl
    return {}


def _resolve_payment_via_embedded_ids(payload: dict, merchant_external: str) -> Payment | None:
    """
    Checkout sends partnershipId + paymentId in additionalProperties.
    Some AzamPay environments echo a different externalreference than our externalId; matching
    those ids is still the same callback for the same Payment row.
    """
    addl = _webhook_additional_properties(payload)
    if not addl:
        return None

    raw_pay = addl.get("paymentId") if addl.get("paymentId") is not None else addl.get("payment_id")
    if raw_pay is None:
        return None
    try:
        pay_pk = int(raw_pay)
    except (TypeError, ValueError):
        return None

    qs = Payment.objects.filter(pk=pay_pk, partnership__isnull=False)
    raw_part = addl.get("partnershipId") if addl.get("partnershipId") is not None else addl.get("partnership_id")
    if raw_part is not None:
        try:
            qs = qs.filter(partnership_id=int(raw_part))
        except (TypeError, ValueError):
            return None

    p = qs.first()
    if not p:
        return None

    db_norm = _normalize_identifier(p.external_reference)
    mer_norm = _normalize_identifier(merchant_external)
    if mer_norm and db_norm and mer_norm != db_norm:
        logger.warning(
            "AzamPay webhook matched via additionalProperties ids but externalreference "
            "differs from our external_reference payment_id=%s partnership_id=%s db_ref=%s webhook_ref=%s",
            p.id,
            p.partnership_id,
            p.external_reference,
            merchant_external,
        )
    return p


def find_payment_for_azam_webhook(payload: dict) -> Payment | None:
    """Full resolution: external/trans ids first, then embedded paymentId from additionalProperties."""
    merchant = _webhook_merchant_external_id(payload)
    gateway = _webhook_gateway_transaction_id(payload)
    p = resolve_payment_for_webhook(merchant, gateway)
    if p:
        return p
    return _resolve_payment_via_embedded_ids(payload, merchant)


@method_decorator(csrf_exempt, name="dispatch")
class AzamPayWebhookAPIView(APIView):
    """AzamPay callback — HTTP 200 on all paths; idempotent status updates."""

    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        close_old_connections()
        arrival = timezone.now()
        pid = os.getpid()
        payload = request.data if isinstance(request.data, dict) else {}

        try:
            from cart_payment.webhook_process import process_cart_azampay_webhook

            cart_response = process_cart_azampay_webhook(payload, relaxed_lookup=False)
            if cart_response is not None:
                return cart_response
        except Exception:
            logger.exception("Cart AzamPay webhook handoff failed pid=%s", pid)

        logger.info(
            "AzamPay webhook pid=%s arrival=%s keys=%s",
            pid,
            arrival.isoformat(),
            list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__,
        )

        try:
            merchant_external = _webhook_merchant_external_id(payload)
            gateway_tx = _webhook_gateway_transaction_id(payload)
            mer_norm = _normalize_identifier(merchant_external)

            logger.info(
                "AzamPay webhook reconcile pid=%s merchant_external=%r norm=%r gateway_tx=%r",
                pid,
                merchant_external,
                mer_norm or "(empty)",
                gateway_tx or "(empty)",
            )

            status_str = (
                str(
                    payload.get("transactionstatus")
                    or payload.get("transactionStatus")
                    or payload.get("status")
                    or payload.get("payment_status")
                    or ""
                ).lower()
            )

            payment = None
            for attempt in range(1, WEBHOOK_PAYMENT_LOOKUP_ATTEMPTS + 1):
                close_old_connections()
                payment = find_payment_for_azam_webhook(payload)
                if payment:
                    if attempt > 1:
                        logger.info(
                            "AzamPay webhook matched payment_id=%s after %s attempts (pid=%s)",
                            payment.id,
                            attempt,
                            pid,
                        )
                    break
                if attempt < WEBHOOK_PAYMENT_LOOKUP_ATTEMPTS:
                    time.sleep(WEBHOOK_PAYMENT_LOOKUP_SLEEP_SEC)

            if not payment:
                logger.warning(
                    "AzamPay webhook: unknown payment pid=%s merchant_external=%r gateway_tx=%r payload_keys=%s",
                    pid,
                    merchant_external or "(empty)",
                    gateway_tx or "(empty)",
                    list(payload.keys()),
                )
                return _webhook_ok({"success": True, "message": "Payment not found"}, status=200)

            terminal = (Payment.STATUS_SUCCESS, Payment.STATUS_FAILED)
            if Payment.objects.filter(pk=payment.pk, status__in=terminal).exists():
                logger.info(
                    "AzamPay webhook idempotent skip (no lock) pid=%s payment_id=%s",
                    pid,
                    payment.id,
                )
                return _webhook_ok({"success": True, "message": "Already processed"}, status=200)

            with transaction.atomic():
                pay = Payment.objects.select_for_update().get(pk=payment.pk)

                if pay.status in (Payment.STATUS_SUCCESS, Payment.STATUS_FAILED):
                    logger.info(
                        "AzamPay webhook idempotent skip pid=%s payment_id=%s status=%s",
                        pid,
                        pay.id,
                        pay.status,
                    )
                    return _webhook_ok({"success": True, "message": "Already processed"}, status=200)

                raw_merge = {**(pay.raw_response or {}), "webhook": payload}
                pay.raw_response = raw_merge
                if gateway_tx:
                    pay.provider_transaction_id = gateway_tx or pay.provider_transaction_id

                util = payload.get("utilityref") or payload.get("utilityRef")
                if util:
                    pay.utility_reference = str(util)[:255]

                try:
                    webhook_amount = Decimal(str(payload.get("amount", "0")))
                    if webhook_amount != pay.amount:
                        logger.error(
                            "Amount mismatch pid=%s payment_id=%s expected=%s got=%s",
                            pid,
                            pay.id,
                            pay.amount,
                            webhook_amount,
                        )
                        pay.status = Payment.STATUS_FAILED
                        pay.save(
                            update_fields=[
                                "status",
                                "raw_response",
                                "provider_transaction_id",
                                "utility_reference",
                            ]
                        )
                        return _webhook_ok(
                            {"success": False, "message": "Amount mismatch — manual review"},
                            status=200,
                        )
                except Exception as e:
                    logger.warning("Could not verify webhook amount pid=%s payment_id=%s err=%s", pid, pay.id, e)

                if status_str in ("success", "successful", "completed", "paid"):
                    pay.status = Payment.STATUS_SUCCESS
                    pay.completed_at = timezone.now()
                    pay.save(
                        update_fields=[
                            "status",
                            "completed_at",
                            "raw_response",
                            "provider_transaction_id",
                            "utility_reference",
                        ]
                    )
                    if pay.partnership_id:
                        pship = (
                            Partnership.objects.select_related("partner_type", "user")
                            .filter(pk=pay.partnership_id)
                            .first()
                        )
                        if pship:
                            pship.paid_at = timezone.now()
                            pship.save(update_fields=["paid_at"])
                            try:
                                from . import email as account_email

                                account_email.send_partner_giving_paid_confirmation(
                                    partnership=pship,
                                    payment=pay,
                                )
                            except Exception:
                                logger.exception(
                                    "Partner giving confirmation email failed pid=%s payment_id=%s",
                                    pid,
                                    pay.id,
                                )
                    logger.info("AzamPay webhook SUCCESS pid=%s payment_id=%s", pid, pay.id)
                    return _webhook_ok({"success": True, "message": "Payment successful"}, status=200)

                if status_str in ("failed", "failure", "error", "rejected"):
                    pay.status = Payment.STATUS_FAILED
                    pay.save(
                        update_fields=[
                            "status",
                            "raw_response",
                            "provider_transaction_id",
                            "utility_reference",
                        ]
                    )
                    logger.info("AzamPay webhook FAILED pid=%s payment_id=%s", pid, pay.id)
                    return _webhook_ok({"success": False, "message": "Payment failed"}, status=200)

                pay.save(
                    update_fields=[
                        "raw_response",
                        "provider_transaction_id",
                        "utility_reference",
                    ]
                )
                return _webhook_ok({"success": True, "message": "Status pending"}, status=200)

        except Exception as e:
            logger.exception("AzamPay webhook error pid=%s err=%s", pid, e)
            return _webhook_ok({"success": False, "message": str(e)}, status=200)


class PartnershipPaymentInitiateAPIView(APIView):
    """Create Payment row (committed), then call AzamPay MNO checkout (partnership gifts in TZS only)."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        partnership_id = data.get("partnership_id")
        phone_raw = data.get("phone_number")
        provider = (data.get("provider") or "Mpesa").strip()

        if not partnership_id or not phone_raw:
            return Response({"detail": "partnership_id and phone_number required"}, status=400)

        if provider not in VALID_MNO_PROVIDERS:
            return Response(
                {"detail": f"Invalid provider. Use one of: {', '.join(sorted(VALID_MNO_PROVIDERS))}"},
                status=400,
            )

        partnership = get_object_or_404(Partnership, pk=int(partnership_id))
        if partnership.currency != Partnership.CURRENCY_TSH:
            return Response({"detail": "Mobile money checkout is only available for TSH amounts"}, status=400)

        account_number = normalize_tz_msisdn(str(phone_raw))
        if len(account_number) < 12:
            return Response({"detail": "Invalid phone number; use 255XXXXXXXXX or local 0XXXXXXXXX"}, status=400)

        external_ref = uuid4().hex

        with transaction.atomic():
            payment = Payment.objects.create(
                partnership=partnership,
                amount=partnership.amount,
                external_reference=external_ref,
                status=Payment.STATUS_PENDING,
                provider=Payment.PROVIDER_AZAMPAY,
            )

        close_old_connections()
        logger.info(
            "Partnership payment created pid=%s payment_id=%s external_reference=%s norm=%s",
            os.getpid(),
            payment.id,
            external_ref,
            payment.external_reference_norm,
        )

        extra = {
            "partnershipId": partnership.id,
            "paymentId": payment.id,
            "giftType": partnership.gift_type,
        }

        try:
            client = AzamPayClient()
        except AzamPayConfigurationError as e:
            payment.status = Payment.STATUS_FAILED
            payment.raw_response = {"configuration_error": str(e)}
            payment.save(update_fields=["status", "raw_response"])
            logger.error("AzamPay configuration: %s", e)
            return Response({"detail": str(e), "payment_id": payment.id}, status=503)

        try:
            resp = client.initiate_mobile_money(
                amount=format_amount_string(partnership.amount),
                account_number=account_number,
                external_id=external_ref,
                provider=provider,
                currency="TZS",
                additional_properties=extra,
            )
            tx_id = resp.get("transactionId") or resp.get("transaction_id") or resp.get("tx_id")
            payment.provider_transaction_id = tx_id
            payment.raw_response = resp
            payment.save(update_fields=["provider_transaction_id", "raw_response"])

            return Response(
                {
                    "success": True,
                    "payment_id": payment.id,
                    "partnership_id": partnership.id,
                    "external_reference": external_ref,
                    "message": resp.get("message") or "Payment request sent. Waiting confirmation.",
                    "provider_response": resp,
                },
                status=200,
            )

        except (ReadTimeout, RequestsConnectionError, ChunkedEncodingError) as e:
            # Same class of ambiguity as ReadTimeout: we may have sent a valid checkout and AzamPay
            # closed the socket without a body (LB/proxy). Webhook is source of truth — never FAILED here.
            logger.warning(
                "AzamPay transport error %s pid=%s payment_id=%s external_reference=%s — left PENDING for webhook: %s",
                type(e).__name__,
                os.getpid(),
                payment.id,
                external_ref,
                e,
            )
            merge = {
                **(payment.raw_response or {}),
                "initiate_transport_error": {"type": type(e).__name__, "detail": str(e)},
            }
            payment.raw_response = merge
            payment.save(update_fields=["raw_response"])
            return Response(
                {
                    "success": True,
                    "status": "PROCESSING",
                    "payment_id": payment.id,
                    "partnership_id": partnership.id,
                    "external_reference": external_ref,
                    "message": "Payment request sent. Waiting confirmation.",
                },
                status=200,
            )

        except RequestException as e:
            logger.exception("AzamPay request error payment_id=%s", payment.id)
            payment.status = Payment.STATUS_FAILED
            payment.raw_response = {"error": str(e)}
            payment.save(update_fields=["status", "raw_response"])
            return Response(
                {
                    "detail": str(e),
                    "payment_id": payment.id,
                    "partnership_id": partnership.id,
                    "external_reference": external_ref,
                },
                status=502,
            )

        except Exception as e:
            logger.exception("AzamPay initiate failure payment_id=%s", payment.id)
            return Response(
                {"detail": str(e), "payment_id": payment.id, "external_reference": external_ref},
                status=500,
            )


class PartnershipPaymentStatusAPIView(APIView):
    """Poll payment outcome after MNO push (webhook remains source of truth)."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, payment_id: int):
        close_old_connections()
        partnership_id = request.query_params.get("partnership_id")
        payment = get_object_or_404(Payment, pk=payment_id, partnership__isnull=False)

        if partnership_id is not None and str(payment.partnership_id) != str(partnership_id):
            return Response({"detail": "partnership_id does not match payment"}, status=400)

        base = {
            "payment_id": payment.id,
            "partnership_id": payment.partnership_id,
            "external_reference": payment.external_reference,
            "transaction_id": payment.provider_transaction_id,
        }

        if payment.status == Payment.STATUS_SUCCESS:
            return Response(
                {
                    **base,
                    "success": True,
                    "status": "SUCCESS",
                    "message": "Payment successful",
                }
            )

        if payment.status == Payment.STATUS_FAILED:
            return Response(
                {
                    **base,
                    "success": False,
                    "status": "FAILED",
                    "message": "Payment failed",
                }
            )

        return Response(
            {
                **base,
                "success": False,
                "status": "PROCESSING",
                "message": "Waiting for payment confirmation",
            }
        )


class PartnershipPaymentReportAPIView(APIView):
    """
    Staff-only reconciliation list for partnership-linked payments (AzamPay MNO, etc.).

    GET /api/admin/reports/partnership-payments/
    Query: status=PENDING|SUCCESS|FAILED (optional), limit (default 100, max 500), offset (default 0).
    """

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        qs = (
            Payment.objects.filter(partnership__isnull=False)
            .select_related("partnership", "partnership__partner_type", "partnership__user")
            .order_by("-created_at")
        )
        status = (request.query_params.get("status") or "").strip().upper()
        if status in (Payment.STATUS_PENDING, Payment.STATUS_SUCCESS, Payment.STATUS_FAILED):
            qs = qs.filter(status=status)

        try:
            limit = int(request.query_params.get("limit", "100"))
        except ValueError:
            limit = 100
        limit = max(1, min(limit, 500))

        try:
            offset = int(request.query_params.get("offset", "0"))
        except ValueError:
            offset = 0
        offset = max(0, offset)

        total = qs.count()
        results = []
        for p in qs[offset : offset + limit]:
            part = p.partnership
            u = part.user
            results.append(
                {
                    "payment_id": p.id,
                    "payment_status": p.status,
                    "provider": p.provider,
                    "amount": str(p.amount),
                    "external_reference": p.external_reference,
                    "external_reference_norm": p.external_reference_norm,
                    "provider_transaction_id": p.provider_transaction_id,
                    "utility_reference": p.utility_reference,
                    "payment_created_at": p.created_at.isoformat() if p.created_at else None,
                    "payment_completed_at": p.completed_at.isoformat() if p.completed_at else None,
                    "partnership_id": part.id,
                    "partnership_amount": str(part.amount),
                    "currency": part.currency,
                    "gift_type": part.gift_type,
                    "frequency": part.frequency,
                    "partner_type_name": part.partner_type.name if part.partner_type_id else None,
                    "partnership_created_at": part.created_at.isoformat() if part.created_at else None,
                    "partnership_paid_at": part.paid_at.isoformat() if part.paid_at else None,
                    "user_id": u.id if u else None,
                    "user_email": getattr(u, "email", None) if u else None,
                }
            )

        return Response(
            {
                "count": total,
                "offset": offset,
                "limit": limit,
                "results": results,
            }
        )
