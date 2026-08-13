"""
Figma OAuth connect + read-only file version history.

Gated behind `FIGMA_ENABLED` — off by default, mirroring
`LIGHTHOUSE_ENABLED` (D33): no Figma OAuth app has been registered for this
environment yet.

Figma has no generic "activity feed" endpoint; the closest read-only signal
that maps to "is this file actually moving" is its version history
(`GET /v1/files/{key}/versions`) — one entry per named/autosaved version,
each with who saved it and when. `external_ref` is the file key from a
Figma file URL (`figma.com/file/<key>/...`).
"""

from __future__ import annotations

from urllib.parse import urlencode

import requests
from django.conf import settings

from .base import IntegrationError, IntegrationUnavailable

AUTHORIZE_URL = "https://www.figma.com/oauth"
TOKEN_URL = "https://api.figma.com/v1/oauth/token"  # noqa: S105 — an API endpoint, not a credential
API_BASE = "https://api.figma.com/v1"

_TIMEOUT = 15


def is_enabled() -> bool:
    return bool(
        settings.FIGMA_ENABLED and settings.FIGMA_CLIENT_ID and settings.FIGMA_CLIENT_SECRET
    )


def authorize_url(redirect_uri: str, state: str) -> str:
    if not is_enabled():
        raise IntegrationUnavailable("Figma is not enabled in this environment.")
    params = {
        "client_id": settings.FIGMA_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "file_read",
        "state": state,
        "response_type": "code",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str, redirect_uri: str) -> dict:
    if not is_enabled():
        raise IntegrationUnavailable("Figma is not enabled in this environment.")
    try:
        token_response = requests.post(
            TOKEN_URL,
            data={
                "client_id": settings.FIGMA_CLIENT_ID,
                "client_secret": settings.FIGMA_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "code": code,
                "grant_type": "authorization_code",
            },
            timeout=_TIMEOUT,
        )
        token_response.raise_for_status()
        token = token_response.json()
    except requests.RequestException as exc:
        raise IntegrationError(str(exc)) from exc

    return {
        "access_token": token["access_token"],
        "refresh_token": token.get("refresh_token", ""),
        "expires_in": token.get("expires_in"),
        "external_label": "",  # Figma's OAuth response carries no profile fields
    }


def fetch_activity(*, access_token: str, external_ref: str, since=None) -> list[dict]:
    """`external_ref` is a Figma file key. Returns a list of
    `{"event_type", "summary", "actor_label", "occurred_at", "external_url", "external_id"}`,
    newest first."""
    if not is_enabled():
        raise IntegrationUnavailable("Figma is not enabled in this environment.")
    try:
        response = requests.get(
            f"{API_BASE}/files/{external_ref}/versions",
            headers={"X-Figma-Token": access_token}
            if access_token.startswith("figd_")
            else {"Authorization": f"Bearer {access_token}"},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise IntegrationError(str(exc)) from exc

    events = []
    for item in response.json().get("versions", []):
        occurred_at = item.get("created_at")
        if since and occurred_at and occurred_at <= since:
            continue
        user = (item.get("user") or {}).get("handle", "")
        label = item.get("label") or "saved a version"
        events.append(
            {
                "event_type": "FileVersion",
                "summary": f"{user}: {label}".strip(": "),
                "actor_label": user,
                "occurred_at": occurred_at,
                "external_url": f"https://www.figma.com/file/{external_ref}",
                "external_id": str(item["id"]),
            }
        )
    return events
