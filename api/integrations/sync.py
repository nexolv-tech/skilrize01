"""Shared activity-sync logic — called from both the manual "sync now"
endpoint and the periodic Celery task, so the two can never drift apart."""

from __future__ import annotations

from datetime import UTC

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import ActivityEvent, ActivityFeedSource, IntegrationConnection
from .providers import registry


def sync_source(source: ActivityFeedSource, connection: IntegrationConnection) -> int:
    """Fetch new activity for one source using one connection's token.

    Returns the number of new events stored. Raises `IntegrationUnavailable`
    / `IntegrationError` — same taxonomy as every other provider call;
    callers decide how to surface it (a 400 from the manual endpoint, a
    logged skip from the periodic sweep).
    """
    module = registry.get(source.provider)
    since = None
    if source.last_synced_at:
        # Match the "Z"-suffixed, no-microseconds shape every provider's own
        # timestamps use, so the >= comparison each adapter does is a true
        # chronological comparison rather than an accidental string one.
        since = source.last_synced_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    events = module.fetch_activity(
        access_token=connection.access_token, external_ref=source.external_ref, since=since
    )

    created = 0
    for item in events:
        occurred_at = parse_datetime(item["occurred_at"]) if item.get("occurred_at") else None
        if occurred_at is None:
            continue
        _, was_created = ActivityEvent.objects.get_or_create(
            source=source,
            external_id=item["external_id"],
            defaults={
                "event_type": item["event_type"],
                "summary": item["summary"],
                "actor_label": item.get("actor_label", ""),
                "occurred_at": occurred_at,
                "external_url": item.get("external_url", ""),
            },
        )
        created += int(was_created)

    source.last_synced_at = timezone.now()
    source.save(update_fields=["last_synced_at", "updated_at"])
    return created
