"""Shared adapter contract. Same shape as `challenges.grading` (D33): a
provider module exposes `is_enabled()`, `authorize_url()`, `exchange_code()`,
and either `create_meeting()` or `fetch_activity()` depending on which set it
belongs to (`integrations.models.MEETING_PROVIDERS` /
`ACTIVITY_PROVIDERS`)."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

#: Retries transient failures — connection resets, timeouts, and 429/5xx —
#: with exponential backoff, so one flaky moment on Zoom's or GitHub's side
#: does not surface as a user-facing error on the first try. Every provider
#: module shares this one session rather than calling `requests.get`/`.post`
#: directly (Phase 11, D37) — a fresh `requests.Session()` per call opened a
#: new TCP/TLS connection for every request and retried nothing.
_RETRY = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],
    raise_on_status=False,
)

session = requests.Session()
session.mount("https://", HTTPAdapter(max_retries=_RETRY))
session.mount("http://", HTTPAdapter(max_retries=_RETRY))


class IntegrationUnavailable(Exception):
    """The provider is not enabled in this environment (no client id/secret
    configured). Distinct from `IntegrationError`: this is an expected,
    environment-level state — never a crash, and callers should surface
    "not connected yet", not a 500."""


class IntegrationError(Exception):
    """The provider was enabled and called, but the call itself failed —
    a bad token, a rate limit, an unreachable API."""
