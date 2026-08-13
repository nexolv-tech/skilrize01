"""Background work for integrations — Phase 10."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def sweep_activity_sources() -> dict:
    """Sync every activity source whose contract has at least one party with
    a live connection for its provider.

    Not yet wired to a schedule — the same gap `core.tasks.sweep_promotions`
    and `sweep_challenge_deadlines` already carry (no `CELERY_BEAT_SCHEDULE`
    exists in this codebase yet; see the module docstrings there). Until that
    infrastructure work happens, a source gets fresh data from the "sync now"
    action (`activity-sources/<id>/sync/`) or by invoking this task directly.
    """
    from .models import ActivityFeedSource, IntegrationConnection
    from .providers.base import IntegrationError, IntegrationUnavailable
    from .sync import sync_source

    synced = 0
    skipped = 0
    failed = 0
    for source in ActivityFeedSource.objects.select_related("contract").all():
        connection = (
            IntegrationConnection.objects.filter(
                provider=source.provider,
                user_id__in=[source.contract.client_id, source.contract.freelancer_id],
            )
            .order_by("-updated_at")
            .first()
        )
        if connection is None:
            skipped += 1
            continue
        try:
            sync_source(source, connection)
            synced += 1
        except IntegrationUnavailable:
            skipped += 1
        except IntegrationError as exc:
            logger.warning("activity_sync_failed source=%s error=%s", source.id, exc)
            failed += 1

    return {"synced": synced, "skipped": skipped, "failed": failed}
