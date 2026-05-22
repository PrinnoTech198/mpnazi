from rest_framework.permissions import BasePermission


class IsStaffAdmin(BasePermission):
    """Admin/leaders: Django users with is_staff."""

    message = "Admin access required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)
