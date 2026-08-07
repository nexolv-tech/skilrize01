"""Request and response shapes for the community layer."""

from __future__ import annotations

from rest_framework import serializers

from core.files import signed_url
from core.scope import Visibility

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


class AuthorSerializer(serializers.Serializer):
    """The slice of a user that every social surface renders.

    Defined here rather than reused from `accounts` because those serializers
    carry verification state and profile completeness — information a
    discussion thread has no business exposing to everyone who can read it.
    """

    id = serializers.IntegerField(read_only=True)
    handle = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()

    def get_avatar_url(self, user) -> str | None:
        return signed_url(user.avatar) if user.avatar_id else None


# --- Communities ------------------------------------------------------------


class CommunitySerializer(serializers.ModelSerializer):
    created_by = AuthorSerializer(read_only=True)
    cover_url = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()
    can_post = serializers.SerializerMethodField()

    class Meta:
        model = Community
        fields = [
            "id",
            "name",
            "slug",
            "tagline",
            "description",
            "kind",
            "cover_url",
            "created_by",
            "member_count",
            "thread_count",
            "is_archived",
            "visibility",
            "my_role",
            "can_post",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "created_by",
            "member_count",
            "thread_count",
            "created_at",
        ]

    def validate(self, attrs):
        """A campus community may only be created by a student of that campus.

        `university` is never taken from the request — it is derived from the
        author. Accepting it would let anyone place a community inside any
        university's portal by sending a different id.
        """
        if attrs.get("visibility") == Visibility.UNIVERSITY:
            author = self.context["request"].user
            if not author.is_verified_student or not author.university_id:
                raise serializers.ValidationError(
                    {"visibility": "Only verified students can create a campus community."}
                )
            attrs["university"] = author.university
        else:
            attrs["university"] = None
        return attrs

    def _viewer(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_cover_url(self, community: Community) -> str | None:
        return signed_url(community.cover) if community.cover_id else None

    def get_my_role(self, community: Community) -> str | None:
        return community.role_of(self._viewer())

    def get_can_post(self, community: Community) -> bool:
        return community.can_be_posted_in_by(self._viewer())


class MembershipSerializer(serializers.ModelSerializer):
    user = AuthorSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "role", "status", "joined_at"]
        read_only_fields = fields


# --- Discussion -------------------------------------------------------------


class ReplySerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    body = serializers.SerializerMethodField()

    class Meta:
        model = Reply
        fields = ["id", "author", "parent", "body", "depth", "is_deleted", "created_at"]
        read_only_fields = ["id", "author", "depth", "is_deleted", "created_at"]

    def get_body(self, reply: Reply) -> str:
        # Removed content never reaches the client, even though the row stays
        # for the moderation trail.
        return reply.visible_body


class ReplyWriteSerializer(serializers.ModelSerializer):
    """Separate from the read serializer because `body` is a method field there.

    Masking removed content on read and accepting it on write are genuinely
    different shapes, and trying to serve both from one class is what produced
    a write path that silently discarded the body.
    """

    class Meta:
        model = Reply
        fields = ["body", "parent"]


class ThreadListSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Thread
        fields = [
            "id",
            "title",
            "author",
            "reply_count",
            "is_pinned",
            "is_locked",
            "last_activity_at",
            "created_at",
        ]
        read_only_fields = fields


class ThreadDetailSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Thread
        fields = [
            "id",
            "community",
            "title",
            "body",
            "author",
            "reply_count",
            "is_pinned",
            "is_locked",
            "last_activity_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "community",
            "author",
            "reply_count",
            "is_pinned",
            "is_locked",
            "last_activity_at",
            "created_at",
        ]


class ChatMessageSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    body = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = ["id", "author", "body", "is_deleted", "created_at"]
        read_only_fields = ["id", "author", "is_deleted", "created_at"]

    def get_body(self, message: ChatMessage) -> str:
        return "[removed]" if message.is_deleted else message.body


class ChatMessageWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["body"]


# --- Events -----------------------------------------------------------------


