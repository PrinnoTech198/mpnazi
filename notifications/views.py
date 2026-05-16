from __future__ import annotations

from urllib.parse import unquote

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DeviceToken
from .serializers import DeviceTokenSerializer


class DeviceTokenRegisterView(APIView):
    """
    POST /api/devices/ — register or refresh an FCM device token.
    Optional JWT: when present, associates the row with the authenticated user.
    """

    def post(self, request, *args, **kwargs):
        ser = DeviceTokenSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        token = ser.validated_data["token"]
        platform = ser.validated_data["platform"]
        user = request.user if getattr(request.user, "is_authenticated", False) else None

        existing = DeviceToken.objects.filter(token=token).first()
        target_user = user if user is not None else (existing.user if existing else None)

        DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                "platform": platform,
                "user": target_user,
            },
        )
        return Response({"success": True}, status=status.HTTP_200_OK)


class DeviceTokenUnregisterView(APIView):
    """
    DELETE /api/devices/<token>/ — remove token on logout (URL-encoded token).
    """

    def delete(self, request, token: str, *args, **kwargs):
        raw = unquote(token).strip()
        if not raw:
            return Response({"success": False, "detail": "Missing token."}, status=400)
        DeviceToken.objects.filter(token=raw).delete()
        return Response({"success": True}, status=status.HTTP_200_OK)
