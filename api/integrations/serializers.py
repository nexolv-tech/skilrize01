"""Shapes for the integrations API."""

from __future__ import annotations

from rest_framework import serializers

from .models import ActivityEvent, ActivityFeedSource, IntegrationConnection, Meeting


class ConnectionSerializer(serializers.ModelSerializer):
    """Read shape for the caller's own connections. Tokens never appear here —
    only enough to render a connect/disconnect toggle."""

    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = IntegrationConnection
        fields = ["id", "provider", "external_label", "expires_at", "is_expired", "created_at"]
        read_only_fields = fields


class MeetingSerializer(serializers.ModelSerializer):
    scheduled_by_handle = serializers.CharField(source="scheduled_by.handle", read_only=True)

    class Meta:
        model = Meeting
        fields = [
            "id",
            "contract",
            "provider",
            "topic",
            "start_time",
            "duration_minutes",
            "join_url",
            "status",
            "scheduled_by",
            "scheduled_by_handle",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "join_url",
            "status",
            "scheduled_by",
            "scheduled_by_handle",
            "created_at",
        ]


class ScheduleMeetingInputSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["zoom", "google_meet"])
    topic = serializers.CharField(max_length=200)
    start_time = serializers.DateTimeField()
    duration_minutes = serializers.IntegerField(min_value=5, max_value=480, default=30)


class ActivityEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityEvent
        fields = ["id", "event_type", "summary", "actor_label", "occurred_at", "external_url"]
        read_only_fields = fields


class ActivitySourceSerializer(serializers.ModelSerializer):
    added_by_handle = serializers.CharField(source="added_by.handle", read_only=True)
    recent_events = serializers.SerializerMethodField()

    class Meta:
        model = ActivityFeedSource
        fields = [
            "id",
            "contract",
            "provider",
            "external_ref",
            "added_by",
            "added_by_handle",
            "last_synced_at",
            "recent_events",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "added_by",
            "added_by_handle",
            "last_synced_at",
            "recent_events",
            "created_at",
        ]

    def get_recent_events(self, obj: ActivityFeedSource) -> list:
        events = getattr(obj, "prefetched_events", None)
        if events is None:
            events = list(obj.events.all()[:20])
        return ActivityEventSerializer(events[:20], many=True).data


class AddActivitySourceInputSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["github", "figma", "notion"])
    external_ref = serializers.CharField(max_length=300)
