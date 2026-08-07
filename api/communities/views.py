"""
Endpoints for the community layer.

Every queryset here starts from a scope-enforcing manager, so the surface
filter is applied before anything else — including before the membership
filter. That order matters: filtering by membership first and scope second
would let a campus community leak into a global listing for anyone who happened
to be a member of it.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core import files as filestore
from core.models import AuditLog, NotificationCategory, StoredFile
from core.notify import dispatch
from core.pagination import CompactPagination, StandardPagination

from .models import (
    ChatMessage,
    Community,
    Conversation,
    DirectMessage,
    Event,
    EventRSVP,
    FeedItem,
    Membership,
    Reply,
    Report,
    Resource,
    Thread,
)
from .permissions import IsAuthorOrModerator, IsCommunityMemberOrReadOnly, IsCommunityModerator
from .serializers import (
    ChatMessageSerializer,
    ChatMessageWriteSerializer,
    CommunitySerializer,
    ConversationSerializer,
    DirectMessageSerializer,
    EventSerializer,
    FeedItemSerializer,
    MembershipSerializer,
    ReplySerializer,
    ReplyWriteSerializer,
    ReportSerializer,
    ResourceSerializer,
    RSVPSerializer,
    ThreadDetailSerializer,
    ThreadListSerializer,
)


def _bad(message: str, code: str = "invalid"):
    return Response({"detail": message, "code": code}, status=status.HTTP_400_BAD_REQUEST)


def _forbidden(message: str, code: str = "forbidden"):
    return Response({"detail": message, "code": code}, status=status.HTTP_403_FORBIDDEN)


def _readable_community(pk, user) -> Community:
    """Fetch a community the caller is allowed to look inside.

    404 rather than 403 for a closed community: a 403 confirms it exists and
    who is in it, which is the thing a closed space is hiding.
    """
    community = get_object_or_404(Community, pk=pk)
    if not community.can_be_read_by(user):
        from django.http import Http404

        raise Http404
    return community


# --- Communities ------------------------------------------------------------


class CommunityViewSet(viewsets.ModelViewSet):
    """
    GET    /communities/              directory on the active surface
    POST   /communities/              create one
    GET    /communities/<id>/         one community
    POST   /communities/<id>/join/    join, or request to
    POST   /communities/<id>/leave/   leave
    GET    /communities/<id>/members/ roster (members only)
    """

    serializer_class = CommunitySerializer
    permission_classes = [IsAuthenticated, IsCommunityMemberOrReadOnly]
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = Community.objects.select_related("created_by").filter(is_archived=False)
        params = self.request.query_params

        if search := params.get("q", "").strip():
            queryset = queryset.filter(Q(name__icontains=search) | Q(tagline__icontains=search))
        if params.get("mine") == "true" and self.request.user.is_authenticated:
            queryset = queryset.filter(
                memberships__user=self.request.user,
                memberships__status=Membership.Status.ACTIVE,
            )
        return queryset

    def perform_create(self, serializer):
        # The creator is the first member and the owner. Doing this in one
        # transaction means a community can never exist with nobody able to
        # moderate it.
        with transaction.atomic():
            community = serializer.save(created_by=self.request.user, member_count=1)
            Membership.objects.create(
                community=community,
                user=self.request.user,
                role=Membership.Role.OWNER,
            )
        FeedItem.record(
            self.request.user,
            FeedItem.Verb.COMMUNITY_CREATED,
            f"{self.request.user.display_name} created {community.name}",
            url=f"/communities/{community.pk}",
            community=community,
        )
        AuditLog.record(
            actor=self.request.user,
            action=AuditLog.Action.CREATE,
            target=community,
            request=self.request,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def join(self, request, pk=None):
        # Plain lookup, not `_readable_community`: a closed community is
        # discoverable by design, so asking to join one must explain *why* it
        # is refused rather than pretending it does not exist.
        community = get_object_or_404(Community, pk=pk)
        if community.is_archived:
            return _bad("This community is archived.")

        existing = community.memberships.filter(user=request.user).first()
        if existing and existing.status == Membership.Status.BANNED:
            return _forbidden("You cannot rejoin this community.", "banned")
        if existing and existing.status == Membership.Status.ACTIVE:
            return Response(CommunitySerializer(community, context={"request": request}).data)

        if community.kind == Community.Kind.CLOSED:
            return _forbidden("This community is invite only.", "invite_only")

        pending = community.kind == Community.Kind.REQUEST
        membership = existing or Membership(community=community, user=request.user)
        membership.status = Membership.Status.PENDING if pending else Membership.Status.ACTIVE
        membership.role = Membership.Role.MEMBER
        membership.save()

        if not pending:
            community.member_count = community.memberships.filter(
                status=Membership.Status.ACTIVE
            ).count()
            community.save(update_fields=["member_count", "updated_at"])
            FeedItem.record(
                request.user,
                FeedItem.Verb.JOINED_COMMUNITY,
                f"{request.user.display_name} joined {community.name}",
                url=f"/communities/{community.pk}",
                community=community,
            )

        return Response(CommunitySerializer(community, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def leave(self, request, pk=None):
        community = get_object_or_404(Community, pk=pk)
        membership = community.memberships.filter(user=request.user).first()
        if membership is None:
            return _bad("You are not a member.")
        if membership.role == Membership.Role.OWNER:
            # Otherwise a community can be orphaned with nobody able to
            # moderate it, and the only fix is a database edit.
            return _bad("Hand ownership to someone else before leaving.", "owner_cannot_leave")

        membership.delete()
        community.member_count = community.memberships.filter(
            status=Membership.Status.ACTIVE
        ).count()
        community.save(update_fields=["member_count", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def members(self, request, pk=None):
        community = get_object_or_404(Community, pk=pk)
        if community.role_of(request.user) is None:
            return _forbidden("Join to see who else is here.", "not_a_member")
        roster = community.memberships.select_related("user").filter(
            status=Membership.Status.ACTIVE
        )
        return Response(MembershipSerializer(roster, many=True).data)


# --- Discussion -------------------------------------------------------------


class ThreadViewSet(viewsets.ModelViewSet):
    """Discussions. Listed per community via `?community=<id>`."""

    permission_classes = [IsAuthenticated, IsAuthorOrModerator]
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return super().get_permissions()

    def get_serializer_class(self):
        return ThreadListSerializer if self.action == "list" else ThreadDetailSerializer

    def get_queryset(self):
        queryset = Thread.objects.select_related("author", "community")
        community_id = self.request.query_params.get("community")
        if community_id:
            queryset = queryset.filter(community_id=community_id)
        # Closed communities are readable only by members, and the same rule
        # has to hold for a bare thread list that never named a community.
        if not self.request.user.is_authenticated:
            return queryset.exclude(community__kind=Community.Kind.CLOSED)
        return queryset.exclude(
            Q(community__kind=Community.Kind.CLOSED)
            & ~Q(
                community__memberships__user=self.request.user,
                community__memberships__status=Membership.Status.ACTIVE,
            )
        )

    def create(self, request, *args, **kwargs):
        community = _readable_community(request.data.get("community"), request.user)
        if not community.can_be_posted_in_by(request.user):
            return _forbidden("Join this community to post in it.", "not_a_member")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        thread = serializer.save(author=request.user, community=community)

        Thread.objects.filter(pk=thread.pk).update(last_activity_at=timezone.now())
        community.thread_count = community.threads.count()
        community.save(update_fields=["thread_count", "updated_at"])

        FeedItem.record(
            request.user,
            FeedItem.Verb.THREAD_POSTED,
            f"{request.user.display_name} started “{thread.title}” in {community.name}",
            url=f"/communities/{community.pk}/threads/{thread.pk}",
            community=community,
        )
        return Response(
            ThreadDetailSerializer(thread, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"], permission_classes=[AllowAny])
    def replies(self, request, pk=None):
        thread = self.get_object()

        if request.method == "GET":
            queryset = thread.replies.select_related("author").order_by("created_at")
            page = self.paginate_queryset(queryset)
            return self.get_paginated_response(ReplySerializer(page, many=True).data)

        if not request.user.is_authenticated:
            return _forbidden("Sign in to reply.", "not_authenticated")
        if thread.is_locked:
            return _bad("This discussion is locked.", "locked")
        if not thread.community.can_be_posted_in_by(request.user):
            return _forbidden("Join this community to reply.", "not_a_member")

        serializer = ReplyWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        parent = None
        if parent_id := serializer.validated_data.get("parent"):
            parent = get_object_or_404(Reply, pk=parent_id.pk, thread=thread)
            if parent.depth + 1 > Reply.MAX_DEPTH:
                return _bad("This conversation is nested as deep as it goes.", "too_deep")

        reply = Reply.objects.create(
            thread=thread,
            author=request.user,
            parent=parent,
            body=serializer.validated_data["body"],
        )
        Thread.objects.filter(pk=thread.pk).update(
            reply_count=thread.replies.count(), last_activity_at=timezone.now()
        )

        # Tell the thread author somebody answered — but not when they are
        # answering themselves.
        if thread.author_id != request.user.pk:
            dispatch(
                thread.author,
                NotificationCategory.COMMUNITY,
                "New reply to your discussion",
                f"{request.user.display_name} replied to “{thread.title}”.",
                data={"thread_id": thread.pk},
            )
        return Response(ReplySerializer(reply).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsCommunityModerator]
    )
    def pin(self, request, pk=None):
        thread = self.get_object()
        thread.is_pinned = not thread.is_pinned
        thread.save(update_fields=["is_pinned", "updated_at"])
        return Response(ThreadDetailSerializer(thread, context={"request": request}).data)

    @action(
        detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsCommunityModerator]
    )
    def lock(self, request, pk=None):
        thread = self.get_object()
        thread.is_locked = not thread.is_locked
        thread.save(update_fields=["is_locked", "updated_at"])
        return Response(ThreadDetailSerializer(thread, context={"request": request}).data)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_reply(request, pk):
    """Soft-delete a reply.

    Author and moderator take different paths on purpose. An author removing
    their own words should not leave "[removed by a moderator]" behind, which
    reads as a sanction that never happened.
    """
    reply = get_object_or_404(Reply.objects.select_related("thread__community"), pk=pk)
    community = reply.thread.community
    is_author = reply.author_id == request.user.pk
    is_moderator = community.role_of(request.user) in {
        Membership.Role.MODERATOR,
        Membership.Role.OWNER,
    }

    if not (is_author or is_moderator):
        return _forbidden("You can only remove your own replies.", "not_yours")

    reply.is_deleted = True
    reply.deleted_by = None if is_author else request.user
    reply.save(update_fields=["is_deleted", "deleted_by", "updated_at"])

    if is_moderator and not is_author:
        AuditLog.record(
            actor=request.user,
            action=AuditLog.Action.DELETE,
            target=reply,
            request=request,
            justification="Reply removed by a community moderator.",
        )
    return Response(status=status.HTTP_204_NO_CONTENT)


# --- Group chat -------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def community_chat(request, pk):
    """The community's live chat: newest first, cursor by `before`."""
    community = _readable_community(pk, request.user)
    if community.role_of(request.user) is None:
        return _forbidden("Join this community to read its chat.", "not_a_member")

    if request.method == "GET":
        queryset = community.chatmessages.select_related("author")
        if before := request.query_params.get("before"):
            queryset = queryset.filter(pk__lt=before)
        messages = list(queryset[:50])
        # Reversed so the client renders oldest-to-newest without re-sorting,
        # while the query still uses the descending index.
        return Response(ChatMessageSerializer(reversed(messages), many=True).data)

    serializer = ChatMessageWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    message = ChatMessage.objects.create(
        community=community, author=request.user, body=serializer.validated_data["body"]
    )
    return Response(ChatMessageSerializer(message).data, status=status.HTTP_201_CREATED)


