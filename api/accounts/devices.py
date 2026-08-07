"""
New-device recognition and the transaction cool-off that follows it.

The flow, in one place so it cannot drift between the login view and the 2FA
view:

  1. Every successful authentication is attributed to a device fingerprint.
  2. A fingerprint we have not seen for this account creates a `KnownDevice`
     whose `trusted_at` is `DEVICE_COOLOFF_SECONDS` in the future, and fires an
     alert email.
  3. Until `trusted_at` passes, `CanTransact` refuses anything money-adjacent
     while leaving the rest of the platform fully usable.

Why a hold rather than a block: signing in from a new laptop is ordinary and
blocking it would be hostile, but a password used from an unseen device is also
exactly what a freshly phished credential looks like. The hold costs a real
user nothing they notice and costs a thief the only thing they came for.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from core.models import client_ip

from .models import KnownDevice

security_log = logging.getLogger("skilrize.security")


def fingerprint(request) -> str:
    """A stable, keyed identifier for the calling device.

    Keyed with `SECRET_KEY` so the stored value is not a plain user-agent
    string — the device table should not double as a browsing-habits dataset if
    the database is ever read by someone who should not have it.
    """
    if request is None:
        return ""
    agent = request.META.get("HTTP_USER_AGENT", "")
    # The address is deliberately *not* part of this. Mobile networks re-assign
    # addresses constantly, and including it would fire an alert every time a
    # user walked out of wifi range — which trains people to ignore the alert.
    return hmac.new(settings.SECRET_KEY.encode(), agent.encode(), hashlib.sha256).hexdigest()


def register(user, request) -> tuple[KnownDevice | None, bool]:
    """Record this sign-in against a device. Returns ``(device, is_new)``."""
    value = fingerprint(request)
    if not value:
        return None, False

    now = timezone.now()
    device, created = KnownDevice.objects.get_or_create(
        user=user,
        fingerprint=value,
        defaults={
            "label": request.META.get("HTTP_USER_AGENT", "")[:120],
            "first_ip": client_ip(request),
            "trusted_at": now + timedelta(seconds=settings.DEVICE_COOLOFF_SECONDS),
            "last_seen_at": now,
        },
    )

    if not created:
        device.last_seen_at = now
        device.save(update_fields=["last_seen_at", "updated_at"])
        return device, False

    security_log.info(
        "new_device user=%s ip=%s trusted_at=%s", user.pk, client_ip(request), device.trusted_at
    )
    return device, True


def current(user, request) -> KnownDevice | None:
    """The `KnownDevice` this request is coming from, if it is recorded."""
    value = fingerprint(request)
    if not value:
        return None
    return KnownDevice.objects.filter(user=user, fingerprint=value).first()


def cooloff_remaining(user, request) -> int:
    """Seconds before this device may transact. 0 when it already may.

    An unrecognised device — one that never went through `register`, which in
    practice means a bearer-token client that skipped the login endpoint — is
    treated as untrusted for the full window rather than waved through. Failing
    open here would make the whole control optional.
    """
    device = current(user, request)
    if device is None:
        return settings.DEVICE_COOLOFF_SECONDS
    return device.seconds_until_trusted


def send_new_device_alert(user, request, device: KnownDevice) -> None:
    """Tell the account owner, on every channel they have enabled.

    Routed through the notification framework rather than `send_mail` so it
    obeys the user's channel preferences and is queued rather than sent inline
    with the login request — a slow mail server must never slow down a sign-in.
    """
    from core.models import NotificationCategory
    from core.notify import dispatch

    when = timezone.localtime(device.created_at).strftime("%d %b %Y at %H:%M")
    ip = device.first_ip or "an unknown address"

    dispatch(
        user,
        category=NotificationCategory.SECURITY,
        title="New sign-in to your SkilRize account",
        body=(
            f"Your account was signed in from a device we have not seen before, "
            f"on {when} from {ip}.\n\n"
            f"If this was you, nothing further is needed — transactions unlock "
            f"automatically about "
            f"{max(1, settings.DEVICE_COOLOFF_SECONDS // 3600)} hour(s) after sign-in.\n\n"
            f"If it was not you, change your password immediately and sign out "
            f"every other device from Settings → Security. Until then this "
            f"device cannot post projects, submit proposals, purchase, or move "
            f"any money."
        ),
        data={
            "kind": "new_device",
            "device_id": device.pk,
            "ip": device.first_ip or "",
            "trusted_at": device.trusted_at.isoformat(),
            "url": "/settings/security",
        },
    )
