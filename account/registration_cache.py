"""
Redis-backed (Django cache) pending registration payloads.

Users are not created until OTP verification succeeds. Cache key: register_<email>.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any

from django.conf import settings
from django.core.cache import cache

REGISTER_CACHE_PREFIX = "register_"
REGISTER_CACHE_TTL = 600  # 10 minutes
REGISTER_OTP_MAX_ATTEMPTS = 5


def register_cache_key(email: str) -> str:
    return f"{REGISTER_CACHE_PREFIX}{email.strip().lower()}"


def _hash_otp(email: str, code: str) -> str:
    pepper = settings.SECRET_KEY.encode()
    raw = f"register|{email}|{code}".encode()
    return hashlib.sha256(pepper + raw).hexdigest()


def otp_matches(email: str, code: str, otp_hash: str) -> bool:
    expect = _hash_otp(email, code)
    return secrets.compare_digest(expect, otp_hash)


def gen_six_digit_otp() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def get_pending(email: str) -> dict[str, Any] | None:
    data = cache.get(register_cache_key(email))
    return data if isinstance(data, dict) else None


def save_pending(
    *,
    email: str,
    username: str,
    password_hash: str,
    first_name: str,
    last_name: str,
    otp_code: str,
    failed_attempts: int = 0,
) -> None:
    payload = {
        "username": username,
        "email": email,
        "password": password_hash,
        "otp": _hash_otp(email, otp_code),
        "first_name": first_name[:150],
        "last_name": last_name[:150],
        "failed_attempts": failed_attempts,
        "sent_at": time.time(),
    }
    cache.set(register_cache_key(email), payload, timeout=REGISTER_CACHE_TTL)


def delete_pending(email: str) -> None:
    cache.delete(register_cache_key(email))


def increment_failed_attempts(email: str) -> int:
    key = register_cache_key(email)
    data = cache.get(key)
    if not isinstance(data, dict):
        return 0
    data["failed_attempts"] = int(data.get("failed_attempts", 0)) + 1
    cache.set(key, data, timeout=REGISTER_CACHE_TTL)
    return data["failed_attempts"]
