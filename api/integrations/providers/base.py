"""Shared adapter contract. Same shape as `challenges.grading` (D33): a
provider module exposes `is_enabled()`, `authorize_url()`, `exchange_code()`,
and either `create_meeting()` or `fetch_activity()` depending on which set it
belongs to (`integrations.models.MEETING_PROVIDERS` /
`ACTIVITY_PROVIDERS`)."""

from __future__ import annotations


class IntegrationUnavailable(Exception):
    """The provider is not enabled in this environment (no client id/secret
    configured). Distinct from `IntegrationError`: this is an expected,
    environment-level state — never a crash, and callers should surface
    "not connected yet", not a 500."""


class IntegrationError(Exception):
    """The provider was enabled and called, but the call itself failed —
    a bad token, a rate limit, an unreachable API."""
