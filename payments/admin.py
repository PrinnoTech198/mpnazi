from django.contrib import admin

from .models import PaymentProvider, PaymentWebhookLog, TransactionHistory


@admin.register(PaymentProvider)
class PaymentProviderAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "is_default", "updated_at")
    list_filter = ("is_active",)


@admin.register(PaymentWebhookLog)
class PaymentWebhookLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source",
        "payment_kind",
        "matched_payment_id",
        "matched_cart_payment_id",
        "outcome",
        "merchant_reference",
        "order_tracking_id",
        "updated_at",
        "received_at",
    )
    list_filter = ("source", "payment_kind", "outcome")
    readonly_fields = ("received_at", "updated_at", "payload")


@admin.register(TransactionHistory)
class TransactionHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "payment_kind",
        "payment_id",
        "provider",
        "from_status",
        "to_status",
        "updated_at",
        "created_at",
    )
    list_filter = ("payment_kind", "provider", "to_status")
    readonly_fields = ("created_at", "updated_at")
