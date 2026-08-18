"""Background work. Nothing here is ever run inline with a web request."""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def scan_file(self, stored_file_id: int) -> str:
    """Antivirus scan. A file is not downloadable until this clears it.

    The scanner itself is an adapter: production points this at ClamAV (or the
    equivalent) over its daemon socket. What is implemented here is the
    surrounding contract — pending until proven clean, quarantined on a hit,
    retried on scanner failure — so that swapping the engine in is a
    configuration change and not a redesign of the upload path.
    """
    from .files import get_storage
    from .models import StoredFile

    record = StoredFile.objects.filter(pk=stored_file_id).first()
    if record is None:
        return "missing"

    try:
        data = get_storage().read(record.key)
    except Exception as exc:
        logger.warning("scan_failed file=%s error=%s", stored_file_id, exc)
        record.scan_status = StoredFile.ScanStatus.FAILED
        record.save(update_fields=["scan_status", "updated_at"])
        raise self.retry(exc=exc) from exc

    try:
        verdict = _scan_bytes(data)
    except Exception as exc:
        # The engine was unreachable or answered with something unusable. The
        # file stays quarantined and the task retries; it is never promoted to
        # clean because the scanner could not be asked.
        logger.warning("scan_engine_error file=%s error=%s", stored_file_id, exc)
        record.scan_status = StoredFile.ScanStatus.FAILED
        record.save(update_fields=["scan_status", "updated_at"])
        raise self.retry(exc=exc) from exc

    record.scan_status = verdict
    record.save(update_fields=["scan_status", "updated_at"])

    if verdict == StoredFile.ScanStatus.INFECTED:
        logging.getLogger("skilrize.security").error(
            "malicious_upload file=%s owner=%s", record.pk, record.owner_id
        )
    return verdict


#: EICAR's standard test string, split so this file does not itself trip a
#: scanner watching the source tree.
_EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR"


def _scan_bytes(data: bytes) -> str:
    """Return a scan verdict for ``data``.

    Points at ClamAV when ``CLAMAV_HOST`` is configured. When it is not, the
    behaviour deliberately differs by environment:

    * With ``REQUIRE_FILE_SCANNER`` off (local development), fall back to
      matching EICAR, so the quarantine path is exercised by the test suite
      rather than assumed to work on the day it first matters.
    * With it on, return ``FAILED``. An unscanned file staying un-downloadable
      is a visible, fixable outage; an unscanned file being served because
      nobody noticed the scanner was unset is a breach. This pipeline fails
      closed on purpose.
    """
    from .models import StoredFile

    host = getattr(settings, "CLAMAV_HOST", "")
    if host:
        return _scan_with_clamav(data, host, settings.CLAMAV_PORT)

    if settings.REQUIRE_FILE_SCANNER:
        logging.getLogger("skilrize.security").error(
            "scanner_not_configured: refusing to mark an upload clean without a scanner"
        )
        return StoredFile.ScanStatus.FAILED

    return StoredFile.ScanStatus.INFECTED if _EICAR in data[:1024] else StoredFile.ScanStatus.CLEAN


def _scan_with_clamav(data: bytes, host: str, port: int) -> str:
    """Scan one buffer over clamd's INSTREAM protocol.

    Spoken directly rather than through a client library: the protocol is a
    length-prefixed chunk stream and a one-line reply, and implementing it here
    is smaller than the dependency plus its transitive surface — which is the
    wrong thing to grow on the component that handles hostile input.
    """
    import socket
    import struct

    from .models import StoredFile

    chunk_size = 64 * 1024
    with socket.create_connection((host, port), timeout=settings.CLAMAV_TIMEOUT) as sock:
        sock.settimeout(settings.CLAMAV_TIMEOUT)
        sock.sendall(b"zINSTREAM\0")
        for start in range(0, len(data), chunk_size):
            chunk = data[start : start + chunk_size]
            sock.sendall(struct.pack("!L", len(chunk)) + chunk)
        # A zero-length chunk terminates the stream.
        sock.sendall(struct.pack("!L", 0))

        reply = b""
        while b"\0" not in reply:
            received = sock.recv(4096)
            if not received:
                break
            reply += received

    verdict = reply.rstrip(b"\0").decode("utf-8", "replace").strip()
    if verdict.endswith("OK"):
        return StoredFile.ScanStatus.CLEAN
    if verdict.endswith("FOUND"):
        logging.getLogger("skilrize.security").error("clamav_hit verdict=%s", verdict)
        return StoredFile.ScanStatus.INFECTED

    # A size limit, a broken stream, or an engine error. Not clean, and not
    # provably infected either — so it stays quarantined and gets retried.
    raise RuntimeError(f"clamav returned an unusable verdict: {verdict!r}")


