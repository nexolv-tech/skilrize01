"""
Tenancy scope enforcement.

Report Section 4.4 calls a missed scope filter a data breach: one university
seeing another's private content, or private student content leaking into the
public marketplace. It cannot be left to individual developers remembering to
filter, so enforcement lives here, at the data-access layer, rather than in
views.

The contract this module enforces:

  * Every scopeable model's default manager requires an explicit scope context.
    A query issued with no scope context raises ``ScopeNotSet`` rather than
    returning unfiltered rows.
  * Scope is derived server-side from the authenticated user and the requested
    surface. A client may *request* a surface; only the server decides whether
    the user is entitled to it.
  * Escaping the filter is possible but must be deliberate and greppable:
    ``Model.objects.unscoped()``. There is no accidental path to unfiltered
    data.

The student portals themselves arrive in a later phase. The enforcement layer
is built now so that every model added between now and then inherits correct
behaviour by default — retrofitting tenancy into models that were written
without it is the kind of rewrite this project cannot afford.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum

from django.db.models import Q

security_log = logging.getLogger("skilrize.security")


class Visibility(StrEnum):
    """Where a piece of content is allowed to be seen."""

    GLOBAL = "global"
    UNIVERSITY = "university"


class SurfaceKind(StrEnum):
    GLOBAL = "global"
    UNIVERSITY = "university"
    #: System and administrative work. Every use is audited.
    UNRESTRICTED = "unrestricted"


class ScopeNotSet(RuntimeError):
    """A scopeable model was queried with no scope context active."""


class ScopeDenied(PermissionError):
    """A surface was requested that the user is not entitled to."""


@dataclass(frozen=True, slots=True)
class Scope:
    """The surface a request is currently operating on."""

    kind: SurfaceKind
    university_id: int | None = None

    def __post_init__(self) -> None:
        if self.kind is SurfaceKind.UNIVERSITY and self.university_id is None:
            raise ValueError("A university scope requires a university_id.")

    @property
    def is_unrestricted(self) -> bool:
        return self.kind is SurfaceKind.UNRESTRICTED

    def as_filter(self) -> Q:
        """The mandatory pre-filter for this scope.

        Applied before any other filter, and in search before ranking runs —
        never as a post-filter on a result set, because a post-filter leaks
        existence through result counts and pagination.
        """
        match self.kind:
            case SurfaceKind.UNRESTRICTED:
                return Q()
            case SurfaceKind.GLOBAL:
                return Q(visibility=Visibility.GLOBAL)
            case SurfaceKind.UNIVERSITY:
                return Q(visibility=Visibility.UNIVERSITY, university_id=self.university_id)
        raise AssertionError(f"Unhandled surface kind: {self.kind}")

    def __str__(self) -> str:
        if self.kind is SurfaceKind.UNIVERSITY:
            return f"university:{self.university_id}"
        return str(self.kind)


GLOBAL_SCOPE = Scope(SurfaceKind.GLOBAL)
UNRESTRICTED_SCOPE = Scope(SurfaceKind.UNRESTRICTED)

_current: ContextVar[Scope | None] = ContextVar("skilrize_scope", default=None)


def get_scope() -> Scope | None:
    return _current.get()


def require_scope() -> Scope:
    scope = _current.get()
    if scope is None:
        raise ScopeNotSet(
            "This model is scopeable and was queried with no active scope. Wrap the "
            "call in `with use_scope(...)`, or use `.unscoped()` if reaching across "
            "every surface is genuinely intended."
        )
    return scope


@contextmanager
def use_scope(scope: Scope):
    """Activate ``scope`` for the duration of the block."""
    token = _current.set(scope)
    try:
        yield scope
    finally:
        _current.reset(token)


def resolve_for(user, requested_surface: str | None, university_id: int | None = None) -> Scope:
    """Decide which scope a request runs under.

    ``requested_surface`` arrives from the client. It is a request, not an
    instruction: a surface the user is not entitled to raises ``ScopeDenied``,
    which the API surfaces as a 403 and records as a security event. It is
    never silently downgraded to an empty result set, because silently empty
    looks identical to "there is nothing here" and hides a real attack.
    """
    if requested_surface in (None, "", SurfaceKind.GLOBAL):
        return GLOBAL_SCOPE

    if requested_surface != SurfaceKind.UNIVERSITY:
        raise ScopeDenied(f"Unknown surface '{requested_surface}'.")

    if not (user and user.is_authenticated):
        raise ScopeDenied("University surfaces require authentication.")

    # A verified student is entitled to exactly one university: their own.
    entitled_id = getattr(user, "university_id", None)
    if entitled_id is None or not getattr(user, "is_verified_student", False):
        security_log.warning(
            "scope_denied user=%s requested=university:%s reason=not_verified",
            user.pk,
            university_id,
        )
        raise ScopeDenied("You are not a verified student of any university.")

    if university_id is not None and university_id != entitled_id:
        security_log.warning(
            "scope_denied user=%s requested=university:%s entitled=university:%s",
            user.pk,
            university_id,
            entitled_id,
        )
        raise ScopeDenied("You are not a verified student of that university.")

    return Scope(SurfaceKind.UNIVERSITY, university_id=entitled_id)
