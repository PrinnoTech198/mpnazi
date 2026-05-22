"""
Cross-cutting payment models: provider registry, webhook audit, transaction history.
Domain payments remain on account.Payment and cart_payment.CartOrderPayment.
"""
from __future__ import annotations

from django.db import models


class PaymentProvider(models.Model):
    """Configurable payment gateway (Pesapal, Stripe, …)."""

    CODE_PESAPAL = "PESAPAL"
    CODE_STRIPE = "STRIPE"
    CODE_PAYPAL = "PAYPAL"
    CODE_FLUTTERWAVE = "FLUTTERWAVE"
    CODE_AZAMPAY = "AZAMPAY"  # legacy records only

    CODE_CHOICES = [
        (CODE_PESAPAL, "Pesapal"),
        (CODE_STRIPE, "Stripe"),
        (CODE_PAYPAL, "PayPal"),
        (CODE_FLUTTERWAVE, "Flutterwave"),
        (CODE_AZAMPAY, "AzamPay (legacy)"),
    ]

    code = models.CharField(max_length=32, unique=True, choices=CODE_CHOICES)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    config = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class PaymentWebhookLog(models.Model):
    """One row per matched payment — updated by IPN and status-poll events."""

    SOURCE_PESAPAL_IPN = "pesapal_ipn"
    SOURCE_PESAPAL_STATUS_SYNC = "pesapal_status_sync"
    SOURCE_LEGACY_AZAMPAY = "azampay_legacy"
    SOURCE_CHOICES = [
        (SOURCE_PESAPAL_IPN, "Pesapal IPN"),
        (SOURCE_PESAPAL_STATUS_SYNC, "Pesapal status sync (poll)"),
        (SOURCE_LEGACY_AZAMPAY, "AzamPay legacy"),
    ]

    KIND_PARTNERSHIP = "partnership"
    KIND_CART = "cart"
    KIND_UNKNOWN = "unknown"
    KIND_CHOICES = [
        (KIND_PARTNERSHIP, "Partner giving"),
        (KIND_CART, "Cart checkout"),
        (KIND_UNKNOWN, "Unknown"),
    ]

    source = models.CharField(max_length=40, choices=SOURCE_CHOICES, default=SOURCE_PESAPAL_IPN)
    payment_kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_UNKNOWN)
    received_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField()
    merchant_reference = models.CharField(max_length=255, blank=True, db_index=True)
    order_tracking_id = models.CharField(max_length=255, blank=True, db_index=True)
    matched_payment_id = models.IntegerField(null=True, blank=True)
    matched_cart_payment_id = models.IntegerField(null=True, blank=True)
    outcome = models.CharField(max_length=120, blank=True)
    http_status_returned = models.IntegerField(default=200)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["source", "received_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["payment_kind", "matched_payment_id"],
                condition=models.Q(matched_payment_id__isnull=False),
                name="payments_webhooklog_partner_uniq",
            ),
            models.UniqueConstraint(
                fields=["payment_kind", "matched_cart_payment_id"],
                condition=models.Q(matched_cart_payment_id__isnull=False),
                name="payments_webhooklog_cart_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"WebhookLog {self.pk} {self.source} {self.outcome}"


class TransactionHistory(models.Model):
    """One row per payment — updated in place as status changes (from_status = initial)."""

    KIND_PARTNERSHIP = "partnership"
    KIND_CART = "cart"

    payment_kind = models.CharField(max_length=20)
    payment_id = models.IntegerField(db_index=True)
    provider = models.CharField(max_length=32)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    order_tracking_id = models.CharField(max_length=255, blank=True)
    merchant_reference = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    note = models.CharField(max_length=255, blank=True)
    raw_provider_response = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name_plural = "Transaction histories"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_kind", "payment_id"],
                name="payments_txhistory_kind_payment_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"TxHistory {self.payment_kind}#{self.payment_id} {self.from_status}->{self.to_status}"
