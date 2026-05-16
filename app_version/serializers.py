from rest_framework import serializers

from .models import AppVersionControl


class AppVersionControlSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppVersionControl
        fields = (
            "latest_version",
            "minimum_supported_version",
            "update_type",
            "title",
            "message",
            "playstore_url",
            "payment_force_update",
            "maintenance_mode",
            "maintenance_message",
        )
