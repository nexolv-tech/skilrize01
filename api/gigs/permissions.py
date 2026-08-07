from rest_framework import permissions


class IsGigOwnerOrReadOnly(permissions.BasePermission):
    """Anyone may read a published gig; only its seller may change it."""

    def has_permission(self, request, view) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.seller_id == request.user.pk


class IsOrderParty(permissions.BasePermission):
    """Only the buyer or the seller on an order may touch it.

    Checked at object level, so guessing an order id returns a 403 rather than
    someone else's purchase.
    """

    message = "You are not a party to this order."

    def has_object_permission(self, request, view, obj) -> bool:
        return obj.involves(request.user)
