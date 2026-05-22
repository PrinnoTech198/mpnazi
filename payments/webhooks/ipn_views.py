"""
Pesapal IPN endpoint — verify status server-side; never trust client redirect alone.
"""
from __future__ import annotations

import logging

from django.db import close_old_connections
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.services.payment_service import PaymentService

logger = logging.getLogger(__name__)


def _extract_ipn_payload(request) -> dict:
    if request.method == "GET":
        return dict(request.query_params.items())
    try:
        data = request.data
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


@method_decorator(csrf_exempt, name="dispatch")
class PesapalIPNAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        return self._handle(request)

    def post(self, request):
        return self._handle(request)

    def _handle(self, request):
        close_old_connections()
        payload = _extract_ipn_payload(request)
        logger.info("Pesapal IPN received method=%s keys=%s", request.method, list(payload.keys()))
        try:
            body = PaymentService().process_ipn_payload(payload)
            http_status = body.get("status", 200)
            if http_status not in (200, 500):
                http_status = 200
            return Response(body, status=200)
        except Exception as e:
            logger.exception("Pesapal IPN handler error: %s", e)
            return Response(
                {
                    "orderNotificationType": payload.get("OrderNotificationType", "IPNCHANGE"),
                    "orderTrackingId": payload.get("OrderTrackingId", ""),
                    "orderMerchantReference": payload.get("OrderMerchantReference", ""),
                    "status": 500,
                },
                status=200,
            )
