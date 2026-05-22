from __future__ import annotations

from django.core.cache import cache


def prayer_submit_rate_limit_exceeded(ip: str, *, limit: int = 5, window_sec: int = 3600) -> bool:
    """Return True if IP exceeded submission limit."""
    if not ip:
        ip = "unknown"
    key = f"prayer:submit:ip:{ip}"
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window_sec)
        count = 1
    return count > limit
