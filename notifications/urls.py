from django.urls import path

from .views import DeviceTokenRegisterView, DeviceTokenUnregisterView

urlpatterns = [
    path("devices/", DeviceTokenRegisterView.as_view(), name="device-register"),
    path(
        "devices/<path:token>/",
        DeviceTokenUnregisterView.as_view(),
        name="device-unregister",
    ),
]
