"""Per-request context, security headers, and the shared error shape."""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

from .scope import ScopeDenied, defer_scope

# Django configures logging before the app registry is ready, and it imports
# `RequestContextFilter` from this module to do it. Nothing at module level
# here may touch models or DRF, both of which need loaded apps — so those
# imports live inside the functions that use them.

security_log = logging.getLogger("skilrize.security")

#: Correlation id for the current request, read by the logging filter.
_request_id: ContextVar[str] = ContextVar("skilrize_request_id", default="-")

#: The client asks for a surface with this header. The server decides whether
#: it is entitled to it (see core.scope.resolve_for).
SURFACE_HEADER = "HTTP_X_SKILRIZE_SURFACE"


class RequestContextMiddleware:
    """Attach a correlation id and activate the request's tenancy scope."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex[:16]
        request.request_id = request_id
        token = _request_id.set(request_id)

        try:
            requested = request.META.get(SURFACE_HEADER)
            # Registered rather than resolved. Authentication happens inside
            # DRF, which is downstream of every middleware, so `request.user`
            # here is still Django's session user — anonymous for any
            # token-authenticated call. Resolving now would deny every
            # university surface to everyone. See `core.scope.defer_scope`.
            with defer_scope(lambda: getattr(request, "user", None), requested):
                response = self.get_response(request)
        finally:
            _request_id.reset(token)

        response["X-Request-Id"] = request_id
        return response


class SecurityHeadersMiddleware:
    """Headers from Section 7.1 that Django does not set on its own."""

    #: The API returns JSON and nothing else, so it needs no script, style, or
    #: image privileges at all.
    API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    #: Django admin is interim internal tooling and needs its own assets.
    ADMIN_CSP = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), interest-cohort=()"

    def __init__(self, get_response):
        from django.conf import settings

        self.get_response = get_response
        # Read once at startup rather than per request, and follow the
        # configured path so relocating the console does not silently hand it
        # the locked-down API policy and break its own stylesheets.
        self.admin_prefix = "/" + settings.ADMIN_URL.lstrip("/")

    def __call__(self, request):
        response = self.get_response(request)
        is_admin = request.path.startswith(self.admin_prefix)
        response.setdefault("Content-Security-Policy", self.ADMIN_CSP if is_admin else self.API_CSP)
        response.setdefault("Permissions-Policy", self.PERMISSIONS_POLICY)
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # JSON responses and signed file downloads are for the requesting
        # origin only; nothing here is meant to be embedded elsewhere.
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response


class RequestContextFilter(logging.Filter):
    """Puts the correlation id on every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


def exception_handler(exc, context):
    """One error shape across the API, and no leaking of internals."""
    from django.core.exceptions import ValidationError as DjangoValidationError
    from rest_framework import status
    from rest_framework.response import Response
    from rest_framework.views import exception_handler as drf_exception_handler

    from .scope import ScopeNotSet

    if isinstance(exc, ScopeDenied):
        return Response(
            {"detail": str(exc), "code": "scope_denied"}, status=status.HTTP_403_FORBIDDEN
        )
    if isinstance(exc, ScopeNotSet):
        # A developer error, not a user error: a scopeable model was queried
        # with no scope. Loud in logs, opaque to the client.
        logging.getLogger(__name__).exception("Query issued with no scope context")
        return Response(
            {"detail": "Server error.", "code": "scope_missing"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if isinstance(exc, DjangoValidationError):
        return Response(
            {"detail": exc.messages[0] if exc.messages else "Invalid input.", "code": "invalid"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(response.data, dict):
        response.data.setdefault("code", _code_for(exc))
    return response


def _code_for(exc) -> str:
    """The most specific machine-readable code an exception carries.

    DRF stores a per-instance code on the ``ErrorDetail`` string rather than on
    the exception, so ``default_code`` alone would flatten every permission
    failure to ``permission_denied`` and lose the reason — the difference
    between "you are not signed in" and "your profile is incomplete", which the
    client needs in order to say anything useful.
    """
    detail = getattr(exc, "detail", None)
    if isinstance(detail, list) and detail:
        detail = detail[0]
    if (code := getattr(detail, "code", None)) is not None:
        return str(code)
    return str(getattr(exc, "default_code", "error"))
