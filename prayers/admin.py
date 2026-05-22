from django.contrib import admin

from .models import PrayerAdminNotification, PrayerRequest


@admin.register(PrayerRequest)
class PrayerRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "display_name",
        "country",
        "category",
        "status",
        "email",
        "created_at",
    )
    list_filter = ("status", "category", "is_anonymous")
    search_fields = ("name", "email", "country", "request_text")
    readonly_fields = ("created_at", "updated_at", "admin_reply_sent_at")


@admin.register(PrayerAdminNotification)
class PrayerAdminNotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "prayer_request", "message", "is_read", "created_at")
    list_filter = ("is_read",)
