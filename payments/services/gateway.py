"""Resolve active payment provider from settings."""
from __future__ import annotations

from django.conf import settings

from payments.providers.base import BasePaymentProvider
from payments.providers.pesapal import PesapalProvider


def get_default_provider() -> BasePaymentProvider:
    code = (getattr(settings, "DEFAULT_PAYMENT_PROVIDER", "PESAPAL") or "PESAPAL").upper()
    if code == "PESAPAL":
        return PesapalProvider()
    raise ValueError(f"Unsupported payment provider: {code}")
