from django.contrib import admin
from django.utils.html import format_html

from .models import AppVersionControl


@admin.register(AppVersionControl)
class AppVersionControlAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "latest_version",
        "minimum_supported_version",
        "update_type",
        "is_active",
        "maintenance_mode",
        "payment_force_update",
        "created_at",
    )
    list_filter = ("update_type", "is_active", "maintenance_mode", "payment_force_update")
    search_fields = ("title", "message", "latest_version")
    readonly_fields = ("created_at",)
    fieldsets = (
        (
            "Versions",
            {
                "fields": (
                    "latest_version",
                    "minimum_supported_version",
                    "update_type",
                ),
            },
        ),
        (
            "User messaging",
            {
                "fields": ("title", "message", "playstore_url"),
            },
        ),
        (
            "Policies",
            {
                "fields": (
                    "payment_force_update",
                    "maintenance_mode",
                    "maintenance_message",
                    "is_active",
                ),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_at",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if obj.is_active:
            AppVersionControl.objects.filter(is_active=True).exclude(pk=obj.pk).update(
                is_active=False
            )
        super().save_model(request, obj, form, change)

    @admin.display(description="Status")
    def status_badge(self, obj: AppVersionControl) -> str:
        if obj.maintenance_mode:
            color, label = "#c62828", "Maintenance"
        elif obj.is_active:
            color, label = "#2e7d32", "Active"
        else:
            color, label = "#757575", "Inactive"
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            color,
            label,
        )
