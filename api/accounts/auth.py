"""
Token issuance, rotation, reuse detection, and the second factor.

The shape of the scheme (Section 6.3):

  * Short-lived access tokens (15 minutes), long-lived rotating refresh tokens
    (30 days).
  * On web, both live in Secure/HttpOnly/SameSite cookies — so neither is
    reachable from JavaScript at all, which is a stronger position than the
    "access token in memory" pattern and still satisfies the rule that access
    tokens are never written to localStorage. Mobile keeps tokens in the
    platform keystore and sends them as bearer headers; both paths are
    supported below.
  * Rotation with reuse detection: presenting an already-consumed refresh token
    invalidates the entire token family. A stolen token and the real user's
    next refresh cannot both succeed, and whichever lands second kills the
    session.
  * Cookie-authenticated state-changing requests are CSRF-checked.
"""

from __future__ import annotations

import hmac
import logging
import secrets
import time
import uuid

import pyotp
from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from django.utils import timezone
from rest_framework import exceptions, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import AccessToken

from core.models import AuditLog, client_ip

from .models import RefreshSession, TwoFactorDevice

security_log = logging.getLogger("skilrize.security")

ACCESS_COOKIE = "skilrize_access"
REFRESH_COOKIE = settings.REFRESH_COOKIE_NAME


class TokenReuseDetected(exceptions.AuthenticationFailed):
    """A refresh token was presented after it had already been rotated away."""


# --- Issuing ---------------------------------------------------------------


def issue(user, request=None, *, family: uuid.UUID | None = None) -> tuple[str, str]:
    """Mint an access/refresh pair. Returns ``(access, refresh_raw)``."""
    access = AccessToken.for_user(user)
    # Claims the client can act on without a round trip. Authorisation is still
    # decided server-side on every request; these are for rendering only.
    access["email"] = user.email
    access["handle"] = user.handle
    access["can_transact"] = user.can_transact
    access["is_verified_student"] = user.is_verified_student

    raw_refresh = secrets.token_urlsafe(48)
    RefreshSession.objects.create(
        user=user,
        family=family or uuid.uuid4(),
        token_hash=RefreshSession.hash_token(raw_refresh),
        expires_at=timezone.now() + settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"],
        device_label=_device_label(request),
        ip_address=client_ip(request) if request else None,
    )
    return str(access), raw_refresh


def rotate(raw_refresh: str, request=None) -> tuple[str, str]:
    """Exchange a refresh token for a new pair, detecting replay."""
    session = (
        RefreshSession.objects.filter(token_hash=RefreshSession.hash_token(raw_refresh))
        .select_related("user")
        .first()
    )

    if session is None:
        raise exceptions.AuthenticationFailed("Invalid refresh token.", code="invalid_refresh")

    if session.rotated_at is not None or session.revoked_at is not None:
        # Either this token was already exchanged (replay) or the family was
        # revoked. Both mean the family can no longer be trusted.
        revoked = session.revoke_family()
        security_log.error(
            "refresh_reuse user=%s family=%s revoked=%s", session.user_id, session.family, revoked
        )
        AuditLog.record(
            actor=session.user,
            action=AuditLog.Action.LOGIN_FAILED,
            target=session.user,
            request=request,
            justification="Refresh token reuse detected; token family revoked.",
        )
        raise TokenReuseDetected("Session is no longer valid. Please sign in again.")

    if session.expires_at <= timezone.now():
        raise exceptions.AuthenticationFailed("Session has expired.", code="expired_refresh")

    session.rotated_at = timezone.now()
    session.last_seen_at = timezone.now()
    session.save(update_fields=["rotated_at", "last_seen_at", "updated_at"])

    return issue(session.user, request, family=session.family)


def revoke(raw_refresh: str) -> None:
    session = RefreshSession.objects.filter(
        token_hash=RefreshSession.hash_token(raw_refresh)
    ).first()
    if session:
        session.revoke_family()


def revoke_all(user, *, reason: str = "") -> int:
    """Terminate every session platform-wide.

    Called on password change, email change, and any detected compromise
    (Section 6.3).
    """
    count = RefreshSession.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    if reason:
        security_log.info("sessions_revoked user=%s count=%s reason=%s", user.pk, count, reason)
    return count


