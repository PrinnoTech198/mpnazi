from __future__ import annotations

import json
import uuid

from rest_framework import serializers

from account.models import Payment
from cart_payment.models import CartOrderPayment
from payments.models import PaymentProvider, PaymentWebhookLog, TransactionHistory


class AdminPartnerPaymentSerializer(serializers.ModelSerializer):
    partnership_label = serializers.SerializerMethodField(read_only=True)
    order_label = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "order",
            "partnership",
            "order_label",
            "partnership_label",
            "amount",
            "currency",
            "provider",
            "payment_method",
            "status",
            "checkout_url",
            "order_tracking_id",
            "external_reference",
            "provider_transaction_id",
            "utility_reference",
            "metadata",
            "raw_response",
            "completed_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "external_reference_norm"]

    def get_partnership_label(self, obj: Payment) -> str | None:
        if not obj.partnership_id:
            return None
        p = obj.partnership
        return f"#{p.id} {p.partner_type} {p.amount} {p.currency}"

    def get_order_label(self, obj: Payment) -> str | None:
        if not obj.order_id:
            return None
        return f"Order #{obj.order_id}"

    def validate(self, attrs):
        order = attrs.get("order", getattr(self.instance, "order", None))
        partnership = attrs.get(
            "partnership", getattr(self.instance, "partnership", None)
        )
        if self.instance:
            order = order if "order" in attrs else self.instance.order
            partnership = (
                partnership if "partnership" in attrs else self.instance.partnership
            )
        has_order = order is not None
        has_partnership = partnership is not None
        if has_order == has_partnership:
            raise serializers.ValidationError(
                "Set exactly one of order or partnership (not both, not neither)."
            )
        return attrs

    def create(self, validated_data):
        if not validated_data.get("external_reference"):
            validated_data["external_reference"] = uuid.uuid4().hex
        return super().create(validated_data)


class AdminCartPaymentSerializer(serializers.ModelSerializer):
    order_label = serializers.SerializerMethodField(read_only=True)
    user_email = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CartOrderPayment
        fields = [
            "id",
            "order",
            "order_label",
            "user_email",
            "amount",
            "currency",
            "provider",
            "payment_method",
            "status",
            "checkout_url",
            "order_tracking_id",
            "external_reference",
            "provider_transaction_id",
            "utility_reference",
            "metadata",
            "raw_initiate_response",
            "raw_last_webhook",
            "completed_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "external_reference_norm"]

    def get_order_label(self, obj: CartOrderPayment) -> str:
        return f"Order #{obj.order_id}"

    def get_user_email(self, obj: CartOrderPayment) -> str | None:
        user = getattr(obj.order, "user", None)
        return getattr(user, "email", None) if user else None

    def create(self, validated_data):
        if not validated_data.get("external_reference"):
            validated_data["external_reference"] = uuid.uuid4().hex
        return super().create(validated_data)


class AdminPaymentProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentProvider
        fields = [
            "id",
            "code",
            "name",
            "is_active",
            "is_default",
            "config",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AdminPaymentWebhookLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentWebhookLog
        fields = [
            "id",
            "source",
            "payment_kind",
            "received_at",
            "payload",
            "merchant_reference",
            "order_tracking_id",
            "matched_payment_id",
            "matched_cart_payment_id",
            "outcome",
            "http_status_returned",
            "updated_at",
        ]
        read_only_fields = ["id", "received_at", "updated_at"]


class AdminTransactionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionHistory
        fields = [
            "id",
            "payment_kind",
            "payment_id",
            "provider",
            "from_status",
            "to_status",
            "order_tracking_id",
            "merchant_reference",
            "amount",
            "currency",
            "note",
            "raw_provider_response",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


def parse_optional_json(value):
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise serializers.ValidationError("Invalid JSON.") from exc
    return value
