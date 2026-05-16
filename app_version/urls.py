from django.urls import path

from .views import AppVersionControlView

urlpatterns = [
    path(
        "app/version-control/",
        AppVersionControlView.as_view(),
        name="app-version-control",
    ),
]
