"""Interim operations console for integrations — same status as the rest of
the admin app until Section 9's console replaces it (it hasn't, for this
corner; see D35 on what Phase 9 covered and what it didn't)."""

from django.contrib import admin

from .models import ActivityEvent, ActivityFeedSource, IntegrationConnection, Meeting


class ActivityEventInline(admin.TabularInline):
    model = ActivityEvent
    extra = 0
    fields = ["event_type", "summary", "actor_label", "occurred_at", "external_url"]
    readonly_fields = fields
    can_delete = False


@admin.register(IntegrationConnection)
class IntegrationConnectionAdmin(admin.ModelAdmin):
    list_display = ["user", "provider", "external_label", "expires_at", "created_at"]
    list_filter = ["provider"]
    search_fields = ["user__handle", "user__email", "external_label"]
    readonly_fields = ["access_token", "refresh_token"]


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ["topic", "contract", "provider", "start_time", "status", "scheduled_by"]
    list_filter = ["provider", "status"]
    search_fields = ["topic", "contract__title"]


@admin.register(ActivityFeedSource)
class ActivityFeedSourceAdmin(admin.ModelAdmin):
    list_display = ["contract", "provider", "external_ref", "added_by", "last_synced_at"]
    list_filter = ["provider"]
    search_fields = ["contract__title", "external_ref"]
    inlines = [ActivityEventInline]