# --- Events -----------------------------------------------------------------


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated, IsAuthorOrModerator]
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = Event.objects.select_related("created_by", "community")
        if community_id := self.request.query_params.get("community"):
            queryset = queryset.filter(community_id=community_id)
        if self.request.query_params.get("past") != "true":
            queryset = queryset.filter(starts_at__gte=timezone.now())
        if not self.request.user.is_authenticated:
            return queryset.exclude(community__kind=Community.Kind.CLOSED)
        return queryset

    def create(self, request, *args, **kwargs):
        community = _readable_community(request.data.get("community"), request.user)
        if not community.can_be_posted_in_by(request.user):
            return _forbidden("Join this community to schedule an event.", "not_a_member")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save(created_by=request.user, community=community)

        FeedItem.record(
            request.user,
            FeedItem.Verb.EVENT_CREATED,
            f"{request.user.display_name} scheduled “{event.title}”",
            url=f"/communities/{community.pk}/events/{event.pk}",
            community=community,
        )
        return Response(
            EventSerializer(event, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def rsvp(self, request, pk=None):
        event = self.get_object()
        if event.is_cancelled:
            return _bad("This event was cancelled.")
        if event.community.role_of(request.user) is None:
            return _forbidden("Join this community to RSVP.", "not_a_member")

        serializer = RSVPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wanted = serializer.validated_data["status"]

        existing = event.rsvps.filter(user=request.user).first()
        going_already = existing is not None and existing.status == EventRSVP.Status.GOING
        if wanted == EventRSVP.Status.GOING and not going_already and event.is_full:
            return _bad("This event is full.", "event_full")

        EventRSVP.objects.update_or_create(
            event=event, user=request.user, defaults={"status": wanted}
        )
        event.going_count = event.rsvps.filter(status=EventRSVP.Status.GOING).count()
        event.save(update_fields=["going_count", "updated_at"])
        return Response(EventSerializer(event, context={"request": request}).data)

    @action(
        detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsAuthorOrModerator]
    )
    def cancel(self, request, pk=None):
        event = self.get_object()
        event.is_cancelled = True
        event.save(update_fields=["is_cancelled", "updated_at"])

        # Everyone who planned around it deserves to hear.
        for rsvp in event.rsvps.select_related("user").filter(status=EventRSVP.Status.GOING):
            dispatch(
                rsvp.user,
                NotificationCategory.COMMUNITY,
                "Event cancelled",
                f"“{event.title}” has been cancelled.",
                data={"event_id": event.pk},
            )
        return Response(EventSerializer(event, context={"request": request}).data)


# --- Resources --------------------------------------------------------------


class ResourceViewSet(viewsets.ModelViewSet):
    serializer_class = ResourceSerializer
    permission_classes = [IsAuthenticated, IsAuthorOrModerator]
    pagination_class = StandardPagination

    def get_queryset(self):
        queryset = Resource.objects.select_related("uploaded_by", "community")
        if community_id := self.request.query_params.get("community"):
            queryset = queryset.filter(community_id=community_id)
        if search := self.request.query_params.get("q", "").strip():
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        return queryset

    def create(self, request, *args, **kwargs):
        community = _readable_community(request.data.get("community"), request.user)
        if not community.can_be_posted_in_by(request.user):
            return _forbidden("Join this community to share a resource.", "not_a_member")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        stored = None
        if uploaded := request.FILES.get("file"):
            stored = filestore.store(
                uploaded, owner=request.user, purpose=StoredFile.Purpose.ATTACHMENT
            )

        resource = serializer.save(uploaded_by=request.user, community=community, file=stored)
        # Validated after save so `clean` sees the stored file; a resource that
        # is neither a file nor a link is meaningless.
        try:
            resource.full_clean(exclude=["community", "uploaded_by", "visibility", "university"])
        except Exception:
            resource.delete()
            return _bad("A resource needs either a file or a link.")

        FeedItem.record(
            request.user,
            FeedItem.Verb.RESOURCE_SHARED,
            f"{request.user.display_name} shared “{resource.title}”",
            url=f"/communities/{community.pk}/resources",
            community=community,
        )
        return Response(
            ResourceSerializer(resource, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


# --- Peer messaging ---------------------------------------------------------


class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    """The inbox. Only ever your own conversations."""

    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        return (
            Conversation.objects.filter(participants=self.request.user)
            .prefetch_related("participants")
            .distinct()
        )

    @action(detail=True, methods=["get", "post"], pagination_class=CompactPagination)
    def messages(self, request, pk=None):
        conversation = self.get_object()

        if request.method == "GET":
            queryset = conversation.messages.select_related("sender")
            # Reading the thread marks the other side's messages read. Doing it
            # here rather than in a separate call means an unread badge can
            # never be left stale by a client that forgot to send it.
            conversation.messages.filter(read_at__isnull=True).exclude(sender=request.user).update(
                read_at=timezone.now()
            )
            page = self.paginate_queryset(queryset)
            return self.get_paginated_response(DirectMessageSerializer(page, many=True).data)

        serializer = DirectMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = DirectMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            body=serializer.validated_data["body"],
        )
        Conversation.objects.filter(pk=conversation.pk).update(last_message_at=timezone.now())

        for participant in conversation.participants.exclude(pk=request.user.pk):
            dispatch(
                participant,
                NotificationCategory.MESSAGE,
                f"Message from {request.user.display_name}",
                message.body[:140],
                data={"conversation_id": conversation.pk},
            )
        return Response(DirectMessageSerializer(message).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_conversation(request):
    """Open (or reuse) a conversation with another user by handle."""
    from accounts.models import User

    handle = (request.data.get("handle") or "").strip()
    if not handle:
        return _bad("Who do you want to message?")

    other = get_object_or_404(User, handle=handle, is_active=True)
    if other.pk == request.user.pk:
        return _bad("You cannot message yourself.")

    conversation = Conversation.between(request.user, other)
    return Response(
        ConversationSerializer(conversation, context={"request": request}).data,
        status=status.HTTP_201_CREATED,
    )


# --- Feed and moderation ----------------------------------------------------


@api_view(["GET"])
@permission_classes([AllowAny])
def activity_feed(request):
    """What has been happening on the surface you are standing on.

    `FeedItem.objects` is scope-enforcing, so the campus feed and the global
    feed are the same code path with a different scope — there is no separate
    "campus feed" query that could be missed.
    """
    queryset = FeedItem.objects.select_related("actor", "community")
    if verb := request.query_params.get("verb"):
        queryset = queryset.filter(verb=verb)

    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(FeedItemSerializer(page, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def report_content(request):
    """Flag something for a moderator."""
    serializer = ReportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    report, created = Report.objects.get_or_create(
        reporter=request.user,
        kind=serializer.validated_data["kind"],
        object_id=serializer.validated_data["object_id"],
        status=Report.Status.OPEN,
        defaults={
            "reason": serializer.validated_data["reason"],
            "community": serializer.validated_data.get("community"),
        },
    )
    if not created:
        return Response(
            {"detail": "You have already reported this.", "code": "already_reported"},
            status=status.HTTP_409_CONFLICT,
        )
    return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def moderation_queue(request):
    """Open reports for communities the caller moderates.

    Scoped to what they actually moderate rather than to a global admin role —
    a university moderator sees their campus's reports and nobody else's.
    """
    moderated = Membership.objects.filter(
        user=request.user,
        status=Membership.Status.ACTIVE,
        role__in=[Membership.Role.MODERATOR, Membership.Role.OWNER],
    ).values_list("community_id", flat=True)

    reports = Report.objects.filter(
        status=Report.Status.OPEN, community_id__in=list(moderated)
    ).select_related("reporter")
    return Response(ReportSerializer(reports, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resolve_report(request, pk):
    report = get_object_or_404(Report.objects.select_related("community"), pk=pk)
    if report.community is None or report.community.role_of(request.user) not in {
        Membership.Role.MODERATOR,
        Membership.Role.OWNER,
    }:
        return _forbidden("Only a moderator of that community can resolve this.", "not_a_moderator")

    upheld = bool(request.data.get("upheld"))
    report.status = Report.Status.UPHELD if upheld else Report.Status.DISMISSED
    report.resolution_note = (request.data.get("note") or "")[:2000]
    report.resolved_by = request.user
    report.resolved_at = timezone.now()
    report.save(
        update_fields=["status", "resolution_note", "resolved_by", "resolved_at", "updated_at"]
    )

    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=report,
        request=request,
        justification=f"Report {report.status}.",
    )
    return Response(ReportSerializer(report).data)
