from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AppVersionControl
from .serializers import AppVersionControlSerializer


class AppVersionControlView(APIView):
    """
    GET /api/app/version-control/

    Returns the single active version-control configuration for mobile clients.
    Public endpoint — no authentication required.
    """

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        config = AppVersionControl.objects.filter(is_active=True).first()
        if config is None:
            return Response(
                {
                    "success": False,
                    "message": "No active version configuration found.",
                    "data": None,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AppVersionControlSerializer(config)
        return Response(
            {
                "success": True,
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
