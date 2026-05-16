"""
Standalone AzamPay MNO client for marketplace cart checkout only.

Does NOT import or subclass partner-giving payment code. Uses
`CART_AZAMPAY_CALLBACK_URL` (see settings) so webhooks route to cart_payment.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from typing import Any, Dict, Optional

import requests
from django.conf import settings
from django.core.cache import cache
from requests.exceptions import ChunkedEncodingError, ConnectionError as RequestsConnectionError

logger = logging.getLogger(__name__)

TOKEN_CACHE_KEY = "cart_azampay_access_token_v1"
TOKEN_TTL_BUFFER_SEC = 120
_CHECKOUT_HTTP_TIMEOUT = (30, 120)
_CHECKOUT_TRANSPORT_RETRIES = 2
_CHECKOUT_RETRY_SLEEP_SEC = 1.5


def normalize_tz_msisdn(phone: str) -> str:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if not digits:
        return ""
    if digits.startswith("255"):
        return digits
    if digits.startswith("0") and len(digits) >= 10:
        return "255" + digits[1:]
    if len(digits) == 9:
        return "255" + digits
    return digits


def format_amount_string(amount: Decimal | str | float) -> str:
    d = Decimal(str(amount))
    if d == d.to_integral():
        return str(int(d))
    return format(d, "f").rstrip("0").rstrip(".")


class CartAzamPayConfigurationError(RuntimeError):
    pass


class CartAzamPayClient:
    def __init__(self) -> None:
        self.auth_base = (getattr(settings, "AZAMPAY_AUTH_BASE_URL", None) or "").rstrip("/")
        self.api_base = (getattr(settings, "AZAMPAY_API_BASE_URL", None) or "").rstrip("/")
        self.app_name = getattr(settings, "AZAMPAY_APP_NAME", None) or ""
        self.client_id = getattr(settings, "AZAMPAY_CLIENT_ID", None) or ""
        self.client_secret = getattr(settings, "AZAMPAY_CLIENT_SECRET", None) or ""
        self.callback_url = (
            getattr(settings, "CART_AZAMPAY_CALLBACK_URL", None) or ""
        ).rstrip("/")
        self.x_api_key = getattr(settings, "AZAMPAY_X_API_KEY", None) or ""

        if not all(
            [
                self.auth_base,
                self.api_base,
                self.app_name,
                self.client_id,
                self.client_secret,
                self.callback_url,
            ]
        ):
            missing = []
            if not self.auth_base:
                missing.append("AZAMPAY_AUTH_BASE_URL")
            if not self.api_base:
                missing.append("AZAMPAY_API_BASE_URL")
            if not self.app_name:
                missing.append("AZAMPAY_APP_NAME")
            if not self.client_id:
                missing.append("AZAMPAY_CLIENT_ID")
            if not self.client_secret:
                missing.append("AZAMPAY_CLIENT_SECRET")
            if not self.callback_url:
                missing.append("CART_AZAMPAY_CALLBACK_URL (or AZAMPAY_CALLBACK_URL to derive from)")
            raise CartAzamPayConfigurationError(
                "Cart AzamPay is not configured. Missing or empty: "
                + ", ".join(missing)
                + ". Set credentials and a public cart webhook URL ending in "
                "/api/cart-payment/webhook/"
            )

    def _fetch_token(self) -> tuple[str, Optional[datetime]]:
        url = f"{self.auth_base}/AppRegistration/GenerateToken"
        body = {
            "appName": self.app_name,
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
        }
        resp = requests.post(url, json=body, timeout=(15, 30))
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(data.get("message") or "AzamPay token request failed")
        inner = data.get("data") or {}
        token = inner.get("accessToken") or inner.get("access_token")
        if not token:
            raise RuntimeError("AzamPay token response missing accessToken")
        expire_raw = inner.get("expire") or inner.get("expires_at")
        expires_at: Optional[datetime] = None
        if expire_raw:
            try:
                expire_clean = str(expire_raw).replace("Z", "+00:00")
                expires_at = datetime.fromisoformat(expire_clean)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=dt_timezone.utc)
            except Exception:
                logger.warning("Could not parse AzamPay token expire: %s", expire_raw)
        return str(token), expires_at

    def _token(self) -> str:
        cached = cache.get(TOKEN_CACHE_KEY)
        if cached:
            return cached
        token, expires_at = self._fetch_token()
        ttl = 600
        if expires_at:
            now = datetime.now(dt_timezone.utc)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=dt_timezone.utc)
            ttl = max(60, int((expires_at - now).total_seconds()) - TOKEN_TTL_BUFFER_SEC)
        cache.set(TOKEN_CACHE_KEY, token, ttl)
        return token

    def _headers(self) -> Dict[str, str]:
        h = {
            "Authorization": f"Bearer {self._token()}",
            "Content-Type": "application/json",
        }
        if self.x_api_key:
            h["X-API-KEY"] = self.x_api_key.strip()
        return h

    def initiate_mobile_money(
        self,
        *,
        amount: str,
        account_number: str,
        external_id: str,
        provider: str,
        currency: str = "TZS",
        additional_properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.api_base}/azampay/mno/checkout"
        callback = self.callback_url.rstrip("/") + "/"
        payload: Dict[str, Any] = {
            "accountNumber": account_number,
            "amount": amount,
            "currency": currency,
            "externalId": external_id,
            "provider": provider,
            "callbackUrl": callback,
            "additionalProperties": additional_properties or {},
        }
        headers = self._headers()
        for attempt in range(1, _CHECKOUT_TRANSPORT_RETRIES + 1):
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=_CHECKOUT_HTTP_TIMEOUT,
                )
                resp.raise_for_status()
                return resp.json()
            except (RequestsConnectionError, ChunkedEncodingError) as e:
                if attempt < _CHECKOUT_TRANSPORT_RETRIES:
                    logger.warning(
                        "Cart AzamPay checkout transport error (attempt %s/%s): %s",
                        attempt,
                        _CHECKOUT_TRANSPORT_RETRIES,
                        e,
                    )
                    time.sleep(_CHECKOUT_RETRY_SLEEP_SEC)
                    continue
                raise
