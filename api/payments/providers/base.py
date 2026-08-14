"""Shared retrying session — same reasoning as `integrations.providers.base`
(Phase 11, D37): one `requests.Session()` with backoff, not a fresh one per
call, so a flaky moment on Swich's side does not surface as a payment
failure on the first try. Owned separately from `integrations`' copy rather
than imported from it — a payments adapter and a marketplace-integrations
adapter are unrelated domains that happen to share an HTTP-retry pattern,
not a real dependency between apps."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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


class SwichUnavailable(Exception):
    """Swich is not configured in this environment — an expected state, not
    a fault, exactly as `core.push.PushUnavailable` is treated."""


class SwichError(Exception):
    """Swich was configured and called, but the call itself failed — a bad
    parameter, an unreachable gateway, a rejected payout."""
