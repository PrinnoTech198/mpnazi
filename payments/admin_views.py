from __future__ import annotations

from rest_framework import filters as drf_filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from account.models import Payment
from account.views import StandardResultsSetPagination
from cart_payment.models import CartOrderPayment
from payments.admin_serializers import (
    AdminCartPaymentSerializer,
    AdminPartnerPaymentSerializer,
    AdminPaymentProviderSerializer,
    AdminPaymentWebhookLogSerializer,
    AdminTransactionHistorySerializer,
)
from payments.models import PaymentProvider, PaymentWebhookLog, TransactionHistory
from payments.services.payment_service import PaymentService


class IsStaffAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)


class AdminPartnerPaymentViewSet(viewsets.ModelViewSet):
    """CRUD for partner-giving ``account.Payment`` rows."""

    queryset = Payment.objects.select_related(
        "partnership", "partnership__partner_type", "order"
    ).order_by("-created_at")
    serializer_class = AdminPartnerPaymentSerializer
    permission_classes = [IsStaffAdmin]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        drf_filters.SearchFilter,
        drf_filters.OrderingFilter,
    ]
    search_fields = [
        "external_reference",
        "order_tracking_id",
        "provider_transaction_id",
        "utility_reference",
        "status",
    ]
    ordering_fields = ["created_at", "amount", "status", "id"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset().filter(partnership__isnull=False)
        st = (self.request.query_params.get("status") or "").strip().upper()
        if st:
            qs = qs.filter(status=st)
        return qs

    @action(detail=True, methods=["post"])
    def resync(self, request, pk=None):
        pay = self.get_object()
        if not pay.partnership_id:
            return Response(
                {"detail": "Not a partnership payment."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        before = pay.status
        pay = PaymentService().verify_and_sync_partner_payment(pay)
        ser = self.get_serializer(pay)
        return Response(
            {
                "before_status": before,
                "payment": ser.data,
            }
        )


class AdminCartPaymentViewSet(viewsets.ModelViewSet):
    """CRUD for marketplace ``CartOrderPayment`` rows."""

    queryset = CartOrderPayment.objects.select_related("order", "order__user").order_by(
        "-created_at"
    )
    serializer_class = AdminCartPaymentSerializer
    permission_classes = [IsStaffAdmin]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        drf_filters.SearchFilter,
        drf_filters.OrderingFilter,
    ]
    search_fields = [
        "external_reference",
        "order_tracking_id",
        "provider_transaction_id",
        "utility_reference",
        "status",
    ]
    ordering_fields = ["created_at", "amount", "status", "id"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        st = (self.request.query_params.get("status") or "").strip().upper()
        if st:
            qs = qs.filter(status=st)
        order_id = self.request.query_params.get("order")
        if order_id:
            try:
                qs = qs.filter(order_id=int(order_id))
            except (TypeError, ValueError):
                pass
        return qs

    @action(detail=True, methods=["post"])
    def resync(self, request, pk=None):
        pay = self.get_object()
        before = pay.status
        pay = PaymentService().verify_and_sync_cart_payment(pay)
        ser = self.get_serializer(pay)
        return Response(
            {
                "before_status": before,
                "payment": ser.data,
            }
        )


class AdminPaymentProviderViewSet(viewsets.ModelViewSet):
    queryset = PaymentProvider.objects.all().order_by("code")
    serializer_class = AdminPaymentProviderSerializer
    permission_classes = [IsStaffAdmin]
    pagination_class = StandardResultsSetPagination
    filter_backends = [drf_filters.SearchFilter, drf_filters.OrderingFilter]
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name", "updated_at"]
    ordering = ["code"]


class AdminPaymentWebhookLogViewSet(viewsets.ModelViewSet):
    queryset = PaymentWebhookLog.objects.all().order_by("-updated_at")
    serializer_class = AdminPaymentWebhookLogSerializer
    permission_classes = [IsStaffAdmin]
    pagination_class = StandardResultsSetPagination
    filter_backends = [drf_filters.SearchFilter, drf_filters.OrderingFilter]
    search_fields = [
        "merchant_reference",
        "order_tracking_id",
        "outcome",
        "payment_kind",
        "source",
    ]
    ordering_fields = ["updated_at", "received_at", "id"]
    ordering = ["-updated_at"]


class AdminTransactionHistoryViewSet(viewsets.ModelViewSet):
    queryset = TransactionHistory.objects.all().order_by("-updated_at")
    serializer_class = AdminTransactionHistorySerializer
    permission_classes = [IsStaffAdmin]
    pagination_class = StandardResultsSetPagination
    filter_backends = [drf_filters.SearchFilter, drf_filters.OrderingFilter]
    search_fields = [
        "merchant_reference",
        "order_tracking_id",
        "payment_kind",
        "provider",
        "note",
    ]
    ordering_fields = ["updated_at", "created_at", "payment_id"]
    ordering = ["-updated_at"]
