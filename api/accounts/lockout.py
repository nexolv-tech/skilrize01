"""
Per-account brute-force lockout.

DRF's throttles bound how fast *one client* can call an endpoint. They do
nothing about a credential-stuffing run that spreads a thousand guesses for one
account across a thousand addresses, which is the shape the attack actually
takes. This counts failures against the *account* instead, so the budget is
shared no matter where the attempts originate.

Two deliberate details:

* Failures are recorded for addresses that do not exist, too. If only real
  accounts locked, the lockout response itself would become an account
  enumeration oracle.
* The counter is keyed by a hash of the address rather than the address itself,
  so a dump of the cache is not a user list.
"""

from __future__ import annotations

import hashlib
import hmac

from django.conf import settings
from django.core.cache import cache

_PREFIX = "skilrize:lockout:v1:"


def _key(email: str) -> str:
    digest = hmac.new(
        settings.SECRET_KEY.encode(),
        email.strip().lower().encode(),
        hashlib.sha256,
    ).hexdigest()[:32]
    return f"{_PREFIX}{digest}"


def locked_for(email: str) -> int:
    """Seconds remaining on the lockout, or 0 when the account may try again."""
    if not email:
        return 0
    key = _key(email)
    if cache.get(key, 0) < settings.LOGIN_MAX_ATTEMPTS:
        return 0
    # `ttl` is Redis-specific; on a backend without it a locked account simply
    # reports the full window rather than the exact remainder.
    try:
        remaining = cache.ttl(key)  # type: ignore[attr-defined]
    except (AttributeError, NotImplementedError):
        remaining = None
    if remaining is None:
        return settings.LOGIN_LOCKOUT_SECONDS
    return max(int(remaining), 1)


def record_failure(email: str) -> int:
    """Count one failed attempt. Returns the new total."""
    if not email:
        return 0
    key = _key(email)
    # `add` only writes when the key is absent, so a concurrent burst cannot
    # reset a counter that is already running.
    cache.add(key, 0, timeout=settings.LOGIN_LOCKOUT_SECONDS)
    try:
        return int(cache.incr(key))
    except ValueError:
        # The key expired between `add` and `incr`. The attempt is genuinely at
        # the start of a fresh window.
        cache.set(key, 1, timeout=settings.LOGIN_LOCKOUT_SECONDS)
        return 1


def clear(email: str) -> None:
    """Forget the failures for an account, after it authenticates."""
    if email:
        cache.delete(_key(email))


# --- Per-source-address blocking -------------------------------------------
#
# The account budget above cannot see a spray: one address trying one password
# against ten thousand accounts never trips any single account's counter. This
# counts failures by origin instead, and blocks the origin outright once it is
# clearly not a person mistyping.


def _ip_key(ip: str, suffix: str) -> str:
    digest = hmac.new(settings.SECRET_KEY.encode(), ip.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{_PREFIX}ip:{suffix}:{digest}"


def ip_blocked_for(ip: str) -> int:
    """Seconds remaining on an address block, or 0 when it may try again."""
    if not ip:
        return 0
    key = _ip_key(ip, "block")
    if not cache.get(key):
        return 0
    try:
        remaining = cache.ttl(key)  # type: ignore[attr-defined]
    except (AttributeError, NotImplementedError):
        remaining = None
    if remaining is None:
        return settings.LOGIN_IP_BLOCK_SECONDS
    return max(int(remaining), 1)


def record_ip_failure(ip: str) -> tuple[int, bool]:
    """Count one failure from ``ip``. Returns ``(failures, now_blocked)``.

    The counter expires on a rolling window rather than being reset on success:
    a spray that happens to guess one password correctly should not be handed a
    clean slate for the next thousand attempts.
    """
    if not ip:
        return 0, False

    counter = _ip_key(ip, "fail")
    cache.add(counter, 0, timeout=settings.LOGIN_IP_WINDOW_SECONDS)
    try:
        failures = int(cache.incr(counter))
    except ValueError:
        cache.set(counter, 1, timeout=settings.LOGIN_IP_WINDOW_SECONDS)
        failures = 1

    if failures >= settings.LOGIN_IP_MAX_FAILURES:
        cache.set(_ip_key(ip, "block"), 1, timeout=settings.LOGIN_IP_BLOCK_SECONDS)
        return failures, True

    return failures, False


def clear_ip(ip: str) -> None:
    """Drop both the counter and any block for an address.

    Operator tooling, not part of the request path — a support agent needs a way
    to release an address that a shared NAT put in the wrong bucket.
    """
    if ip:
        cache.delete(_ip_key(ip, "fail"))
        cache.delete(_ip_key(ip, "block"))