@shared_task
def reindex_search() -> dict:
    """Rebuild every search vector.

    Belt and braces. Vectors are written on save, so this exists for the cases
    a save hook cannot cover: a bulk `update()`, a data migration, a restored
    backup. Cheap enough to run nightly and the only thing that makes "search
    is stale" a non-problem rather than a class of bug report.
    """
    from .indexing import reindex_all

    return reindex_all()


@shared_task
def refresh_reputation(limit: int = 500) -> int:
    """Recompute the oldest job success scores and seller levels."""
    from accounts.reputation import recompute_stale

    return recompute_stale(limit=limit)


@shared_task
def assess_review_integrity(limit: int = 500) -> int:
    """Work through unassessed reviews.

    Runs behind publication rather than inside it: a fraud check that blocks a
    review from appearing turns every false positive into a support ticket
    about a missing review, and every slow check into a stalled request.
    """
    from contracts.integrity import check_unassessed

    return check_unassessed(limit=limit)


@shared_task
def sweep_promotions() -> int:
    """Start, stop, and expire promoted placements. Runs every 5 minutes
    (`core/migrations/0004_seed_beat_schedule.py`)."""
    from discovery.models import expire_promotions

    return expire_promotions()


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def grade_challenge_submission(self, participation_id: int) -> str:
    """Run automated (Lighthouse) grading for one challenge submission.

    Not retried on `GradingUnavailable` or `GradingFailed` — neither is a
    transient error `bind`'s retry would fix. It is retried (implicitly, by
    Celery's own task-level acks) only on something unexpected raising past
    the two handled exceptions, same as `scan_file` above.
    """
    from challenges.grading import GradingFailed, GradingUnavailable, grade_url
    from challenges.models import Participation

    from .models import NotificationCategory
    from .notify import dispatch

    participation = (
        Participation.objects.filter(pk=participation_id)
        .select_related("challenge", "user")
        .first()
    )
    if participation is None:
        return "missing"

    try:
        result = grade_url(participation.submission_url)
    except GradingUnavailable as exc:
        logger.info(
            "challenge_grading_unavailable participation=%s reason=%s", participation_id, exc
        )
        participation.apply_automated_result(status=Participation.AutomatedStatus.UNAVAILABLE)
        return "unavailable"
    except GradingFailed as exc:
        logger.warning("challenge_grading_failed participation=%s error=%s", participation_id, exc)
        participation.apply_automated_result(status=Participation.AutomatedStatus.FAILED)
        return "failed"

    participation.apply_automated_result(
        status=Participation.AutomatedStatus.COMPLETE,
        score=result["score"],
        report=result["report"],
    )

    if participation.status == Participation.Status.GRADED:
        dispatch(
            participation.user,
            NotificationCategory.CHALLENGE,
            "Your submission was graded",
            f"{participation.challenge.title}: {participation.final_score}/100.",
            data={"challenge_slug": participation.challenge.slug},
        )
    return "graded"


