from rest_framework import permissions


class IsProjectOwnerOrReadOnly(permissions.BasePermission):
    """Anyone may read a published brief; only its author may change it.

    This is the object-level half of the rule — Section 4.4 requires the check
    on every detail endpoint, not only on lists, because guessing an id must
    not bypass anything.
    """

    def has_permission(self, request, view) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.client_id == request.user.pk
