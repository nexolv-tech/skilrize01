"""
Notification dispatch.

Section 24 in one function: every notification is written to the in-app centre,
fanned out to the channels the user actually wants, queued rather than sent
inline with a web request, and — for security, payment, and dispute events —
delivered regardless of preferences or quiet hours.
"""

from __future__ import annotations

from .models import (
    UNMUTABLE_CATEGORIES,
    Channel,
    Notification,
    NotificationPreference,
)


def preferences_for(user) -> NotificationPreference:
    preference, _ = NotificationPreference.objects.get_or_create(user=user)
    return preference


def dispatch(
    user,
    category: str,
    title: str,
    body: str = "",
    *,
    data: dict | None = None,
    channels: list[str] | None = None,
) -> Notification:
    """Record a notification and queue delivery on every permitted channel."""
    from .tasks import deliver_notification

    notification = Notification.objects.create(
        user=user, category=category, title=title, body=body, data=data or {}
    )

    preference = preferences_for(user)
    quiet = preference.in_quiet_hours() and category not in UNMUTABLE_CATEGORIES

    for channel in channels or [Channel.EMAIL, Channel.PUSH, Channel.SMS]:
        if channel == Channel.IN_APP:
            continue  # Already delivered by creating the row above.
        if not preference.allows(category, channel):
            continue
        if quiet:
            # Held for the next digest rather than dropped.
            continue
        deliver_notification.delay(notification.pk, str(channel))

    return notification
