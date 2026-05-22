"""
Marketplace order payments and fulfillment — separate tables from partner `Payment`.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models


class CartOrderPayment(models.Model):
    """Hosted checkout payment row for a marketplace Order (Pesapal, etc.)."""

    PROVIDER_AZAMPAY = "AZAMPAY"
    PROVIDER_PESAPAL = "PESAPAL"
    PROVIDER_CHOICES = [
        (PROVIDER_AZAMPAY, "AzamPay (legacy)"),
        (PROVIDER_PESAPAL, "Pesapal"),
    ]

    STATUS_PENDING = "PENDING"
    STATUS_PROCESSING = "PROCESSING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_REFUNDED = "REFUNDED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_REFUNDED, "Refunded"),
    ]

    order = models.ForeignKey(
        "account.Order",
        on_delete=models.CASCADE,
        related_name="cart_payments",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="TZS")
    provider = models.CharField(
        max_length=32, choices=PROVIDER_CHOICES, default=PROVIDER_PESAPAL
    )
    payment_method = models.CharField(max_length=64, blank=True, default="")
    checkout_url = models.URLField(max_length=500, blank=True, null=True)
    order_tracking_id = models.CharField(
        max_length=255, blank=True, null=True, db_index=True
    )
    metadata = models.JSONField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    external_reference = models.CharField(max_length=255, unique=True, db_index=True)
    external_reference_norm = models.CharField(
        max_length=255, null=True, blank=True, db_index=True
    )
    provider_transaction_id = models.CharField(
        max_length=255, blank=True, null=True, db_index=True
    )
    utility_reference = models.CharField(max_length=255, blank=True, null=True)
    raw_initiate_response = models.JSONField(blank=True, null=True)
    raw_last_webhook = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order", "status"]),
        ]

    def save(self, *args, **kwargs):
        ref = (self.external_reference or "").strip()
        if ref:
            self.external_reference_norm = "".join(
                c for c in ref.lower() if c.isalnum()
            )
        else:
            self.external_reference_norm = None
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"CartPayment {self.pk} order={self.order_id} {self.status}"


class CartOrderFulfillment(models.Model):
    """Pickup / delivery lifecycle for a paid marketplace order (separate from partner flows)."""

    ST_PENDING = "PENDING"
    ST_PROCESSING = "PROCESSING"
    ST_SENT_TO_REP = "SENT_TO_REPRESENTATIVE"
    ST_AT_REP = "ARRIVED_AT_REPRESENTATIVE"
    ST_READY = "READY_FOR_PICKUP"
    ST_COMPLETED = "COMPLETED"
    STATUS_CHOICES = [
        (ST_PENDING, "Pending"),
        (ST_PROCESSING, "Processing"),
        (ST_SENT_TO_REP, "Sent to representative"),
        (ST_AT_REP, "Arrived at representative"),
        (ST_READY, "Ready for pickup"),
        (ST_COMPLETED, "Completed"),
    ]

    order = models.OneToOneField(
        "account.Order",
        on_delete=models.CASCADE,
        related_name="cart_fulfillment",
    )
    status = models.CharField(
        max_length=40,
        choices=STATUS_CHOICES,
        default=ST_PENDING,
        db_index=True,
    )
    internal_note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cart order fulfillment"
        verbose_name_plural = "Cart order fulfillments"

    def __str__(self) -> str:
        return f"Fulfillment order={self.order_id} {self.status}"


class CartPaymentWebhookLog(models.Model):
    """Audit trail for cart-payment webhooks (troubleshooting)."""

    received_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField()
    matched_payment_id = models.IntegerField(null=True, blank=True)
    outcome = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-received_at"]
