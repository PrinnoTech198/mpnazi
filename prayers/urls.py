from django.urls import path

from . import views

urlpatterns = [
    path("prayers/submit/", views.prayer_submit, name="prayer-submit"),
    path("admin/prayers/", views.admin_prayer_list, name="admin-prayer-list"),
    path("admin/prayers/<int:pk>/", views.admin_prayer_detail, name="admin-prayer-detail"),
    path(
        "admin/prayers/<int:pk>/status/",
        views.admin_prayer_status,
        name="admin-prayer-status",
    ),
    path(
        "admin/prayers/<int:pk>/reply/",
        views.admin_prayer_reply,
        name="admin-prayer-reply",
    ),
    path(
        "admin/notifications/",
        views.admin_notifications_list,
        name="admin-notifications-list",
    ),
    path(
        "admin/notifications/read-all/",
        views.admin_notifications_mark_all_read,
        name="admin-notifications-read-all",
    ),
    path(
        "admin/notifications/<int:pk>/read/",
        views.admin_notification_mark_read,
        name="admin-notification-read",
    ),
    path("admin/stats/", views.admin_stats, name="admin-stats"),
]
