from django.contrib import admin

from .models import CartOrderFulfillment, CartOrderPayment, CartPaymentWebhookLog


@admin.register(CartOrderPayment)
class CartOrderPaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "status", "amount", "provider", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("external_reference", "provider_transaction_id", "order__id")


@admin.register(CartOrderFulfillment)
class CartOrderFulfillmentAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "updated_at")
    list_filter = ("status",)


@admin.register(CartPaymentWebhookLog)
class CartPaymentWebhookLogAdmin(admin.ModelAdmin):
    list_display = ("id", "received_at", "matched_payment_id", "outcome")