class EventSerializer(serializers.ModelSerializer):
    created_by = AuthorSerializer(read_only=True)
    my_rsvp = serializers.SerializerMethodField()
    is_full = serializers.BooleanField(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "community",
            "title",
            "description",
            "created_by",
            "starts_at",
            "ends_at",
            "location",
            "online_url",
            "capacity",
            "going_count",
            "is_full",
            "is_cancelled",
            "my_rsvp",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "community",
            "created_by",
            "going_count",
            "is_cancelled",
            "created_at",
        ]

    def get_my_rsvp(self, event: Event) -> str | None:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        rsvp = event.rsvps.filter(user=user).first()
        return rsvp.status if rsvp else None

    def validate(self, attrs):
        instance = Event(**{**{f: getattr(self.instance, f, None) for f in ()}, **attrs})
        instance.clean_fields(exclude=["community", "created_by", "visibility"])
        # Re-run the cross-field rules the model owns, so the API and the admin
        # reject exactly the same things.
        if attrs.get("ends_at") and attrs.get("starts_at"):
            if attrs["ends_at"] <= attrs["starts_at"]:
                raise serializers.ValidationError({"ends_at": "An event must end after it starts."})
        if not attrs.get("location") and not attrs.get("online_url"):
            raise serializers.ValidationError(
                {"location": "Give a place or a link, or nobody can attend."}
            )
        return attrs


class RSVPSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=EventRSVP.Status.choices)


# --- Resources --------------------------------------------------------------


class ResourceSerializer(serializers.ModelSerializer):
    uploaded_by = AuthorSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "community",
            "title",
            "description",
            "kind",
            "url",
            "file_url",
            "tags",
            "uploaded_by",
            "download_count",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "community",
            "file_url",
            "uploaded_by",
            "download_count",
            "created_at",
        ]

    def get_file_url(self, resource: Resource) -> str | None:
        # Short-lived and signed, like every other private file on the
        # platform — a resource inside a campus community must not become a
        # public URL somebody can pass around.
        return signed_url(resource.file) if resource.file_id else None


# --- Peer messaging ---------------------------------------------------------


class DirectMessageSerializer(serializers.ModelSerializer):
    sender = AuthorSerializer(read_only=True)

    class Meta:
        model = DirectMessage
        fields = ["id", "sender", "body", "read_at", "created_at"]
        read_only_fields = ["id", "sender", "read_at", "created_at"]


class ConversationSerializer(serializers.ModelSerializer):
    other = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "other", "last_message", "unread_count", "last_message_at"]
        read_only_fields = fields

    def _viewer(self):
        return getattr(self.context.get("request"), "user", None)

    def get_other(self, conversation: Conversation):
        """The inbox shows who you are talking to, not a list of participants."""
        viewer = self._viewer()
        for participant in conversation.participants.all():
            if participant.pk != getattr(viewer, "pk", None):
                return AuthorSerializer(participant).data
        return None

    def get_last_message(self, conversation: Conversation):
        message = conversation.messages.order_by("-created_at").first()
        return DirectMessageSerializer(message).data if message else None

    def get_unread_count(self, conversation: Conversation) -> int:
        viewer = self._viewer()
        if not viewer or not viewer.is_authenticated:
            return 0
        return conversation.messages.filter(read_at__isnull=True).exclude(sender=viewer).count()


# --- Feed and moderation ----------------------------------------------------


class FeedItemSerializer(serializers.ModelSerializer):
    actor = AuthorSerializer(read_only=True)

    class Meta:
        model = FeedItem
        fields = ["id", "actor", "verb", "summary", "url", "community", "created_at"]
        read_only_fields = fields


class ReportSerializer(serializers.ModelSerializer):
    reporter = AuthorSerializer(read_only=True)

    class Meta:
        model = Report
        fields = [
            "id",
            "reporter",
            "community",
            "kind",
            "object_id",
            "reason",
            "status",
            "resolution_note",
            "created_at",
            "resolved_at",
        ]
        read_only_fields = [
            "id",
            "reporter",
            "status",
            "resolution_note",
            "created_at",
            "resolved_at",
        ]
