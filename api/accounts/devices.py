"""
New-device recognition and the transaction cool-off that follows it.

The flow, in one place so it cannot drift between the login view and the 2FA
view:

  1. Every successful authentication is attributed to a device fingerprint.
  2. A fingerprint we have not seen for this account creates a `KnownDevice`
     whose `trusted_at` is `DEVICE_COOLOFF_SECONDS` in the future, and fires an
     alert email. The device an account is created on is trusted at once:
     a brand-new account has nothing to steal yet.
  3. Until `trusted_at` passes, `CanTransact` refuses anything money-adjacent
     while leaving the rest of the platform fully usable.

What a "device" is: a random id the device keeps. A browser holds it in a
long-lived HttpOnly cookie set at sign-in; the app keeps it in the phone's
secure storage and sends it as `X-Skilrize-Device`. Before D52 the
fingerprint was the user agent, which every browser update changes (a
routine Chrome update looked like a new device, email code and hold
included) and which every copy of the same browser shares. Devices recorded
that way are still recognised by their user agent once, then re-keyed to the
id on that sign-in.

Why a hold rather than a block: signing in from a new laptop is ordinary and
blocking it would be hostile, but a password used from an unseen device is also
exactly what a freshly phished credential looks like. The hold costs a real
user nothing they notice and costs a thief the only thing they came for.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from core.models import client_ip

from .models import KnownDevice

security_log = logging.getLogger("skilrize.security")


DEVICE_COOKIE = "skilrize_device"
DEVICE_HEADER = "HTTP_X_SKILRIZE_DEVICE"
#: Browsers cap a cookie's lifetime at 400 days; each sign-in renews it.
DEVICE_COOKIE_MAX_AGE = 400 * 24 * 3600
_DEVICE_ID = re.compile(r"^[A-Za-z0-9_-]{32,64}$")
#: Where `issue_device_id` leaves a freshly minted id for the rest of the
#: request, before any cookie carrying it exists.
_MINTED = "_skilrize_device_id"


def _keyed(value: str) -> str:
    """Keyed with `SECRET_KEY`, so the stored value is neither the id itself
    (a database reader could not replay it) nor a plain user-agent string
    (the device table does not double as a browsing-habits dataset)."""
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def device_id(request) -> str:
    """The id the calling device presented, or "" when it has none."""
    if request is None:
        return ""
    value = (
        getattr(request, _MINTED, "")
        or request.META.get(DEVICE_HEADER, "")
        or request.COOKIES.get(DEVICE_COOKIE, "")
    )
    return value if _DEVICE_ID.match(value) else ""


def _agent_fingerprint(request) -> str:
    # The address is deliberately *not* part of this. Mobile networks re-assign
    # addresses constantly, and including it would fire an alert every time a
    # user walked out of wifi range, which trains people to ignore the alert.
    return _keyed(request.META.get("HTTP_USER_AGENT", ""))


def fingerprint(request) -> str:
    """A stable, keyed identifier for the calling device: its id when it has
    one, else its user agent (an app too old to send the header)."""
    if request is None:
        return ""
    value = device_id(request)
    return _keyed(f"device:{value}") if value else _agent_fingerprint(request)


def issue_device_id(request) -> str:
    """The device's id, minting one for a browser that has none yet.

    Called just before a sign-in is recorded, so a new device row is keyed by
    the id from the start; `set_device_cookie` then hands it to the browser.
    The app always sends its own.
    """
    value = device_id(request)
    if not value:
        value = secrets.token_urlsafe(32)
        setattr(request, _MINTED, value)
    return value


def set_device_cookie(response, value: str):
    response.set_cookie(
        DEVICE_COOKIE,
        value,
        max_age=DEVICE_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    return response


def register(user, request, *, trusted: bool = False) -> tuple[KnownDevice | None, bool]:
    """Record this sign-in against a device. Returns ``(device, is_new)``.

    ``trusted`` skips the cool-off: used for the device an account is created
    on, which has no history to protect yet.
    """
    value = fingerprint(request)
    if not value:
        return None, False

    now = timezone.now()
    device = current(user, request)
    if device is not None:
        fields = ["last_seen_at", "updated_at"]
        device.last_seen_at = now
        if device.fingerprint != value:
            # Recognised by its user agent from before device ids. From now on
            # it is known by its id, so the next browser update changes nothing.
            device.fingerprint = value
            fields.append("fingerprint")
        device.save(update_fields=fields)
        return device, False

    device = KnownDevice.objects.create(
        user=user,
        fingerprint=value,
        label=request.META.get("HTTP_USER_AGENT", "")[:120],
        first_ip=client_ip(request),
        trusted_at=now if trusted else now + timedelta(seconds=settings.DEVICE_COOLOFF_SECONDS),
        last_seen_at=now,
    )
    security_log.info(
        "new_device user=%s ip=%s trusted_at=%s", user.pk, client_ip(request), device.trusted_at
    )
    return device, True


def current(user, request) -> KnownDevice | None:
    """The `KnownDevice` this request is coming from, if it is recorded."""
    value = fingerprint(request)
    if not value:
        return None
    device = KnownDevice.objects.filter(user=user, fingerprint=value).first()
    if device is None and device_id(request):
        # A device recorded before ids existed is still keyed by its agent.
        device = KnownDevice.objects.filter(
            user=user, fingerprint=_agent_fingerprint(request)
        ).first()
    return device


def remember(user, request, response) -> None:
    """Give a browser signed in before device ids existed its id.

    Its session outlives the switch, and without an id the next browser
    update would turn it into an unknown device in the middle of that
    session. Only a browser whose agent still matches a device on record is
    given one; anything else waits for its next sign-in.
    """
    if device_id(request) or request.META.get("HTTP_X_SKILRIZE_CLIENT"):
        return
    device = current(user, request)
    if device is None:
        return
    value = issue_device_id(request)
    device.fingerprint = fingerprint(request)
    device.save(update_fields=["fingerprint", "updated_at"])
    set_device_cookie(response, value)


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


def _duration(seconds: int) -> str:
    """`1800` -> "30 minutes", `7200` -> "2 hours", `5400` -> "1 hour 30 minutes"."""
    hours, minutes = divmod(max(60, seconds) // 60, 60)
    parts = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return " ".join(parts)


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
            f"automatically {_duration(settings.DEVICE_COOLOFF_SECONDS)} after sign-in.\n\n"
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
