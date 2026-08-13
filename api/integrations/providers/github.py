"""
GitHub OAuth connect + read-only repo activity.

Gated behind `GITHUB_ENABLED` — off by default, mirroring
`LIGHTHOUSE_ENABLED` (D33): no GitHub OAuth app has been registered for this
environment yet.

`fetch_activity` reads the repo's public events timeline
(`GET /repos/{owner}/{repo}/events`) — pushes, PR opens, issue comments —
which is exactly what shows up on the repo's own Activity tab. Nothing here
requests write scopes; the OAuth request below asks for `repo` read access
only insofar as GitHub's scope model allows narrowing it, and no write call
is ever made.
"""

from __future__ import annotations

from urllib.parse import urlencode

import requests
from django.conf import settings

from .base import IntegrationError, IntegrationUnavailable

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105 — an API endpoint, not a credential
API_BASE = "https://api.github.com"

_TIMEOUT = 15

#: GitHub's own vocabulary for the handful of event types worth surfacing —
#: everything else (WatchEvent, ForkEvent, ...) is noise for a client trying
#: to see "is this contract's work actually moving."
_EVENT_LABELS = {
    "PushEvent": "pushed commits",
    "PullRequestEvent": "opened/updated a pull request",
    "IssuesEvent": "opened/updated an issue",
    "IssueCommentEvent": "commented",
    "PullRequestReviewEvent": "reviewed a pull request",
    "ReleaseEvent": "published a release",
}


def is_enabled() -> bool:
    return bool(
        settings.GITHUB_ENABLED and settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET
    )


def authorize_url(redirect_uri: str, state: str) -> str:
    if not is_enabled():
        raise IntegrationUnavailable("GitHub is not enabled in this environment.")
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "repo:status read:user",
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str, redirect_uri: str) -> dict:
    if not is_enabled():
        raise IntegrationUnavailable("GitHub is not enabled in this environment.")
    try:
        token_response = requests.post(
            TOKEN_URL,
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
            timeout=_TIMEOUT,
        )
        token_response.raise_for_status()
        token = token_response.json()
        if "error" in token:
            raise IntegrationError(token.get("error_description", token["error"]))

        profile_response = requests.get(
            f"{API_BASE}/user",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=_TIMEOUT,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
    except requests.RequestException as exc:
        raise IntegrationError(str(exc)) from exc

    return {
        "access_token": token["access_token"],
        "refresh_token": "",  # GitHub OAuth apps issue non-expiring tokens by default
        "expires_in": None,
        "external_label": profile.get("login", ""),
    }


def fetch_activity(*, access_token: str, external_ref: str, since=None) -> list[dict]:
    """`external_ref` is `owner/repo`. Returns a list of
    `{"event_type", "summary", "actor_label", "occurred_at", "external_url", "external_id"}`,
    newest first."""
    if not is_enabled():
        raise IntegrationUnavailable("GitHub is not enabled in this environment.")
    try:
        response = requests.get(
            f"{API_BASE}/repos/{external_ref}/events",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"per_page": 30},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise IntegrationError(str(exc)) from exc

    events = []
    for item in response.json():
        occurred_at = item.get("created_at")
        if since and occurred_at and occurred_at <= since:
            continue
        actor = (item.get("actor") or {}).get("login", "")
        label = _EVENT_LABELS.get(item["type"], item["type"])
        events.append(
            {
                "event_type": item["type"],
                "summary": f"{actor} {label}".strip(),
                "actor_label": actor,
                "occurred_at": occurred_at,
                "external_url": f"https://github.com/{external_ref}",
                "external_id": item["id"],
            }
        )
    return events
