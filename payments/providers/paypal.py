"""PayPal provider stub — implement when enabling PayPal."""
from __future__ import annotations

from .base import BasePaymentProvider, CheckoutResult, PaymentStatusResult


class PayPalProvider(BasePaymentProvider):
    provider_code = "PAYPAL"

    def create_checkout(self, **kwargs) -> CheckoutResult:
        raise NotImplementedError("PayPal integration not configured")

    def get_transaction_status(self, order_tracking_id: str) -> PaymentStatusResult:
        raise NotImplementedError("PayPal integration not configured")

    def register_ipn(self, ipn_url: str, notification_type: str = "POST") -> str:
        raise NotImplementedError("PayPal integration not configured")
