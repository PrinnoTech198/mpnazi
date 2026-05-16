from django.urls import path

from .views import (
    CartAzamPayWebhookAPIView,
    CartFulfillmentUpdateAPIView,
    CartMyOrdersAPIView,
    CartPaymentInitiateAPIView,
    CartPaymentStatusAPIView,
)

urlpatterns = [
    path("initiate/", CartPaymentInitiateAPIView.as_view(), name="cart-payment-initiate"),
    path("webhook/", CartAzamPayWebhookAPIView.as_view(), name="cart-payment-webhook"),
    path("webhook", CartAzamPayWebhookAPIView.as_view(), name="cart-payment-webhook-noslash"),
    path(
        "status/<int:payment_id>/",
        CartPaymentStatusAPIView.as_view(),
        name="cart-payment-status",
    ),
    path("my-orders/", CartMyOrdersAPIView.as_view(), name="cart-my-orders"),
    path(
        "fulfillment/<int:order_id>/",
        CartFulfillmentUpdateAPIView.as_view(),
        name="cart-fulfillment-update",
    ),
]