@shared_task
def sweep_challenge_deadlines() -> dict:
    """Expire attempts nobody submitted in time, and finalize challenges whose
    submission window has closed — ranking every graded attempt and awarding
    badges. Runs every 15 minutes (`core/migrations/0004_seed_beat_schedule.py`)."""
    from challenges.models import Challenge, Participation, finalize_challenge

    from .models import NotificationCategory
    from .notify import dispatch

    expired = Participation.objects.filter(
        status=Participation.Status.IN_PROGRESS, deadline__lt=timezone.now()
    ).update(status=Participation.Status.EXPIRED, updated_at=timezone.now())

    finalized = 0
    badges_awarded = 0
    due = Challenge.objects.filter(status=Challenge.Status.PUBLISHED, closes_at__lt=timezone.now())
    for challenge in due:
        # Everyone's deadline is capped at closes_at, so once closes_at has
        # passed the bulk expire above has already cleared every straggler —
        # this is a belt-and-braces check, not the thing doing the work.
        if challenge.participations.filter(status=Participation.Status.IN_PROGRESS).exists():
            continue
        badges_awarded += finalize_challenge(challenge)
        finalized += 1
        for badge in challenge.badges.select_related("user"):
            dispatch(
                badge.user,
                NotificationCategory.CHALLENGE,
                f"You earned a badge: {badge.label}",
                f"{challenge.title} — {badge.final_score}/100.",
                data={"challenge_slug": challenge.slug, "badge_id": badge.id},
            )

    return {"expired": expired, "challenges_finalized": finalized, "badges_awarded": badges_awarded}


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def deliver_notification(self, notification_id: int, channel: str) -> str:
    """Send one notification on one channel, with retry."""
    from .models import Channel, Notification

    notification = Notification.objects.filter(pk=notification_id).select_related("user").first()
    if notification is None:
        return "missing"

    try:
        if channel == Channel.EMAIL:
            send_mail(
                subject=notification.title,
                message=notification.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.user.email],
                fail_silently=False,
            )
        elif channel == Channel.PUSH:
            return _deliver_push(notification)
        else:
            # SMS is connected in the phase that needs it; the queue contract
            # and retry behaviour are already correct.
            logger.info("notification_pending channel=%s notification=%s", channel, notification_id)
            return "pending_provider"
    except Exception as exc:
        raise self.retry(exc=exc) from exc

    return "sent"


def _deliver_push(notification) -> str:
    """Fan one notification out to every active device the user has — Phase 7.

    Returns a summary verdict rather than raising, for the same reason
    `grade_challenge_submission` (D33) does: "this environment has no FCM
    credentials" and "this user has no devices registered" are both ordinary
    states, not failures worth retrying five times with backoff.

    A `PushFailed` on one device does not abandon the rest: with several
    devices on one account, one transient failure should not cost the others
    their notification. Genuinely dead tokens are deactivated as they are
    found, which is the only thing that keeps a long-lived account's device
    list from silently accumulating tokens that can never resolve again.
    """
    from .models import PushDevice
    from .push import PushFailed, PushTokenInvalid, PushUnavailable
    from .push import send as send_push

    devices = list(PushDevice.objects.filter(user=notification.user, is_active=True))
    if not devices:
        return "no_devices"

    sent = 0
    failed = 0
    dead: list[int] = []
    for device in devices:
        try:
            send_push(
                token=device.token,
                title=notification.title,
                body=notification.body,
                data={**notification.data, "notification_id": notification.pk},
            )
            sent += 1
        except PushUnavailable:
            # Not configured here. Nothing to retry, and nothing is wrong.
            return "unavailable"
        except PushTokenInvalid:
            dead.append(device.pk)
        except PushFailed as exc:
            logger.warning("push_failed device=%s error=%s", device.pk, exc)
            failed += 1

    if dead:
        PushDevice.objects.filter(pk__in=dead).update(is_active=False, updated_at=timezone.now())
        logger.info("push_tokens_pruned count=%s user=%s", len(dead), notification.user_id)

    if sent:
        return "sent"
    if failed:
        return "failed"
    return "pruned"
