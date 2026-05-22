"""
Partner giving payments via Pesapal hosted checkout + status polling.
"""
from __future__ import annotations

import logging

from django.db import close_old_connections
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.providers.pesapal import PesapalConfigurationError
from payments.services.payment_service import PaymentService
from payments.services.status_api import build_partner_status_payload

from .models import Partnership, Payment

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class LegacyAzamPayWebhookAPIView(APIView):
    """Deprecated — AzamPay removed; returns 200 so old retries do not loop."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        logger.warning("Legacy AzamPay webhook called — ignored (use Pesapal IPN)")
        return Response(
            {"success": True, "message": "AzamPay deprecated; use Pesapal IPN"},
            status=200,
        )


class PartnershipPaymentInitiateAPIView(APIView):
    """Create Payment + Pesapal checkout URL (all currencies)."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        partnership_id = data.get("partnership_id")
        if not partnership_id:
            return Response({"detail": "partnership_id required"}, status=400)

        partnership = get_object_or_404(Partnership, pk=int(partnership_id))
        billing = {
            "email": data.get("email") or data.get("email_address"),
            "phone_number": data.get("phone_number") or data.get("phone"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
        }

        try:
            payment, body = PaymentService().initiate_partnership_payment(
                partnership, billing_data=billing
            )
        except PesapalConfigurationError as e:
            logger.error("Pesapal configuration: %s", e)
            return Response(
                {"detail": str(e), "payment_id": getattr(locals().get("payment"), "id", None)},
                status=503,
            )
        except Exception as e:
            logger.exception("Partnership payment initiate failed")
            return Response({"detail": str(e)}, status=500)

        code = 200 if body.get("success") else 502
        return Response(body, status=code)


class PartnershipPaymentStatusAPIView(APIView):
    """Poll payment outcome; syncs with Pesapal when still processing."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, payment_id: int):
        close_old_connections()
        partnership_id = request.query_params.get("partnership_id")
        payment = get_object_or_404(Payment, pk=payment_id, partnership__isnull=False)

        if partnership_id is not None and str(payment.partnership_id) != str(partnership_id):
            return Response({"detail": "partnership_id does not match payment"}, status=400)

        return Response(build_partner_status_payload(payment))


class PartnershipPaymentReportAPIView(APIView):
    """Staff-only reconciliation list for partnership-linked payments."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        qs = (
            Payment.objects.filter(partnership__isnull=False)
            .select_related("partnership", "partnership__partner_type", "partnership__user")
            .order_by("-created_at")
        )
        status = (request.query_params.get("status") or "").strip().upper()
        if status in dict(Payment.STATUS_CHOICES):
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
                    "currency": p.currency or part.currency,
                    "external_reference": p.external_reference,
                    "order_tracking_id": p.order_tracking_id,
                    "checkout_url": p.checkout_url,
                    "provider_transaction_id": p.provider_transaction_id,
                    "payment_created_at": p.created_at.isoformat() if p.created_at else None,
                    "payment_completed_at": p.completed_at.isoformat() if p.completed_at else None,
                    "partnership_id": part.id,
                    "partnership_amount": str(part.amount),
                    "partnership_currency": part.currency,
                    "gift_type": part.gift_type,
                    "partnership_paid_at": part.paid_at.isoformat() if part.paid_at else None,
                    "user_email": getattr(u, "email", None) if u else part.guest_email,
                }
            )

        return Response({"count": total, "offset": offset, "limit": limit, "results": results})
