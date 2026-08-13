"""Background work for integrations — Phase 10."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def sweep_activity_sources() -> dict:
    """Sync every activity source whose contract has at least one party with
    a live connection for its provider.

    Runs every 30 minutes (`core/migrations/0004_seed_beat_schedule.py`,
    Phase 11 / D37). A source can also get fresh data sooner from the
    "sync now" action (`activity-sources/<id>/sync/`).

    Deliberately not `@shared_task(bind=True, max_retries=N)` like
    `scan_file`/`deliver_notification`/`grade_challenge_submission` — those
    each act on one row, so retrying the whole task is retrying the one
    thing that failed. This task acts on every source in one pass; retrying
    the *task* on one source's failure would re-sync every source that
    already succeeded, for no benefit. What actually matters —
    transient network failures on the one HTTP call each sync makes — is
    handled a layer down, by `integrations.providers.base.session`'s retry
    adapter, which is where the retry belongs.
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
