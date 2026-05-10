from rest_framework.permissions import BasePermission, SAFE_METHODS


class PublicReadAuthenticatedWrite(BasePermission):
    """
    Public can read; authenticated users can write.
    Useful for user-generated resources with public listing/detail.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)


class PublicReadAdminWrite(BasePermission):
    """
    Public can read; only staff/admin users can write.
    Useful for public content managed from admin.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)
