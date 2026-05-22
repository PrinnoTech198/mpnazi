"""
Pesapal API 3.0 JSON provider (sandbox + live).
Docs: https://developer.pesapal.com/how-to-integrate/e-commerce/api-30-json/api-reference
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

from .base import BasePaymentProvider, CheckoutResult, PaymentStatusResult

logger = logging.getLogger(__name__)

TOKEN_CACHE_KEY = "pesapal_access_token_v1"
IPN_ID_CACHE_KEY = "pesapal_ipn_id_v1"


def clear_pesapal_cache() -> None:
    """Call after switching sandbox/live credentials."""
    cache.delete(TOKEN_CACHE_KEY)
    cache.delete(IPN_ID_CACHE_KEY)


class PesapalConfigurationError(Exception):
    """Missing or invalid Pesapal configuration."""


class PesapalProvider(BasePaymentProvider):
    provider_code = "PESAPAL"

    def __init__(self) -> None:
        self.base_url = (getattr(settings, "PESAPAL_BASE_URL", "") or "").rstrip("/")
        self.consumer_key = getattr(settings, "PESAPAL_CONSUMER_KEY", "") or ""
        self.consumer_secret = getattr(settings, "PESAPAL_CONSUMER_SECRET", "") or ""
        self.ipn_url = (getattr(settings, "PESAPAL_IPN_URL", "") or "").strip()
        self.callback_url = (getattr(settings, "PESAPAL_CALLBACK_URL", "") or "").strip()
        self.cancellation_url = (
            getattr(settings, "PESAPAL_CANCELLATION_URL", "") or ""
        ).strip() or None
        self.notification_id = (getattr(settings, "PESAPAL_NOTIFICATION_ID", "") or "").strip()
        self._validate_config()

    def _validate_config(self) -> None:
        missing = []
        if not self.base_url:
            missing.append("PESAPAL_BASE_URL")
        if not self.consumer_key:
            missing.append("PESAPAL_CONSUMER_KEY")
        if not self.consumer_secret:
            missing.append("PESAPAL_CONSUMER_SECRET")
        if not self.ipn_url:
            missing.append("PESAPAL_IPN_URL")
        if not self.callback_url:
            missing.append("PESAPAL_CALLBACK_URL")
        if missing:
            raise PesapalConfigurationError(
                f"Pesapal configuration incomplete. Set: {', '.join(missing)}"
            )

    @staticmethod
    def _auth_error_message(data: dict) -> str:
        err = data.get("error")
        if isinstance(err, dict):
            code = err.get("code") or err.get("error_type") or ""
            msg = (err.get("message") or "").strip()
            if code == "invalid_consumer_key_or_secret_provided":
                return (
                    "Invalid Pesapal consumer key or secret. Merchant keys from your "
                    "Pesapal email must use PESAPAL_BASE_URL=https://pay.pesapal.com/v3 "
                    "(live). Public demo keys from developer.pesapal.com only work on "
                    "https://cybqa.pesapal.com/pesapalv3 (sandbox). Quote key/secret in "
                    ".env if they contain +, /, or =."
                )
            if msg:
                return f"Pesapal authentication failed: {msg}"
            if code:
                return f"Pesapal authentication failed ({code})"
        return f"Pesapal authentication failed: {data}"

    def _token(self) -> str:
        cached = cache.get(TOKEN_CACHE_KEY)
        if cached:
            return cached

        url = f"{self.base_url}/api/Auth/RequestToken"
        resp = requests.post(
            url,
            json={
                "consumer_key": self.consumer_key,
                "consumer_secret": self.consumer_secret,
            },
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30,
        )
        try:
            data = resp.json()
        except ValueError:
            data = {"message": resp.text[:500]}

        token = data.get("token") if isinstance(data, dict) else None
        if not token:
            if resp.status_code >= 400:
                logger.error(
                    "Pesapal RequestToken HTTP %s base_url=%s",
                    resp.status_code,
                    self.base_url,
                )
            raise PesapalConfigurationError(self._auth_error_message(data or {}))

        if resp.status_code >= 400:
            resp.raise_for_status()

        expiry = data.get("expiryDate")
        ttl = 240
        if expiry:
            try:
                exp_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                ttl = max(60, int((exp_dt - datetime.now(timezone.utc)).total_seconds()) - 30)
            except (ValueError, TypeError):
                pass
        cache.set(TOKEN_CACHE_KEY, token, ttl)
        return token

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token()}",
        }

    def _notification_id(self) -> str:
        if self.notification_id:
            return self.notification_id
        cached = cache.get(IPN_ID_CACHE_KEY)
        if cached:
            return cached
        ipn_id = self.register_ipn(self.ipn_url, "POST")
        cache.set(IPN_ID_CACHE_KEY, ipn_id, 86400 * 7)
        return ipn_id

    def register_ipn(self, ipn_url: str, notification_type: str = "POST") -> str:
        url = f"{self.base_url}/api/URLSetup/RegisterIPN"
        resp = requests.post(
            url,
            json={"url": ipn_url, "ipn_notification_type": notification_type},
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        ipn_id = data.get("ipn_id")
        if not ipn_id:
            raise PesapalConfigurationError(f"Pesapal IPN registration failed: {data}")
        logger.info("Pesapal IPN registered url=%s ipn_id=%s", ipn_url, ipn_id)
        return str(ipn_id)

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
        ref = merchant_reference[:50]
        payload: dict[str, Any] = {
            "id": ref,
            "currency": currency,
            "amount": float(amount),
            "description": (description or "Payment")[:100],
            "callback_url": callback_url or self.callback_url,
            "notification_id": self._notification_id(),
            "billing_address": billing_address or {},
        }
        cancel = cancellation_url or self.cancellation_url
        if cancel:
            payload["cancellation_url"] = cancel

        url = f"{self.base_url}/api/Transactions/SubmitOrderRequest"
        try:
            resp = requests.post(
                url, json=payload, headers=self._headers(), timeout=60
            )
            data = resp.json() if resp.content else {}
        except requests.RequestException as e:
            logger.exception("Pesapal SubmitOrderRequest failed ref=%s", ref)
            return CheckoutResult(
                success=False,
                merchant_reference=ref,
                error_message=str(e),
            )

        if resp.status_code >= 400 or data.get("error"):
            err = data.get("error") or data
            msg = err.get("message") if isinstance(err, dict) else str(err)
            return CheckoutResult(
                success=False,
                merchant_reference=ref,
                raw_response=data,
                error_message=msg or "Pesapal order creation failed",
            )

        redirect = data.get("redirect_url")
        tracking = data.get("order_tracking_id")
        if not redirect or not tracking:
            return CheckoutResult(
                success=False,
                merchant_reference=ref,
                raw_response=data,
                error_message="Pesapal response missing redirect_url or order_tracking_id",
            )

        return CheckoutResult(
            success=True,
            merchant_reference=ref,
            order_tracking_id=str(tracking),
            redirect_url=str(redirect),
            raw_response=data,
        )

    def get_transaction_status(self, order_tracking_id: str) -> PaymentStatusResult:
        url = f"{self.base_url}/api/Transactions/GetTransactionStatus"
        resp = requests.get(
            url,
            params={"orderTrackingId": order_tracking_id},
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        raw_code = data.get("status_code")
        try:
            status_code = int(raw_code) if raw_code is not None and raw_code != "" else None
        except (TypeError, ValueError):
            status_code = None

        desc = (data.get("payment_status_description") or "").strip().upper()
        internal = "pending"
        if status_code == 1 or desc in ("COMPLETED", "COMPLETE"):
            internal = "completed"
        elif status_code == 2 or desc == "FAILED":
            internal = "failed"
        elif status_code == 3 or desc == "REVERSED":
            internal = "refunded"
        elif status_code == 0 or desc == "INVALID":
            # Inconclusive — do not treat as failed while customer may still be paying
            internal = "pending"

        amt = data.get("amount")
        return PaymentStatusResult(
            status=internal,
            amount=Decimal(str(amt)) if amt is not None else None,
            currency=data.get("currency"),
            payment_method=data.get("payment_method"),
            confirmation_code=data.get("confirmation_code"),
            provider_status_code=status_code,
            provider_status_description=data.get("payment_status_description"),
            raw_response=data,
        )
