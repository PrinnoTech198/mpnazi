from __future__ import annotations

from django.conf import settings
from django.db import models


class PrayerRequest(models.Model):
    STATUS_NEW = "new"
    STATUS_PRAYING = "praying"
    STATUS_ANSWERED = "answered"
    STATUS_URGENT = "urgent"
    STATUS_CHOICES = [
        (STATUS_NEW, "New"),
        (STATUS_PRAYING, "Praying"),
        (STATUS_ANSWERED, "Answered"),
        (STATUS_URGENT, "Urgent"),
    ]

    CATEGORY_GENERAL = "general"
    CATEGORY_HEALTH = "health"
    CATEGORY_FAMILY = "family"
    CATEGORY_FINANCE = "finance"
    CATEGORY_URGENT = "urgent"
    CATEGORY_CHOICES = [
        (CATEGORY_GENERAL, "General"),
        (CATEGORY_HEALTH, "Health"),
        (CATEGORY_FAMILY, "Family"),
        (CATEGORY_FINANCE, "Finance"),
        (CATEGORY_URGENT, "Urgent"),
    ]

    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    country = models.CharField(max_length=100)
    country_flag = models.CharField(max_length=10, blank=True)
    is_anonymous = models.BooleanField(default=False)

    request_text = models.TextField()
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_GENERAL
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    admin_reply = models.TextField(blank=True)
    admin_reply_sent_at = models.DateTimeField(null=True, blank=True)
    admin_replied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="prayer_replies",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["category", "-created_at"]),
        ]

    def __str__(self) -> str:
        label = "Anonymous" if self.is_anonymous or not self.name else self.name
        return f"{label} ({self.country}) — {self.get_status_display()}"

    @property
    def display_name(self) -> str:
        if self.is_anonymous or not self.name.strip():
            return "Anonymous"
        return self.name.strip()


class PrayerAdminNotification(models.Model):
    prayer_request = models.ForeignKey(
        PrayerRequest,
        on_delete=models.CASCADE,
        related_name="admin_notifications",
    )
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.message[:80]
