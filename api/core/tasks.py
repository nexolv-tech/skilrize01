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
