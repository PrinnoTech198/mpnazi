"""
Abstract payment provider interface — plug in Stripe, PayPal, Flutterwave, etc.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class CheckoutResult:
    """Result of initiating a hosted checkout session."""

    success: bool
    merchant_reference: str
    order_tracking_id: str | None = None
    redirect_url: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


@dataclass
class PaymentStatusResult:
    """Verified payment status from the provider API."""

    status: str  # pending | processing | completed | failed | cancelled | refunded
    amount: Decimal | None = None
    currency: str | None = None
    payment_method: str | None = None
    confirmation_code: str | None = None
    provider_status_code: int | None = None
    provider_status_description: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


class BasePaymentProvider(ABC):
    """Contract for all payment gateway implementations."""

    provider_code: str = ""

    @abstractmethod
    def create_checkout(
        self,
        *,
        merchant_reference: str,
        amount: Decimal,
        currency: str,
        description: str,
        callback_url: str,
        cancellation_url: str | None = None,
        billing_address: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CheckoutResult:
        """Create a hosted checkout and return redirect URL."""

    @abstractmethod
    def get_transaction_status(self, order_tracking_id: str) -> PaymentStatusResult:
        """Fetch authoritative payment status from the provider."""

    @abstractmethod
    def register_ipn(self, ipn_url: str, notification_type: str = "POST") -> str:
        """Register IPN URL; return notification_id (ipn_id)."""
