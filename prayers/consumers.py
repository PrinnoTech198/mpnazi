from __future__ import annotations

import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)
User = get_user_model()
ADMIN_GROUP = "admin_prayer_notifications"


class AdminNotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = await self._user_from_token()
        if user is None or not user.is_staff:
            await self.close(code=4401)
            return
        self.scope["user"] = user
        await self.channel_layer.group_add(ADMIN_GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "channel_layer") and self.channel_layer:
            await self.channel_layer.group_discard(ADMIN_GROUP, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Clients may send ping; respond with pong.
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def new_prayer_event(self, event):
        payload = event.get("payload") or {}
        await self.send_json(payload)

    @database_sync_to_async
    def _user_from_token(self):
        qs = self.scope.get("query_string", b"").decode()
        token = None
        for part in qs.split("&"):
            if part.startswith("token="):
                token = part.split("=", 1)[1]
                break
        if not token:
            return None
        try:
            access = AccessToken(token)
            uid = access.get("user_id")
            return User.objects.filter(pk=uid, is_active=True).first()
        except (InvalidToken, TokenError, Exception) as e:
            logger.debug("WS auth failed: %s", e)
            return None
