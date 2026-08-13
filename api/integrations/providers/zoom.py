"""
Zoom OAuth connect + meeting creation.

Gated behind `ZOOM_ENABLED` — off by default, mirroring `LIGHTHOUSE_ENABLED`
(D33): no Zoom OAuth app has been registered for this environment yet. Every
call below is a real Zoom API v2 call; the day `ZOOM_CLIENT_ID` /
`ZOOM_CLIENT_SECRET` are set, this starts working with zero further code
changes.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

import requests
from django.conf import settings

from .base import IntegrationError, IntegrationUnavailable, session

AUTHORIZE_URL = "https://zoom.us/oauth/authorize"
TOKEN_URL = "https://zoom.us/oauth/token"  # noqa: S105 — an API endpoint, not a credential
API_BASE = "https://api.zoom.us/v2"

_TIMEOUT = 15


def is_enabled() -> bool:
    return bool(settings.ZOOM_ENABLED and settings.ZOOM_CLIENT_ID and settings.ZOOM_CLIENT_SECRET)


def authorize_url(redirect_uri: str, state: str) -> str:
    if not is_enabled():
        raise IntegrationUnavailable("Zoom is not enabled in this environment.")
    params = {
        "response_type": "code",
        "client_id": settings.ZOOM_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str, redirect_uri: str) -> dict:
    """Returns `{"access_token", "refresh_token", "expires_in", "external_label"}`."""
    if not is_enabled():
        raise IntegrationUnavailable("Zoom is not enabled in this environment.")
    try:
        token_response = session.post(
            TOKEN_URL,
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
            auth=(settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET),
            timeout=_TIMEOUT,
        )
        token_response.raise_for_status()
        token = token_response.json()

        profile_response = session.get(
            f"{API_BASE}/users/me",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=_TIMEOUT,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
    except requests.RequestException as exc:
        raise IntegrationError(str(exc)) from exc

    return {
        "access_token": token["access_token"],
        "refresh_token": token.get("refresh_token", ""),
        "expires_in": token.get("expires_in"),
        "external_label": profile.get("email", ""),
    }


def create_meeting(
    *, access_token: str, topic: str, start_time: datetime, duration_minutes: int
) -> dict:
    """Returns `{"join_url", "external_id"}`."""
    if not is_enabled():
        raise IntegrationUnavailable("Zoom is not enabled in this environment.")
    try:
        response = session.post(
            f"{API_BASE}/users/me/meetings",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "topic": topic,
                "type": 2,  # scheduled meeting
                "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "duration": duration_minutes,
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise IntegrationError(str(exc)) from exc

    payload = response.json()
    return {"join_url": payload["join_url"], "external_id": str(payload["id"])}
