from __future__ import annotations

import logging
from typing import Any

from django.db import close_old_connections

logger = logging.getLogger(__name__)


def deliver_push_task(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, Any] | None,
) -> None:
    """
    Entry point for Django-Q2 workers. Ensures fresh DB connections in the worker process.
    """
    close_old_connections()
    try:
        from .fcm import send_push

        send_push(list(tokens or []), title, body, data or {})
    except Exception:
        logger.exception("deliver_push_task failed")
        raise
    finally:
        close_old_connections()
