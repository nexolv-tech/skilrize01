"""Background work. Nothing here is ever run inline with a web request."""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

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

    verdict = _scan_bytes(data)
    record.scan_status = verdict
    record.save(update_fields=["scan_status", "updated_at"])

    if verdict == StoredFile.ScanStatus.INFECTED:
        logging.getLogger("skilrize.security").error(
            "malicious_upload file=%s owner=%s", record.pk, record.owner_id
        )
    return verdict


def _scan_bytes(data: bytes) -> str:
    """Return a scan verdict for ``data``.

    Replace the body with a call to the real engine. The EICAR check is here so
    the quarantine path is exercised by the test suite rather than assumed to
    work on the day it first matters.
    """
    from .models import StoredFile

    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR"
    if eicar in data[:1024]:
        return StoredFile.ScanStatus.INFECTED
    return StoredFile.ScanStatus.CLEAN


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
        else:
            # Push and SMS providers are connected in the phase that needs
            # them; the queue contract and retry behaviour are already correct.
            logger.info("notification_pending channel=%s notification=%s", channel, notification_id)
            return "pending_provider"
    except Exception as exc:
        raise self.retry(exc=exc) from exc

    return "sent"
