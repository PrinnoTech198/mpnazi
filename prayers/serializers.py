from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import PrayerAdminNotification, PrayerRequest

User = get_user_model()


class PrayerRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrayerRequest
        fields = (
            "name",
            "email",
            "country",
            "country_flag",
            "is_anonymous",
            "request_text",
            "category",
        )

    def validate_request_text(self, value):
        text = (value or "").strip()
        if len(text) < 10:
            raise serializers.ValidationError(
                "Please share at least a few words for your prayer request."
            )
        if len(text) > 2000:
            raise serializers.ValidationError("Prayer request must be 2000 characters or less.")
        return text

    def validate_email(self, value):
        email = (value or "").strip()
        return email

    def validate(self, attrs):
        if attrs.get("is_anonymous"):
            attrs["name"] = ""
        return attrs


class PrayerRequestPublicSuccessSerializer(serializers.ModelSerializer):
    """Returned after public submit — no email exposed."""

    class Meta:
        model = PrayerRequest
        fields = ("id", "category", "country", "country_flag", "created_at", "status")


class PrayerRequestAdminSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    admin_replied_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PrayerRequest
        fields = (
            "id",
            "name",
            "display_name",
            "email",
            "country",
            "country_flag",
            "is_anonymous",
            "request_text",
            "category",
            "status",
            "created_at",
            "updated_at",
            "admin_reply",
            "admin_reply_sent_at",
            "admin_replied_by",
            "admin_replied_by_name",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "admin_reply_sent_at",
            "admin_replied_by",
            "admin_replied_by_name",
        )

    def get_admin_replied_by_name(self, obj):
        if obj.admin_replied_by_id:
            u = obj.admin_replied_by
            return u.get_full_name() or u.username
        return None


class PrayerRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrayerRequest
        fields = ("status",)

    def validate_status(self, value):
        valid = {c[0] for c in PrayerRequest.STATUS_CHOICES}
        if value not in valid:
            raise serializers.ValidationError("Invalid status.")
        return value


class PrayerReplySerializer(serializers.Serializer):
    reply_text = serializers.CharField(min_length=10, max_length=5000)

    def validate_reply_text(self, value):
        return value.strip()


class PrayerAdminNotificationSerializer(serializers.ModelSerializer):
    prayer_id = serializers.IntegerField(source="prayer_request_id", read_only=True)
    category = serializers.CharField(source="prayer_request.category", read_only=True)
    country = serializers.CharField(source="prayer_request.country", read_only=True)
    country_flag = serializers.CharField(source="prayer_request.country_flag", read_only=True)

    class Meta:
        model = PrayerAdminNotification
        fields = (
            "id",
            "prayer_id",
            "message",
            "is_read",
            "created_at",
            "category",
            "country",
            "country_flag",
        )


class AdminStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    new_count = serializers.IntegerField()
    praying_count = serializers.IntegerField()
    answered_count = serializers.IntegerField()
    urgent_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    unread_notifications = serializers.IntegerField()
