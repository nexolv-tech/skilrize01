"""
Interim moderation console for the community layer.

Every list here is registered against `all_objects` rather than the scoped
manager: an operator answering a report needs to see content on whichever
surface it lives on, and the scoped manager would refuse to run at all outside
a request. Reaching across surfaces is exactly what `unscoped` is for, and the
audit log records who looked.
"""

from django.contrib import admin

from .models import (
    ChatMessage,
    Community,
    Conversation,
    Event,
    EventRSVP,
    FeedItem,
    Membership,
    Reply,
    Report,
    Resource,
    Thread,
)


class ScopedAdmin(admin.ModelAdmin):
    """Base for scopeable models, so admin never runs into `ScopeNotSet`."""

    def get_queryset(self, request):
        return self.model.all_objects.all()


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Community)
class CommunityAdmin(ScopedAdmin):
    list_display = [
        "name",
        "kind",
        "visibility",
        "university",
        "member_count",
        "thread_count",
        "is_archived",
    ]
    list_filter = ["kind", "visibility", "is_archived", "university"]
    search_fields = ["name", "slug", "tagline"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [MembershipInline]
    actions = ["archive_selected"]

    @admin.action(description="Archive — hides it and stops new posts")
    def archive_selected(self, request, queryset):
        # Archive rather than delete: deleting cascades to every thread, event,
        # and resource inside, which is almost never what a moderator means.
        updated = queryset.update(is_archived=True)
        self.message_user(request, f"{updated} community(ies) archived.")


@admin.register(Thread)
class ThreadAdmin(ScopedAdmin):
    list_display = [
        "title",
        "community",
        "author",
        "reply_count",
        "is_pinned",
        "is_locked",
        "created_at",
    ]
    list_filter = ["is_pinned", "is_locked", "visibility"]
    search_fields = ["title", "body", "author__email"]


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ["__str__", "thread", "author", "depth", "is_deleted", "created_at"]
    list_filter = ["is_deleted"]
    search_fields = ["body", "author__email"]


@admin.register(ChatMessage)
class ChatMessageAdmin(ScopedAdmin):
    list_display = ["__str__", "community", "author", "is_deleted", "created_at"]
    list_filter = ["is_deleted", "visibility"]
    search_fields = ["body", "author__email"]


@admin.register(Event)
class EventAdmin(ScopedAdmin):
    list_display = ["title", "community", "starts_at", "going_count", "capacity", "is_cancelled"]
    list_filter = ["is_cancelled", "visibility", "starts_at"]
    search_fields = ["title", "description"]


@admin.register(EventRSVP)
class EventRSVPAdmin(admin.ModelAdmin):
    list_display = ["event", "user", "status"]
    list_filter = ["status"]


@admin.register(Resource)
class ResourceAdmin(ScopedAdmin):
    list_display = ["title", "community", "kind", "uploaded_by", "download_count", "created_at"]
    list_filter = ["kind", "visibility"]
    search_fields = ["title", "description"]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """The escalation queue — reports a community moderator did not resolve."""

    list_display = ["kind", "object_id", "community", "reporter", "status", "created_at"]
    list_filter = ["status", "kind", "community"]
    search_fields = ["reason", "reporter__email"]
    readonly_fields = ["reporter", "kind", "object_id", "community", "reason", "created_at"]


@admin.register(FeedItem)
class FeedItemAdmin(ScopedAdmin):
    list_display = ["actor", "verb", "summary", "visibility", "university", "created_at"]
    list_filter = ["verb", "visibility"]
    search_fields = ["summary"]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Listed, never read.

    Private messages between two users are not admin's to browse. The list
    exists so support can confirm a conversation exists and when it was last
    active; the bodies stay out of the console entirely.
    """

    list_display = ["id", "participant_list", "last_message_at"]
    readonly_fields = ["participants", "last_message_at"]

    @admin.display(description="Between")
    def participant_list(self, obj: Conversation) -> str:
        return ", ".join(user.email for user in obj.participants.all())

    def has_view_permission(self, request, obj=None) -> bool:
        # Deliberately blocks the detail page, which would render messages.
        return obj is None and super().has_view_permission(request, obj)


# `DirectMessage` is intentionally not registered. Private correspondence
# between two users has no legitimate admin browsing case, and the surest way
# to keep it out of the console is to give the console no page for it. Lawful
# disclosure goes through an explicit, audited export, not a list view.
