"""Who may read, post, and moderate inside a community."""

from __future__ import annotations

from rest_framework import permissions

from .models import Community, Membership


class IsCommunityMemberOrReadOnly(permissions.BasePermission):
    """Read a community if it lets you; write only as a member.

    Two separate questions, and conflating them is the usual bug. A closed
    community's *existence* is public so it can be found and joined; its
    *contents* are not.
    """

    message = "Join this community to post in it."
    code = "not_a_member"

    def has_object_permission(self, request, view, obj) -> bool:
        community = obj if isinstance(obj, Community) else obj.community
        if request.method in permissions.SAFE_METHODS:
            return community.can_be_read_by(request.user)
        return community.can_be_posted_in_by(request.user)


class IsAuthorOrModerator(permissions.BasePermission):
    """Edit your own words; remove anyone's if you moderate the space.

    Deletion by a moderator is a soft delete handled in the view — the two
    actions are not the same and must not share a code path, because an author
    deleting their own post should not leave "[removed by a moderator]" behind.
    """

    message = "You can only change your own posts."
    code = "not_yours"

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True

        author_id = getattr(obj, "author_id", None) or getattr(obj, "uploaded_by_id", None)
        if author_id == request.user.pk:
            return True

        community = obj if isinstance(obj, Community) else getattr(obj, "community", None)
        if community is None:
            return False
        return community.role_of(request.user) in {
            Membership.Role.MODERATOR,
            Membership.Role.OWNER,
        }


class IsCommunityModerator(permissions.BasePermission):
    """Pin, lock, ban, and resolve reports."""

    message = "Only a moderator of this community can do that."
    code = "not_a_moderator"

    def has_object_permission(self, request, view, obj) -> bool:
        community = obj if isinstance(obj, Community) else obj.community
        return community.role_of(request.user) in {
            Membership.Role.MODERATOR,
            Membership.Role.OWNER,
        }
