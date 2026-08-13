from rest_framework import permissions


class IsStaffOrAdmin(permissions.BasePermission):
    """Authoring and reviewing challenges — staff/admin only, never a participant."""

    message = "Staff only."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or user.admin_role))
