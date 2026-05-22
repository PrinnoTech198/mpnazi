from __future__ import annotations

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django_q.tasks import async_task
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import PrayerAdminNotification, PrayerRequest
from .permissions import IsStaffAdmin
from .rate_limit import prayer_submit_rate_limit_exceeded
from .serializers import (
    AdminStatsSerializer,
    PrayerAdminNotificationSerializer,
    PrayerReplySerializer,
    PrayerRequestAdminSerializer,
    PrayerRequestCreateSerializer,
    PrayerRequestPublicSuccessSerializer,
    PrayerRequestStatusSerializer,
)
from .tasks import notify_admin_new_prayer_task, send_admin_reply_email_task


def _client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "unknown")[:45]


class AdminPrayerPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


@api_view(["POST"])
@permission_classes([AllowAny])
def prayer_submit(request):
    if prayer_submit_rate_limit_exceeded(_client_ip(request)):
        return Response(
            {"detail": "Too many prayer requests. Please try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    ser = PrayerRequestCreateSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    prayer = ser.save()
    async_task(
        "prayers.tasks.notify_admin_new_prayer_task",
        prayer.id,
        task_name=f"prayer_notify_{prayer.id}",
    )

    out = PrayerRequestPublicSuccessSerializer(prayer)
    return Response(out.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsStaffAdmin])
def admin_prayer_list(request):
    qs = PrayerRequest.objects.all()
    status_filter = (request.query_params.get("status") or "").strip().lower()
    if status_filter and status_filter != "all":
        qs = qs.filter(status=status_filter)

    category = (request.query_params.get("category") or "").strip().lower()
    if category:
        qs = qs.filter(category=category)

    search = (request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(request_text__icontains=search)
            | Q(name__icontains=search)
            | Q(email__icontains=search)
            | Q(country__icontains=search)
        )

    paginator = AdminPrayerPagination()
    page = paginator.paginate_queryset(qs, request)
    ser = PrayerRequestAdminSerializer(page, many=True)
    return paginator.get_paginated_response(ser.data)


@api_view(["GET"])
@permission_classes([IsStaffAdmin])
def admin_prayer_detail(request, pk):
    prayer = get_object_or_404(PrayerRequest, pk=pk)
    return Response(PrayerRequestAdminSerializer(prayer).data)


@api_view(["PATCH"])
@permission_classes([IsStaffAdmin])
def admin_prayer_status(request, pk):
    prayer = get_object_or_404(PrayerRequest, pk=pk)
    ser = PrayerRequestStatusSerializer(prayer, data=request.data, partial=True)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
    ser.save()
    return Response(PrayerRequestAdminSerializer(prayer).data)


@api_view(["POST"])
@permission_classes([IsStaffAdmin])
def admin_prayer_reply(request, pk):
    prayer = get_object_or_404(PrayerRequest, pk=pk)
    if not prayer.email:
        return Response(
            {"detail": "This requester did not provide an email address."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ser = PrayerReplySerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    reply_text = ser.validated_data["reply_text"]
    async_task(
        "prayers.tasks.send_admin_reply_email_task",
        prayer.id,
        reply_text,
        request.user.id,
        task_name=f"prayer_reply_{prayer.id}",
    )

    return Response(
        {
            "detail": f"Reply queued for delivery to {prayer.email}.",
            "prayer": PrayerRequestAdminSerializer(prayer).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsStaffAdmin])
def admin_notifications_list(request):
    unread_only = request.query_params.get("unread", "").lower() in ("1", "true", "yes")
    qs = PrayerAdminNotification.objects.select_related("prayer_request")
    if unread_only:
        qs = qs.filter(is_read=False)
    qs = qs[:50]
    return Response(PrayerAdminNotificationSerializer(qs, many=True).data)


@api_view(["PATCH"])
@permission_classes([IsStaffAdmin])
def admin_notification_mark_read(request, pk):
    note = get_object_or_404(PrayerAdminNotification, pk=pk)
    note.is_read = True
    note.save(update_fields=["is_read"])
    return Response(PrayerAdminNotificationSerializer(note).data)


@api_view(["POST"])
@permission_classes([IsStaffAdmin])
def admin_notifications_mark_all_read(request):
    PrayerAdminNotification.objects.filter(is_read=False).update(is_read=True)
    return Response({"detail": "All notifications marked as read."})


@api_view(["GET"])
@permission_classes([IsStaffAdmin])
def admin_stats(request):
    agg = PrayerRequest.objects.aggregate(
        total=Count("id"),
        new_count=Count("id", filter=Q(status=PrayerRequest.STATUS_NEW)),
        praying_count=Count("id", filter=Q(status=PrayerRequest.STATUS_PRAYING)),
        answered_count=Count("id", filter=Q(status=PrayerRequest.STATUS_ANSWERED)),
        urgent_count=Count("id", filter=Q(status=PrayerRequest.STATUS_URGENT)),
    )
    pending = (agg["new_count"] or 0) + (agg["urgent_count"] or 0)
    unread = PrayerAdminNotification.objects.filter(is_read=False).count()
    data = {
        **agg,
        "pending_count": pending,
        "unread_notifications": unread,
    }
    return Response(AdminStatsSerializer(data).data)
