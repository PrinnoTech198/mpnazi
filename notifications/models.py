from __future__ import annotations

from django.conf import settings
from django.db import models


class DeviceToken(models.Model):
    PLATFORM_ANDROID = "android"
    PLATFORM_IOS = "ios"
    PLATFORM_CHOICES = [
        (PLATFORM_ANDROID, "Android"),
        (PLATFORM_IOS, "iOS"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="device_tokens",
    )
    token = models.CharField(max_length=512, unique=True, db_index=True)
    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.platform} token …{self.token[-8:]}"


class NotificationLog(models.Model):
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    ]

    token = models.CharField(max_length=512, db_index=True)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, db_index=True)
    error_message = models.TextField(blank=True)
    fcm_message_id = models.CharField(max_length=512, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self) -> str:
        return f"{self.status} {self.title}"
