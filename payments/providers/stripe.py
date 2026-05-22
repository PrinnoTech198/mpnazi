"""Stripe provider stub — implement when enabling Stripe."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from .base import BasePaymentProvider, CheckoutResult, PaymentStatusResult


class StripeProvider(BasePaymentProvider):
    provider_code = "STRIPE"

    def create_checkout(self, **kwargs) -> CheckoutResult:
        raise NotImplementedError("Stripe integration not configured")

    def get_transaction_status(self, order_tracking_id: str) -> PaymentStatusResult:
        raise NotImplementedError("Stripe integration not configured")

    def register_ipn(self, ipn_url: str, notification_type: str = "POST") -> str:
        raise NotImplementedError("Stripe integration not configured")
