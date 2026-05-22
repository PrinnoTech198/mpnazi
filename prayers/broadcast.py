from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def broadcast_new_prayer(prayer) -> None:
    """Push real-time event to connected admin WebSocket clients."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if layer is None:
            return
        async_to_sync(layer.group_send)(
            "admin_prayer_notifications",
            {
                "type": "new_prayer_event",
                "payload": {
                    "type": "new_prayer",
                    "id": prayer.id,
                    "name": prayer.display_name,
                    "country": prayer.country,
                    "country_flag": prayer.country_flag or "",
                    "category": prayer.category,
                    "status": prayer.status,
                    "created_at": prayer.created_at.isoformat(),
                },
            },
        )
    except Exception:
        logger.exception("broadcast_new_prayer failed")
