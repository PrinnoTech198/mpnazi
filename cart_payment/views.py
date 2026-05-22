"""
Cart checkout: Pesapal hosted checkout, status polling, fulfillment.
"""
from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import Order
from account.serializers import OrderSerializer, RepresentativeSerializer
from payments.providers.pesapal import PesapalConfigurationError
from payments.services.payment_service import PaymentService
from payments.services.status_api import build_cart_status_payload

from .models import CartOrderFulfillment, CartOrderPayment

logger = logging.getLogger(__name__)


def _order_has_full_pickup_location(order: Order) -> bool:
    fields = (
        "pickup_country",
        "pickup_region",
        "pickup_district",
        "pickup_ward",
        "pickup_village",
        "pickup_landmark",
    )
    return all((getattr(order, f, None) or "").strip() for f in fields)


class CartPaymentInitiateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        if not order_id:
            return Response(
                {"detail": "order_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
                    "before payment."
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

        billing = {
            "email": request.data.get("email") or getattr(request.user, "email", ""),
            "phone_number": request.data.get("phone_number") or request.data.get("phone"),
            "first_name": request.data.get("first_name")
            or getattr(request.user, "first_name", ""),
            "last_name": request.data.get("last_name")
            or getattr(request.user, "last_name", ""),
        }

        try:
            pay, body = PaymentService().initiate_cart_payment(
                order, request.user, billing_data=billing
            )
        except PesapalConfigurationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Cart payment initiate failed order_id=%s", order.id)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        http_status = status.HTTP_200_OK if body.get("success") else status.HTTP_502_BAD_GATEWAY
        return Response(body, status=http_status)


@method_decorator(csrf_exempt, name="dispatch")
class LegacyCartAzamPayWebhookAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        logger.warning("Legacy cart AzamPay webhook — ignored")
        return Response({"success": True, "message": "AzamPay deprecated"}, status=200)


class CartPaymentStatusAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, payment_id: int):
        try:
            pay = CartOrderPayment.objects.select_related("order").get(
                pk=payment_id, order__user=request.user
            )
        except CartOrderPayment.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(build_cart_status_payload(pay))


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
