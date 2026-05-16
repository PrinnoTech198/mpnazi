"""
Cart checkout: AzamPay initiate, webhook, status, orders list, fulfillment updates.

Does not import `account.payment_views` or `account.models.Payment` (partnership).
"""
from __future__ import annotations

import logging
import time
from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from requests.exceptions import ReadTimeout, RequestException
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import Order
from account.serializers import OrderSerializer, RepresentativeSerializer

from .gateway_azampay import (
    CartAzamPayClient,
    CartAzamPayConfigurationError,
    format_amount_string,
    normalize_tz_msisdn,
)
from .models import CartOrderFulfillment, CartOrderPayment
from .webhook_process import process_cart_azampay_webhook

logger = logging.getLogger(__name__)

VALID_MNO = frozenset({"Mpesa", "Tigo", "Airtel", "Halopesa", "Azampesa"})


def _order_has_full_pickup_location(order: Order) -> bool:
    """True when customer entered the full address (no representative on order)."""
    fields = (
        "pickup_country",
        "pickup_region",
        "pickup_district",
        "pickup_ward",
        "pickup_village",
        "pickup_landmark",
    )
    return all((getattr(order, f, None) or "").strip() for f in fields)


def _webhook_ok(body: dict, code: int = 200):
    return Response(body, status=code)


class CartPaymentInitiateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        phone = request.data.get("phone_number") or request.data.get("phone")
        provider = (request.data.get("provider") or "").strip()
        if not order_id or not phone or not provider:
            return Response(
                {"detail": "order_id, phone_number, and provider are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if provider not in VALID_MNO:
            return Response({"detail": "Invalid MNO provider."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.select_related("representative").get(
                pk=int(order_id), user=request.user
            )
        except (Order.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        if not order.representative_id and not _order_has_full_pickup_location(order):
            return Response(
                {
                    "detail": "Select a representative or provide a full pickup address "
                    "(country, region, district, ward, village, landmark) before payment."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order.status not in (Order.STATUS_PENDING, Order.STATUS_PROCESSING):
            return Response(
                {"detail": "This order is not awaiting payment."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if CartOrderPayment.objects.filter(
            order=order, status=CartOrderPayment.STATUS_SUCCESS
        ).exists():
            return Response(
                {"detail": "Order is already paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        external_id = uuid4().hex
        amount_str = format_amount_string(order.total_amount)
        msisdn = normalize_tz_msisdn(phone)
        if len(msisdn) < 12:
            return Response(
                {"detail": "Invalid phone number. Use Tanzania format (e.g. 07… or 255…)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pay = CartOrderPayment.objects.create(
            order=order,
            amount=order.total_amount,
            currency="TZS",
            status=CartOrderPayment.STATUS_PENDING,
            external_reference=external_id,
        )

        addl = {
            "cartPaymentId": pay.id,
            "orderId": order.id,
            "kind": "marketplace_cart",
        }

        try:
            client = CartAzamPayClient()
        except CartAzamPayConfigurationError as e:
            pay.delete()
            return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            resp = client.initiate_mobile_money(
                amount=amount_str,
                account_number=msisdn,
                external_id=external_id,
                provider=provider,
                additional_properties=addl,
            )
        except ReadTimeout:
            logger.info(
                "Cart AzamPay initiate ReadTimeout (treated as processing) order_id=%s payment_id=%s",
                order.id,
                pay.id,
            )
            pay.raw_initiate_response = {"timeout": True}
            pay.save(update_fields=["raw_initiate_response"])
            order.status = Order.STATUS_PROCESSING
            order.payment_method = Order.PAYMENT_MOBILE
            order.external_reference = external_id
            order.save(update_fields=["status", "payment_method", "external_reference"])
            msg = (
                "Payment request may have reached your operator. "
                "Confirm on your phone if prompted; this page will update when we receive confirmation."
            )
            return Response(
                {
                    "detail": msg,
                    "message": msg,
                    "payment_id": pay.id,
                    "order_id": order.id,
                    "external_reference": external_id,
                    "processing": True,
                    "status": "PROCESSING",
                    "success": False,
                },
                status=status.HTTP_200_OK,
            )
        except RequestException as e:
            logger.exception("Cart AzamPay initiate failed payment_id=%s", pay.id)
            pay.raw_initiate_response = {"error": str(e)}
            pay.save(update_fields=["raw_initiate_response"])
            return Response(
                {
                    "detail": "Payment gateway error.",
                    "message": "Payment gateway error.",
                    "payment_id": pay.id,
                    "success": False,
                    "status": "FAILED",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        pay.raw_initiate_response = resp
        tid = (resp or {}).get("transactionId") or (resp or {}).get("transaction_id")
        if tid:
            pay.provider_transaction_id = str(tid)[:255]
        pay.save(update_fields=["raw_initiate_response", "provider_transaction_id"])

        order.status = Order.STATUS_PROCESSING
        order.payment_method = Order.PAYMENT_MOBILE
        order.external_reference = external_id
        order.save(update_fields=["status", "payment_method", "external_reference"])

        gateway_msg = ""
        if isinstance(resp, dict):
            gateway_msg = (resp.get("message") or resp.get("Message") or "") or ""
        if not isinstance(gateway_msg, str):
            gateway_msg = str(gateway_msg)
        user_msg = gateway_msg.strip() or "Payment request received. Confirm on your phone if prompted."

        return Response(
            {
                "payment_id": pay.id,
                "order_id": order.id,
                "external_reference": external_id,
                "gateway": resp,
                "message": user_msg,
                "detail": user_msg,
                "status": "PROCESSING",
                "success": False,
                "processing": True,
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class CartAzamPayWebhookAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            payload = request.data if isinstance(request.data, dict) else {}
        except Exception:
            payload = {}

        resp = process_cart_azampay_webhook(payload)
        if resp is None:
            return _webhook_ok({"success": True, "message": "ignored"}, 200)
        return resp


class CartPaymentStatusAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, payment_id: int):
        try:
            pay = CartOrderPayment.objects.select_related("order").get(
                pk=payment_id, order__user=request.user
            )
        except CartOrderPayment.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        order = pay.order
        ff = CartOrderFulfillment.objects.filter(order=order).first()
        fulfillment = ff.status if ff else order.fulfillment_status

        base = {
            "payment_id": pay.id,
            "order_id": pay.order_id,
            "external_reference": pay.external_reference,
            "transaction_id": pay.provider_transaction_id or "",
            "order_status": order.status,
            "fulfillment_status": fulfillment,
        }

        if pay.status == CartOrderPayment.STATUS_SUCCESS:
            return Response(
                {
                    **base,
                    "success": True,
                    "status": "SUCCESS",
                    "message": "Payment successful",
                }
            )

        if pay.status == CartOrderPayment.STATUS_FAILED:
            return Response(
                {
                    **base,
                    "success": False,
                    "status": "FAILED",
                    "message": "Payment failed",
                }
            )

        raw = pay.raw_initiate_response if isinstance(pay.raw_initiate_response, dict) else {}
        msg = "Waiting for payment confirmation. Approve on your phone if prompted."
        if raw.get("timeout"):
            msg = (
                "Your payment may still be processing. "
                "The link to AzamPay took longer than usual—check your phone for the mobile money prompt. "
                "This screen updates automatically when payment completes."
            )
        else:
            gw = raw.get("message") or raw.get("Message")
            if isinstance(gw, str) and gw.strip():
                msg = gw.strip()

        return Response(
            {
                **base,
                "success": False,
                "status": "PROCESSING",
                "message": msg,
            }
        )


class CartMyOrdersAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = (
            Order.objects.filter(user=request.user)
            .select_related("representative")
            .prefetch_related("items__service")
            .order_by("-created_at")[:50]
        )
        out = []
        for o in qs:
            ser = OrderSerializer(o, context={"request": request})
            row = dict(ser.data)
            ff = CartOrderFulfillment.objects.filter(order=o).first()
            row["cart_fulfillment_status"] = ff.status if ff else o.fulfillment_status
            out.append(row)
        return Response(out)


class CartFulfillmentUpdateAPIView(APIView):
    """Staff / admin: advance marketplace fulfillment status."""

    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, order_id: int):
        st = request.data.get("status")
        note = request.data.get("internal_note", "")
        allowed = {c[0] for c in CartOrderFulfillment.STATUS_CHOICES}
        if st not in allowed:
            return Response({"detail": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        ff, _ = CartOrderFulfillment.objects.get_or_create(
            order=order,
            defaults={"status": CartOrderFulfillment.ST_PENDING},
        )
        ff.status = st
        if note:
            ff.internal_note = note
        ff.save(update_fields=["status", "internal_note", "updated_at"])
        order.fulfillment_status = ff.status
        order.save(update_fields=["fulfillment_status"])
        return Response(
            {
                "order_id": order.id,
                "fulfillment_status": ff.status,
                "representative": RepresentativeSerializer(
                    order.representative, context={"request": request}
                ).data
                if order.representative
                else None,
            }
        )
