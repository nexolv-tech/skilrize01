"""
Push delivery via Firebase Cloud Messaging — Phase 7.

An adapter, in the shape this codebase has used four times now: `_scan_bytes`
for ClamAV (Phase 0), `challenges.grading` for Lighthouse (D33),
`integrations.providers.*` for Zoom/GitHub/etc (D36). `FCM_ENABLED` gates
whether any of it talks to Google at all, and is off by default — no Firebase
project has been created for this environment, so there are no service-account
credentials to load. Everything *around* the call is real regardless: token
fan-out, the dead-token taxonomy, error handling, and the pruning that keeps a
device list from filling with tokens that will never resolve again.

**Why `google-auth` rather than hand-rolled JWT signing.** FCM's HTTP v1 API
authenticates with an OAuth2 bearer token minted from a service-account
key — sign a JWT, exchange it, cache it until expiry, refresh it. The ClamAV
adapter deliberately speaks its protocol directly rather than taking a client
library, but that protocol is a length-prefixed byte stream and this one is
an asymmetric-crypto handshake with a refresh lifecycle. Google's own library
is the proportionate dependency here; the legacy FCM API that needed only a
static server key was shut down in 2024, so there is no simpler path left.
"""

from __future__ import annotations

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_TIMEOUT = 15


class PushUnavailable(Exception):
    """FCM is not configured in this environment. An expected state, not a
    fault — the caller records it and moves on, exactly as
    `challenges.grading.GradingUnavailable` is treated."""


class PushFailed(Exception):
    """FCM was configured and called, but the send failed for a reason that
    may not repeat — a 5xx, a timeout, a rate limit. Worth a retry."""


class PushTokenInvalid(Exception):
    """FCM says this token will never work again: the app was uninstalled,
    or the token was reissued. Distinct from `PushFailed` because the
    correct response is to stop sending to it, not to try harder."""


def is_enabled() -> bool:
    return bool(settings.FCM_ENABLED and settings.FCM_PROJECT_ID and settings.FCM_CREDENTIALS_JSON)


def _credentials():
    """Service-account credentials, refreshed on demand.

    Built per call rather than cached at import: the object holds a live
    access token with an expiry, and `google-auth` already caches and
    refreshes internally per instance. Sending is a background task, not a
    request path, so the handful of milliseconds is not worth a module-level
    singleton that would need its own thread-safety story.
    """
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    info = json.loads(settings.FCM_CREDENTIALS_JSON)
    credentials = service_account.Credentials.from_service_account_info(info, scopes=[_SCOPE])
    credentials.refresh(Request())
    return credentials


def send(*, token: str, title: str, body: str, data: dict | None = None) -> None:
    """Deliver one notification to one device token.

    Raises `PushUnavailable` when FCM is not configured, `PushTokenInvalid`
    when the token is permanently dead, and `PushFailed` for anything that
    might succeed on a retry.
    """
    if not is_enabled():
        raise PushUnavailable("FCM is not enabled in this environment.")

    import requests

    try:
        credentials = _credentials()
    except Exception as exc:  # malformed key, clock skew, network on refresh
        logger.warning("fcm_credentials_failed error=%s", exc)
        raise PushFailed(f"Could not obtain FCM credentials: {exc}") from exc

    # FCM requires every data value to be a string; anything structured has
    # to be serialised by us rather than by the client library.
    payload_data = {
        str(k): json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        for k, v in (data or {}).items()
    }

    try:
        response = requests.post(
            f"https://fcm.googleapis.com/v1/projects/{settings.FCM_PROJECT_ID}/messages:send",
            headers={"Authorization": f"Bearer {credentials.token}"},
            json={
                "message": {
                    "token": token,
                    "notification": {"title": title, "body": body},
                    "data": payload_data,
                }
            },
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise PushFailed(str(exc)) from exc

    if response.status_code == 200:
        return

    # 404 UNREGISTERED and 400 INVALID_ARGUMENT on the token field are FCM's
    # two ways of saying "this token is finished." Everything else — 401 on a
    # rotated key, 429, 503 — is transient from our side.
    if response.status_code in (400, 404):
        detail = response.text[:300]
        if response.status_code == 404 or "INVALID_ARGUMENT" in detail:
            raise PushTokenInvalid(detail)
        raise PushFailed(detail)

    raise PushFailed(f"FCM returned {response.status_code}: {response.text[:300]}")