def _device_label(request) -> str:
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:120]


# --- Cookies ---------------------------------------------------------------


def _cookie_kwargs(max_age: int) -> dict:
    return {
        "max_age": max_age,
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
        "domain": settings.COOKIE_DOMAIN,
        "path": "/",
    }


def set_auth_cookies(response, access: str, refresh: str):
    access_ttl = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
    refresh_ttl = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
    response.set_cookie(ACCESS_COOKIE, access, **_cookie_kwargs(access_ttl))
    response.set_cookie(REFRESH_COOKIE, refresh, **_cookie_kwargs(refresh_ttl))
    return response


def clear_auth_cookies(response):
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(
            name, path="/", domain=settings.COOKIE_DOMAIN, samesite=settings.COOKIE_SAMESITE
        )
    return response


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate from the access cookie, falling back to the bearer header.

    Web sends cookies; mobile sends ``Authorization: Bearer``. Only the cookie
    path is CSRF-checked, because only the cookie path is something a browser
    will attach automatically to a cross-site request.
    """

    def authenticate(self, request):
        header_result = super().authenticate(request)
        if header_result is not None:
            return header_result

        raw = request.COOKIES.get(ACCESS_COOKIE)
        if not raw:
            return None

        validated = self.get_validated_token(raw)
        user = self.get_user(validated)
        self._enforce_csrf(request)
        return user, validated

    def _enforce_csrf(self, request) -> None:
        if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            return

        reason_holder = {}

        def _reject(req, reason):
            reason_holder["reason"] = reason
            return reason

        check = CsrfViewMiddleware(lambda req: None)
        check.process_request(request)
        failure = check.process_view(request, _reject, (), {})
        if failure is not None:
            raise exceptions.PermissionDenied(
                f"CSRF check failed: {reason_holder.get('reason', 'rejected')}"
            )


# --- Second factor ---------------------------------------------------------


def provisioning_uri(device: TwoFactorDevice) -> str:
    return pyotp.TOTP(device.secret).provisioning_uri(
        name=device.user.email, issuer_name="SkilRize"
    )


def verify_totp(device: TwoFactorDevice, code: str) -> bool:
    """Check a TOTP code, allowing one step of clock drift either way.

    Acceptance is tracked by time-step rather than by wall clock, so a code
    cannot be replayed inside its own validity window while a genuinely new
    code is still accepted immediately — which is what a naive "nothing within
    30 seconds" guard gets wrong.
    """
    if not device.secret or not code:
        return False
    code = code.strip().replace(" ", "")

    totp = pyotp.TOTP(device.secret)
    now = int(time.time())
    current_step = now // totp.interval

    for drift in (0, -1, 1):
        step = current_step + drift
        if not hmac.compare_digest(totp.at(step * totp.interval), code):
            continue
        if device.last_used_counter is not None and step <= device.last_used_counter:
            return False
        device.last_used_counter = step
        device.last_used_at = timezone.now()
        device.save(update_fields=["last_used_counter", "last_used_at", "updated_at"])
        return True

    return False


def verify_second_factor(user, code: str) -> bool:
    """Accept either a TOTP code or a single-use recovery code."""
    device = getattr(user, "two_factor", None)
    if device is None or not device.confirmed_at:
        return False
    return verify_totp(device, code) or device.consume_recovery_code(code)


def verify_step_up(user, password: str = "", code: str = "") -> bool:
    """Re-prove identity for a sensitive change.

    Required for changing payout details, changing the email address, and
    disabling 2FA — regardless of an otherwise valid session (Section 6.4).
    Where a second factor is enrolled it must be used; a password alone is not
    step-up for those users.
    """
    if user.has_two_factor:
        return verify_second_factor(user, code)
    return bool(password) and user.check_password(password)


# --- Permissions -----------------------------------------------------------


class CanTransact(permissions.BasePermission):
    """The profile-completion gate, as a permission class.

    Section 8.4: until email, phone, and national identity are all verified, a
    user may browse but may not post projects, publish gigs, submit proposals,
    purchase gigs, or transact in any way. Every phase that adds a
    money-adjacent endpoint attaches this — the gate is enforced in one place
    rather than re-derived per view.
    """

    message = "Complete your profile before transacting."
    code = "profile_incomplete"

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.can_transact)
