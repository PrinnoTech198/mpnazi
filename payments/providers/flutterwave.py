"""Flutterwave provider stub — implement when enabling Flutterwave."""
from __future__ import annotations

from .base import BasePaymentProvider, CheckoutResult, PaymentStatusResult


class FlutterwaveProvider(BasePaymentProvider):
    provider_code = "FLUTTERWAVE"

    def create_checkout(self, **kwargs) -> CheckoutResult:
        raise NotImplementedError("Flutterwave integration not configured")

    def get_transaction_status(self, order_tracking_id: str) -> PaymentStatusResult:
        raise NotImplementedError("Flutterwave integration not configured")

    def register_ipn(self, ipn_url: str, notification_type: str = "POST") -> str:
        raise NotImplementedError("Flutterwave integration not configured")
