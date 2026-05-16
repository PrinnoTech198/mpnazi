from django.contrib import admin

from .models import DeviceToken, NotificationLog


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "platform", "user", "updated_at", "token_tail")
    list_filter = ("platform",)
    search_fields = ("token",)

    @staticmethod
    def token_tail(obj: DeviceToken) -> str:
        t = obj.token or ""
        return f"…{t[-12:]}" if len(t) > 12 else t


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "title", "sent_at", "token_tail")
    list_filter = ("status",)
    search_fields = ("token", "title", "fcm_message_id")

    @staticmethod
    def token_tail(obj: NotificationLog) -> str:
        t = obj.token or ""
        return f"…{t[-12:]}" if len(t) > 12 else t
