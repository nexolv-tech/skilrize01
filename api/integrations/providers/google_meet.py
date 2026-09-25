"""
Google Meet, via the Calendar API's `conferenceData` request — Google has no
standalone "create a Meet link" endpoint; a Meet link is a side effect of
creating a calendar event with a conference request attached.

Gated behind `GOOGLE_MEET_ENABLED` — off by default, mirroring
`LIGHTHOUSE_ENABLED` (D33): no Google Cloud OAuth client has been registered
for this environment yet.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings

from .base import IntegrationError, IntegrationUnavailable, session

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 — an API endpoint, not a credential
CALENDAR_API = "https://www.googleapis.com/calendar/v3"
USERINFO_API = "https://www.googleapis.com/oauth2/v2/userinfo"

_SCOPES = (
    "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/userinfo.email"
)
_TIMEOUT = 15


def is_enabled() -> bool:
    return bool(
        settings.GOOGLE_MEET_ENABLED and settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET
    )


def authorize_url(redirect_uri: str, state: str) -> str:
    if not is_enabled():
        raise IntegrationUnavailable("Google Meet is not enabled in this environment.")
    params = {
        "response_type": "code",
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": _SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str, redirect_uri: str) -> dict:
    if not is_enabled():
        raise IntegrationUnavailable("Google Meet is not enabled in this environment.")
    try:
        token_response = session.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
            },
            timeout=_TIMEOUT,
        )
        token_response.raise_for_status()
        token = token_response.json()

        profile_response = session.get(
            USERINFO_API,
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


def refresh(refresh_token: str) -> dict:
    """A new access token (they last an hour). Google keeps the refresh token
    it issued at consent, so none comes back."""
    if not is_enabled():
        raise IntegrationUnavailable("Google Meet is not enabled in this environment.")
    try:
        response = session.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        token = response.json()
    except requests.RequestException as exc:
        raise IntegrationError(str(exc)) from exc
    return {"access_token": token["access_token"], "expires_in": token.get("expires_in")}


def create_meeting(
    *, access_token: str, topic: str, start_time: datetime, duration_minutes: int
) -> dict:
    if not is_enabled():
        raise IntegrationUnavailable("Google Meet is not enabled in this environment.")
    end_time = start_time + timedelta(minutes=duration_minutes)
    request_id = uuid.uuid4().hex
    try:
        response = session.post(
            f"{CALENDAR_API}/calendars/primary/events",
            params={"conferenceDataVersion": 1},
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "summary": topic,
                "start": {"dateTime": start_time.isoformat()},
                "end": {"dateTime": end_time.isoformat()},
                "conferenceData": {
                    "createRequest": {
                        "requestId": request_id,
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                },
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise IntegrationError(str(exc)) from exc

    payload = response.json()
    join_url = payload.get("hangoutLink", "")
    return {"join_url": join_url, "external_id": str(payload.get("id", ""))}
