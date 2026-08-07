from rest_framework import permissions


class IsContractParty(permissions.BasePermission):
    """Only the client or the freelancer on a contract may touch it.

    Checked at object level so that guessing a contract id gets a 403 rather
    than a contract — the list filter alone is not sufficient (Section 4.4).
    """

    message = "You are not a party to this contract."

    def has_object_permission(self, request, view, obj) -> bool:
        return obj.involves(request.user)
