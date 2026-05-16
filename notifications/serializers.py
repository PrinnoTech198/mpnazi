from rest_framework import serializers

from .models import DeviceToken


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ("token", "platform")

    def validate_platform(self, value: str) -> str:
        v = (value or "").strip().lower()
        if v not in (DeviceToken.PLATFORM_ANDROID, DeviceToken.PLATFORM_IOS):
            raise serializers.ValidationError('platform must be "android" or "ios".')
        return v

    def validate_token(self, value: str) -> str:
        t = (value or "").strip()
        if len(t) < 10:
            raise serializers.ValidationError("Invalid device token.")
        if len(t) > 511:
            raise serializers.ValidationError("Token too long.")
        return t
