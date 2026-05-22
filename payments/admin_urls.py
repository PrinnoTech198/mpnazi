from django.urls import include, path
from rest_framework.routers import DefaultRouter

from payments.admin_views import (
    AdminCartPaymentViewSet,
    AdminPartnerPaymentViewSet,
    AdminPaymentProviderViewSet,
    AdminPaymentWebhookLogViewSet,
    AdminTransactionHistoryViewSet,
)

router = DefaultRouter()
router.register(
    r"partner-payments",
    AdminPartnerPaymentViewSet,
    basename="admin-partner-payment",
)
router.register(
    r"cart-payments",
    AdminCartPaymentViewSet,
    basename="admin-cart-payment",
)
router.register(
    r"payment-providers",
    AdminPaymentProviderViewSet,
    basename="admin-payment-provider",
)
router.register(
    r"payment-webhook-logs",
    AdminPaymentWebhookLogViewSet,
    basename="admin-payment-webhook-log",
)
router.register(
    r"transaction-history",
    AdminTransactionHistoryViewSet,
    basename="admin-transaction-history",
)

urlpatterns = [
    path("", include(router.urls)),
]
