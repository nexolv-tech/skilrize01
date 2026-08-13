"""
Notion OAuth connect + a read-only edit signal for one page.

Gated behind `NOTION_ENABLED` — off by default, mirroring
`LIGHTHOUSE_ENABLED` (D33): no Notion integration has been registered for
this environment yet.

**Known limitation, stated plainly rather than papered over:** Notion's
public API has no per-edit activity log — that exists only in the Enterprise
plan's separate Audit Log API, which most workspaces this platform's clients
and freelancers actually have don't carry. What the public API does expose
is `last_edited_time` on the page object itself. `fetch_activity` therefore
returns at most a single synthetic "page was last edited at T" event per
call rather than a real timeline — an honest, coarser signal, not a full
feed. `external_ref` is the Notion page id.
"""

from __future__ import annotations

from urllib.parse import urlencode

import requests
from django.conf import settings

from .base import IntegrationError, IntegrationUnavailable, session

AUTHORIZE_URL = "https://api.notion.com/v1/oauth/authorize"
TOKEN_URL = "https://api.notion.com/v1/oauth/token"  # noqa: S105 — an API endpoint, not a credential
API_BASE = "https://api.notion.com/v1"
_API_VERSION = "2022-06-28"

_TIMEOUT = 15


def is_enabled() -> bool:
    return bool(
        settings.NOTION_ENABLED and settings.NOTION_CLIENT_ID and settings.NOTION_CLIENT_SECRET
    )


def authorize_url(redirect_uri: str, state: str) -> str:
    if not is_enabled():
        raise IntegrationUnavailable("Notion is not enabled in this environment.")
    params = {
        "client_id": settings.NOTION_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "owner": "user",
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str, redirect_uri: str) -> dict:
    if not is_enabled():
        raise IntegrationUnavailable("Notion is not enabled in this environment.")
    try:
        token_response = session.post(
            TOKEN_URL,
            json={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
            auth=(settings.NOTION_CLIENT_ID, settings.NOTION_CLIENT_SECRET),
            headers={"Notion-Version": _API_VERSION},
            timeout=_TIMEOUT,
        )
        token_response.raise_for_status()
        token = token_response.json()
    except requests.RequestException as exc:
        raise IntegrationError(str(exc)) from exc

    workspace = token.get("workspace_name", "")
    return {
        "access_token": token["access_token"],
        "refresh_token": "",  # Notion's internal-integration tokens do not expire
        "expires_in": None,
        "external_label": workspace,
    }


def fetch_activity(*, access_token: str, external_ref: str, since=None) -> list[dict]:
    """`external_ref` is a Notion page id. See module docstring for why this
    returns at most one event rather than a timeline."""
    if not is_enabled():
        raise IntegrationUnavailable("Notion is not enabled in this environment.")
    try:
        response = session.get(
            f"{API_BASE}/pages/{external_ref}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Notion-Version": _API_VERSION,
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise IntegrationError(str(exc)) from exc

    page = response.json()
    occurred_at = page.get("last_edited_time")
    if not occurred_at or (since and occurred_at <= since):
        return []

    editor = (page.get("last_edited_by") or {}).get("id", "")
    return [
        {
            "event_type": "PageEdited",
            "summary": "Page was last edited",
            "actor_label": editor,
            "occurred_at": occurred_at,
            "external_url": page.get("url", ""),
            "external_id": f"{external_ref}:{occurred_at}",
        }
    ]
