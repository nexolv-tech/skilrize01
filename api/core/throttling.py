"""
Named-scope throttling, reusable across every app — Phase 11 (D37).

**Found while doing this phase's pass over auth/2FA edges, not written from
scratch:** `accounts/views.py` had its own `_throttled(scope)` helper that
set `view.throttle_scope = scope` on the *function* before `@api_view`
wrapped it into a class. DRF's `api_view()` explicitly copies
`throttle_classes`, `permission_classes`, and a handful of other attributes
from that function onto the class it generates — but never `throttle_scope`
(`rest_framework/decorators.py`, `api_view()`). The result: every one of
`signup`, `login`, `otp`, and `password_reset`'s named rate limits was a
silent no-op. `ScopedRateThrottle.allow_request` returns `True`
unconditionally whenever `getattr(view, 'throttle_scope', None)` is falsy —
which it always was — so these four endpoints were throttled only by the
blanket `anon`/`user` rates the whole API already carries, not by the
tighter, purpose-picked rates in `DEFAULT_THROTTLE_RATES` that looked, from
reading the settings file alone, like they were doing real work.

`scoped_throttle()` below sets the scope on the *dispatched view instance*,
inside `allow_request` itself, at request time — which works identically for
a function-based view wrapped by `@api_view` and for a class-based
`APIView`/`ViewSet` action, because both call
`throttle.allow_request(request, view)` with the real instance DRF just
built for this request, never the pre-wrap function.
"""

from __future__ import annotations

from rest_framework.decorators import throttle_classes
from rest_framework.permissions import SAFE_METHODS
from rest_framework.throttling import ScopedRateThrottle


def scoped_throttle(scope: str, *, writes_only: bool = False) -> type[ScopedRateThrottle]:
    """A `ScopedRateThrottle` bound to `scope`, independent of whatever the
    dispatched view instance does or does not carry as its own
    `throttle_scope` attribute.

    `writes_only=True` skips GET/HEAD/OPTIONS entirely — for a view that
    combines a cheap list/read with an expensive write under one
    `@api_view(["GET", "POST"])` (e.g. `integrations.views.contract_meetings`),
    the named rate is meant for the write, and applying it to the read too
    would throttle browsing a contract's own meeting list at the same rate
    as actually creating one.
    """

    class _Scoped(ScopedRateThrottle):
        def allow_request(self, request, view):
            if writes_only and request.method in SAFE_METHODS:
                return True
            view.throttle_scope = scope
            return super().allow_request(request, view)

    return _Scoped


def throttled(scope: str, *, writes_only: bool = False):
    """Decorator for function-based views: `@throttled("otp")`."""

    def decorator(view):
        return throttle_classes([scoped_throttle(scope, writes_only=writes_only)])(view)

    return decorator
