"""Merchant reference helpers for Pesapal (max 50 chars, alphanumeric + - _ . :)."""
from __future__ import annotations

import re
from uuid import uuid4

_VALID_REF = re.compile(r"^[A-Za-z0-9\-_.:]+$")


def new_merchant_reference(prefix: str = "") -> str:
    """Generate a Pesapal-safe unique merchant reference."""
    core = uuid4().hex
    if prefix:
        ref = f"{prefix}{core}"[:50]
    else:
        ref = core[:50]
    return ref


def normalize_merchant_reference(value: str | None) -> str:
    if not value:
        return ""
    return "".join(c for c in str(value).strip().lower() if c.isalnum())


def partnership_currency_iso(currency: str) -> str:
    """Map app currency codes to ISO codes for Pesapal."""
    c = (currency or "").upper()
    if c == "TSH":
        return "TZS"
    return c
