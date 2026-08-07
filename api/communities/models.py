"""
Communities, discussion, events, resources, peer messaging, and the activity
feed — the retention layer that makes a campus portal somewhere to *be* rather
than somewhere to transact.

Two design decisions run through the whole file and are worth stating once.

**Everything a community contains is itself scopeable.** A thread only exists
inside a community, so in principle its tenancy could be inherited by joining
through `community`. It is not: `Thread`, `Event`, `Resource`, and `FeedItem`
are each `ScopedModel` with their own `visibility`/`university`, copied from
the parent on save. This is deliberate duplication. `core.test_tenancy`
discovers every `ScopedModel` automatically and proves it filters, so making
these scopeable puts them inside the release gate for free — whereas a model
that inherits tenancy through a join is exactly the shape that leaks when
somebody writes `Thread.objects.filter(...)` without remembering the join.

**Peer messaging is not scoped.** A conversation is between two people, not
inside a surface. Scoping it would break the case the platform exists for — a
verified student messaging a client in the global marketplace — and there is
nothing to leak, because a conversation is only ever readable by its two
participants.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from core.models import ScopedModel, TimestampedModel
from core.scope import Visibility


class CommunityScopedModel(ScopedModel):
    """Content that lives inside a community and borrows its surface.

    The copy happens on save rather than being read through the relation so
    that the scope filter stays a plain column predicate. A tenancy filter that
    needs a join is a tenancy filter somebody will eventually write without the
    join.
    """

    community = models.ForeignKey(
        "communities.Community", on_delete=models.CASCADE, related_name="%(class)ss"
    )

    class Meta(ScopedModel.Meta):
        abstract = True

    def save(self, *args, **kwargs):
        # Always re-derived, never trusted from the caller: a client that could
        # set `visibility` directly could publish campus content globally.
        if self.community_id:
            self.visibility = self.community.visibility
            self.university_id = self.community.university_id
        return super().save(*args, **kwargs)


# --- Communities ------------------------------------------------------------


class Community(ScopedModel):
    """A space, global or campus-only, that people join."""

    class Kind(models.TextChoices):
        OPEN = "open", "Anyone can join"
        REQUEST = "request", "Joining needs approval"
        CLOSED = "closed", "Invite only"

    name = models.CharField(max_length=120, validators=[MinLengthValidator(3)])
    slug = models.SlugField(max_length=140, unique=True)
    tagline = models.CharField(max_length=180, blank=True)
    description = models.TextField(blank=True)
    cover = models.ForeignKey(
        "core.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.OPEN)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="communities_created"
    )
    #: Denormalised so a directory of 200 communities is one query rather than
    #: 200 counts. Maintained by `join`/`leave`.
    member_count = models.PositiveIntegerField(default=0)
    thread_count = models.PositiveIntegerField(default=0)
    is_archived = models.BooleanField(default=False)

    class Meta(ScopedModel.Meta):
        ordering = ["-member_count", "name"]
        verbose_name_plural = "communities"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        return super().save(*args, **kwargs)

    def _unique_slug(self) -> str:
        base = slugify(self.name)[:120] or "community"
        candidate, suffix = base, 2
        # `all_objects`, not `objects`: uniqueness is global across every
        # surface, so the check must see rows the caller's scope would hide.
        # Checking through the scoped manager would let two universities each
        # take the same slug and collide on the unique index.
        while Community.all_objects.filter(slug=candidate).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def role_of(self, user) -> str | None:
        if not user or not user.is_authenticated:
            return None
        membership = self.memberships.filter(user=user, status=Membership.Status.ACTIVE).first()
        return membership.role if membership else None

    def can_be_read_by(self, user) -> bool:
        """Closed communities hide their contents, not their existence.

        A directory entry is public so people know a space exists and can ask
        to join; the threads inside are not. Hiding the entry too would make
        closed communities undiscoverable and therefore unjoinable.
        """
        if self.kind != self.Kind.CLOSED:
            return True
        return self.role_of(user) is not None

    def can_be_posted_in_by(self, user) -> bool:
        return self.role_of(user) is not None and not self.is_archived


class Membership(TimestampedModel):
    class Role(models.TextChoices):
        MEMBER = "member", "Member"
        MODERATOR = "moderator", "Moderator"
        OWNER = "owner", "Owner"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PENDING = "pending", "Awaiting approval"
        BANNED = "banned", "Banned"

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="community_memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-joined_at"]
        constraints = [
            models.UniqueConstraint(fields=["community", "user"], name="one_membership_per_user")
        ]
        indexes = [models.Index(fields=["community", "status", "role"])]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.community_id} ({self.role})"

    @property
    def can_moderate(self) -> bool:
        return self.role in {self.Role.MODERATOR, self.Role.OWNER}


# --- Discussion -------------------------------------------------------------


class Thread(CommunityScopedModel):
    """One discussion topic."""

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="threads"
    )
    title = models.CharField(max_length=200, validators=[MinLengthValidator(5)])
    body = models.TextField(validators=[MinLengthValidator(10)])

    is_pinned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    reply_count = models.PositiveIntegerField(default=0)
    #: Drives ordering. Bumped by every reply, so an active thread rises
    #: without a subquery over replies on every list request.
    last_activity_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta(ScopedModel.Meta):
        # Pinned first, then genuinely active. Both descending, so the ordering
        # is a single index scan.
        ordering = ["-is_pinned", "-last_activity_at"]
        indexes = [models.Index(fields=["community", "-is_pinned", "-last_activity_at"])]

    def __str__(self) -> str:
        return self.title

    def bump(self) -> None:
        self.last_activity_at = timezone.now()
        self.save(update_fields=["last_activity_at", "updated_at"])


class Reply(TimestampedModel):
    """A comment, optionally nested under another.

    Not a `ScopedModel`: a reply is unreachable except through its thread, and
    the thread is scoped. Adding a third copy of the tenancy columns to the
    highest-volume table in the app would cost more than it protects.
    """

    #: Deep nesting is unreadable on a phone and unbounded nesting is a
    #: rendering denial-of-service. Three levels is a conversation; ten is a
    #: thread nobody finishes.
    MAX_DEPTH = 3

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="replies"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    body = models.TextField(validators=[MinLengthValidator(1)])
    depth = models.PositiveSmallIntegerField(default=0)
    #: Soft delete: removing the row would orphan every reply beneath it, and
    #: a moderator removing abuse should not also delete the answers to it.
    is_deleted = models.BooleanField(default=False)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["thread", "created_at"])]

    def __str__(self) -> str:
        return f"Reply {self.pk} on thread {self.thread_id}"

    def clean(self) -> None:
        super().clean()
        if self.parent and self.parent.thread_id != self.thread_id:
            raise ValidationError({"parent": "A reply must stay in its own thread."})
        if self.parent and self.parent.depth + 1 > self.MAX_DEPTH:
            raise ValidationError({"parent": "This conversation is nested as deep as it goes."})

    def save(self, *args, **kwargs):
        self.depth = self.parent.depth + 1 if self.parent else 0
        return super().save(*args, **kwargs)

    @property
    def visible_body(self) -> str:
        return "[removed by a moderator]" if self.is_deleted else self.body


class ChatMessage(CommunityScopedModel):
    """The community's group chat: one flat, fast stream per community.

    Kept separate from `Thread`/`Reply` rather than modelled as a thread whose
    replies never nest, because the two are read completely differently. A
    thread is browsed by topic and lives for weeks; chat is tailed from the
    bottom and is stale in an hour. Sharing a table would mean every chat poll
    scanning the discussion index.

    Transport is polling for now. The read model is what a socket would need,
    so adding one later is a delivery change rather than a schema change.
    """

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_messages"
    )
    body = models.TextField(validators=[MinLengthValidator(1)], max_length=4000)
    is_deleted = models.BooleanField(default=False)

    class Meta(ScopedModel.Meta):
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["community", "-created_at"])]

    def __str__(self) -> str:
        return f"Chat {self.pk} in {self.community_id}"


# --- Events -----------------------------------------------------------------


class Event(CommunityScopedModel):
    title = models.CharField(max_length=200, validators=[MinLengthValidator(3)])
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="events_created"
    )

    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    online_url = models.URLField(blank=True)
    #: 0 means unlimited, which is the common case and avoids a nullable int
    #: that every caller would have to branch on.
    capacity = models.PositiveIntegerField(default=0)
    is_cancelled = models.BooleanField(default=False)
    going_count = models.PositiveIntegerField(default=0)

    class Meta(ScopedModel.Meta):
        ordering = ["starts_at"]
        indexes = [models.Index(fields=["community", "starts_at"])]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "An event must end after it starts."})
        if not self.location and not self.online_url:
            raise ValidationError({"location": "Give a place or a link, or nobody can attend."})

    @property
    def is_full(self) -> bool:
        return bool(self.capacity) and self.going_count >= self.capacity

    @property
    def has_started(self) -> bool:
        return self.starts_at <= timezone.now()


class EventRSVP(TimestampedModel):
    class Status(models.TextChoices):
        GOING = "going", "Going"
        INTERESTED = "interested", "Interested"
        DECLINED = "declined", "Can't make it"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="rsvps")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rsvps"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.GOING)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["event", "user"], name="one_rsvp_per_user")]

    def __str__(self) -> str:
        return f"{self.user_id} {self.status} {self.event_id}"


# --- Resource library -------------------------------------------------------


class Resource(CommunityScopedModel):
    """A shared file or link — past papers, templates, reading lists."""

    class Kind(models.TextChoices):
        FILE = "file", "File"
        LINK = "link", "Link"

    title = models.CharField(max_length=200, validators=[MinLengthValidator(3)])
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=6, choices=Kind.choices, default=Kind.FILE)
    file = models.ForeignKey(
        "core.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    url = models.URLField(blank=True)
    tags = models.JSONField(default=list, blank=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resources"
    )
    download_count = models.PositiveIntegerField(default=0)

    class Meta(ScopedModel.Meta):
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["community", "-created_at"])]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        if self.kind == self.Kind.LINK and not self.url:
            raise ValidationError({"url": "A link resource needs a URL."})
        if self.kind == self.Kind.FILE and not self.file_id:
            raise ValidationError({"file": "A file resource needs a file."})


# --- Peer messaging ---------------------------------------------------------


class Conversation(TimestampedModel):
    """A direct thread between two people.

    Deliberately not scoped — see the module docstring. Two participants rather
    than a generic group: group conversation already exists as a community's
    chat, and a second, subtly different group model would be two places to fix
    every moderation bug.
    """

    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="conversations")
    #: Denormalised for the inbox ordering, which is the hottest read here.
    last_message_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-last_message_at"]

    def __str__(self) -> str:
        return f"Conversation {self.pk}"

    @classmethod
    def between(cls, first, second) -> Conversation:
        """Find or open the conversation between two people.

        Matched on the participant set rather than an ordered pair, so it does
        not matter who opens it first and a second conversation between the
        same two people is impossible.
        """
        # The membership tests are subqueries rather than chained
        # `filter(participants=…)` calls, because a chained filter constrains
        # the very join the Count annotation is computed over — the size comes
        # back as 1, matches nothing, and a second conversation is opened every
        # time the other side replies. Subqueries leave the annotation's join
        # untouched, so `total` really is the participant count.
        existing = (
            cls.objects.annotate(total=models.Count("participants", distinct=True))
            .filter(total=2)
            .filter(pk__in=cls.objects.filter(participants=first).values("pk"))
            .filter(pk__in=cls.objects.filter(participants=second).values("pk"))
            .first()
        )
        if existing:
            return existing
        conversation = cls.objects.create()
        conversation.participants.add(first, second)
        return conversation


class DirectMessage(TimestampedModel):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages"
    )
    body = models.TextField(validators=[MinLengthValidator(1)], max_length=8000)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self) -> str:
        return f"Message {self.pk}"


# --- Activity feed ----------------------------------------------------------


class FeedItem(ScopedModel):
    """One line of the campus activity feed.

    Written when something happens rather than assembled by querying every
    source table at read time. A feed built by union-ing six tables is six
    queries that grow with the platform; a feed built by appending is one
    index scan no matter how large the platform gets.

    It carries denormalised display text on purpose. A feed entry is a record
    of what happened *then* — if a community is later renamed, the line that
    said someone joined its old name is still what happened.
    """

    class Verb(models.TextChoices):
        COMMUNITY_CREATED = "community_created", "created a community"
        JOINED_COMMUNITY = "joined_community", "joined a community"
        THREAD_POSTED = "thread_posted", "started a discussion"
        EVENT_CREATED = "event_created", "scheduled an event"
        RESOURCE_SHARED = "resource_shared", "shared a resource"
        GIG_PUBLISHED = "gig_published", "published a service"
        PROJECT_POSTED = "project_posted", "posted a project"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feed_items"
    )
    verb = models.CharField(max_length=32, choices=Verb.choices, db_index=True)
    summary = models.CharField(max_length=280)
    #: Where the entry points. Kept as a path rather than a generic foreign key:
    #: the feed only ever needs to link, and a GenericForeignKey would add a
    #: join per row to render a list.
    url = models.CharField(max_length=300, blank=True)
    community = models.ForeignKey(
        Community, null=True, blank=True, on_delete=models.CASCADE, related_name="feed_items"
    )

    class Meta(ScopedModel.Meta):
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["visibility", "university", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.actor_id} {self.verb}"

    @classmethod
    def record(cls, actor, verb: str, summary: str, *, url: str = "", community=None):
        """Append one entry on the surface the actor is currently acting in.

        Never raises into the caller. A feed is a convenience; failing to write
        one must not roll back the thing that actually happened.
        """
        import logging

        try:
            if community is not None:
                visibility, university_id = community.visibility, community.university_id
            elif actor.is_verified_student and actor.university_id:
                # Activity by a student inside their portal stays there.
                from core.scope import SurfaceKind, get_scope

                scope = get_scope()
                on_campus = scope is not None and scope.kind is SurfaceKind.UNIVERSITY
                visibility = Visibility.UNIVERSITY if on_campus else Visibility.GLOBAL
                university_id = actor.university_id if on_campus else None
            else:
                visibility, university_id = Visibility.GLOBAL, None

            return cls.objects.create(
                actor=actor,
                verb=verb,
                summary=summary[:280],
                url=url,
                community=community,
                visibility=visibility,
                university_id=university_id,
            )
        except Exception:
            logging.getLogger(__name__).exception("feed_write_failed verb=%s", verb)
            return None


# --- Moderation -------------------------------------------------------------


class Report(TimestampedModel):
    """A member flagging content for a moderator.

    One table for every reportable kind, keyed by a string rather than a
    generic foreign key: the queue is read by humans who need the link and the
    reason, and a `GenericForeignKey` would make the queue view a join per row
    for information a moderator does not use.
    """

    class Kind(models.TextChoices):
        THREAD = "thread", "Discussion"
        REPLY = "reply", "Reply"
        CHAT = "chat", "Chat message"
        RESOURCE = "resource", "Resource"
        COMMUNITY = "community", "Community"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        UPHELD = "upheld", "Upheld — content removed"
        DISMISSED = "dismissed", "Dismissed"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_made"
    )
    community = models.ForeignKey(
        Community, null=True, blank=True, on_delete=models.CASCADE, related_name="reports"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices)
    object_id = models.PositiveBigIntegerField()
    reason = models.TextField(validators=[MinLengthValidator(5)])

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]
        constraints = [
            # One open report per person per item. Without this a brigade can
            # bury the queue in a hundred copies of the same complaint.
            models.UniqueConstraint(
                fields=["reporter", "kind", "object_id"],
                condition=models.Q(status="open"),
                name="one_open_report_per_reporter_per_object",
            )
        ]

    def __str__(self) -> str:
        return f"{self.kind}:{self.object_id} ({self.status})"
