"""Identity endpoints: signup, sign-in, verification, sessions, and profiles."""

from __future__ import annotations

import logging

import pyotp
from django.conf import settings
from django.contrib.auth import authenticate
from django.core import signing
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from core import files as filestore
from core.models import AuditLog, NotificationCategory, StoredFile
from core.notify import dispatch

from . import auth as tokens
from .models import (
    ApprovedEmailDomain,
    BuyerProfile,
    RefreshSession,
    SecurityToken,
    SellerProfile,
    TwoFactorDevice,
    User,
    VerificationStatus,
)
from .serializers import (
    BuyerProfileSerializer,
    LoginSerializer,
    OTPSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PhoneSerializer,
    PublicUserSerializer,
    SellerProfileSerializer,
    SessionSerializer,
    SignupSerializer,
    StepUpSerializer,
    TwoFactorChallengeSerializer,
    UserSerializer,
)

security_log = logging.getLogger("skilrize.security")

CHALLENGE_SALT = "skilrize.2fa.challenge"
CHALLENGE_MAX_AGE = 300  # A partially-authenticated state should be brief.


def _throttled(scope: str):
    """Attach a named throttle rate to a function-based view."""

    class _Scoped(ScopedRateThrottle):
        pass

    def decorator(view):
        view.throttle_scope = scope
        return throttle_classes([_Scoped])(view)

    return decorator


def _authenticated_response(user, request, *, created: bool = False):
    """Issue tokens, set cookies, and return the user."""
    access, refresh = tokens.issue(user, request)
    payload = UserSerializer(user).data
    response = Response(
        {"user": payload}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    user.last_active_at = timezone.now()
    user.save(update_fields=["last_active_at", "updated_at"])
    return tokens.set_auth_cookies(response, access, refresh)


# --- Bootstrap -------------------------------------------------------------


@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf(request):
    """Hand the client a CSRF token before any cookie-authenticated write."""
    return Response({"detail": "ok"})


# --- Registration and sign-in ---------------------------------------------


@api_view(["POST"])
@permission_classes([AllowAny])
@_throttled("signup")
def signup(request):
    serializer = SignupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    user = User.objects.create_user(
        email=data["email"], password=data["password"], full_name=data.get("full_name", "")
    )
    # Both faces exist from the start; the platform never asks someone to
    # choose between hiring and being hired.
    SellerProfile.objects.create(user=user)
    BuyerProfile.objects.create(user=user)

    _send_email_verification(user)
    AuditLog.record(actor=user, action=AuditLog.Action.CREATE, target=user, request=request)
    return _authenticated_response(user, request, created=True)


@api_view(["POST"])
@permission_classes([AllowAny])
@_throttled("login")
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data["email"].strip().lower()

    user = authenticate(request, username=email, password=serializer.validated_data["password"])
    if user is None:
        security_log.info("login_failed email=%s ip=%s", email, request.META.get("REMOTE_ADDR"))
        AuditLog.record(
            action=AuditLog.Action.LOGIN_FAILED, request=request, after={"email": email}
        )
        return Response(
            {"detail": "Email or password is incorrect.", "code": "invalid_credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        return Response(
            {"detail": "This account has been suspended.", "code": "account_suspended"},
            status=status.HTTP_403_FORBIDDEN,
        )

    if user.has_two_factor:
        # Password alone does not produce a session. It produces a short-lived
        # challenge that is worthless without the second factor.
        challenge = signing.dumps({"uid": user.pk}, salt=CHALLENGE_SALT)
        return Response({"two_factor_required": True, "challenge": challenge})

    if user.requires_two_factor:
        # Administrative roles must enrol before they can hold a session.
        return Response(
            {
                "detail": "Two-factor authentication is required for this account.",
                "code": "two_factor_enrolment_required",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    AuditLog.record(actor=user, action=AuditLog.Action.LOGIN, target=user, request=request)
    return _authenticated_response(user, request)


@api_view(["POST"])
@permission_classes([AllowAny])
@_throttled("login")
def login_two_factor(request):
    serializer = TwoFactorChallengeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        payload = signing.loads(
            serializer.validated_data["challenge"], salt=CHALLENGE_SALT, max_age=CHALLENGE_MAX_AGE
        )
    except signing.BadSignature:
        return Response(
            {
                "detail": "This sign-in attempt has expired. Start again.",
                "code": "challenge_expired",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = User.objects.filter(pk=payload["uid"], is_active=True).first()
    if user is None or not tokens.verify_second_factor(user, serializer.validated_data["code"]):
        security_log.warning("two_factor_failed user=%s", payload.get("uid"))
        return Response(
            {"detail": "That code is not valid.", "code": "invalid_code"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    AuditLog.record(actor=user, action=AuditLog.Action.LOGIN, target=user, request=request)
    return _authenticated_response(user, request)


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh(request):
    raw = request.COOKIES.get(tokens.REFRESH_COOKIE) or request.data.get("refresh")
    if not raw:
        return Response(
            {"detail": "No refresh token supplied.", "code": "no_refresh"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        access, new_refresh = tokens.rotate(raw, request)
    except tokens.TokenReuseDetected as exc:
        return tokens.clear_auth_cookies(
            Response(
                {"detail": str(exc), "code": "token_reuse"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        )

    return tokens.set_auth_cookies(Response({"detail": "ok"}), access, new_refresh)


@api_view(["POST"])
@permission_classes([AllowAny])
def logout(request):
    raw = request.COOKIES.get(tokens.REFRESH_COOKIE)
    if raw:
        tokens.revoke(raw)
    if request.user.is_authenticated:
        AuditLog.record(
            actor=request.user, action=AuditLog.Action.LOGOUT, target=request.user, request=request
        )
    return tokens.clear_auth_cookies(Response({"detail": "ok"}))


# --- The signed-in user ----------------------------------------------------


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def me(request):
    if request.method == "PATCH":
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(UserSerializer(request.user).data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_seller_profile(request):
    profile, _ = SellerProfile.objects.get_or_create(user=request.user)
    serializer = SellerProfileSerializer(profile, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_buyer_profile(request):
    profile, _ = BuyerProfile.objects.get_or_create(user=request.user)
    serializer = BuyerProfileSerializer(profile, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_avatar(request):
    uploaded = request.FILES.get("file")
    if uploaded is None:
        return Response(
            {"detail": "No file was provided.", "code": "invalid"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    record = filestore.store(
        uploaded, owner=request.user, purpose=StoredFile.Purpose.AVATAR, max_bytes=5 * 1024 * 1024
    )
    request.user.avatar = record
    request.user.save(update_fields=["avatar", "updated_at"])
    return Response(UserSerializer(request.user).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_profile(request, handle: str):
    user = get_object_or_404(User, handle=handle, is_active=True)
    if user.profile_visibility == User.Visibility.PRIVATE:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    if user.profile_visibility == User.Visibility.PLATFORM and not request.user.is_authenticated:
        return Response(
            {"detail": "Sign in to view this profile.", "code": "authentication_required"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    return Response(PublicUserSerializer(user).data)


# --- Email, phone, and identity verification ------------------------------


def _send_email_verification(user: User) -> None:
    _, raw = SecurityToken.issue(user, SecurityToken.Purpose.EMAIL_VERIFY)
    link = f"{settings.FRONTEND_URL}/verify-email?token={raw}&email={user.email}"
    send_mail(
        subject="Confirm your SkilRize email",
        message=f"Confirm your email address to finish setting up your account:\n\n{link}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_throttled("otp")
def request_email_verification(request):
    if request.user.email_verified:
        return Response({"detail": "Already verified."})
    _send_email_verification(request.user)
    return Response({"detail": "Verification email sent."})


@api_view(["POST"])
@permission_classes([AllowAny])
@_throttled("otp")
def confirm_email(request):
    email = (request.data.get("email") or "").strip().lower()
    token = request.data.get("token") or ""
    user = User.objects.filter(email=email).first()

    if user is None or not SecurityToken.consume(user, SecurityToken.Purpose.EMAIL_VERIFY, token):
        return Response(
            {"detail": "This link is invalid or has expired.", "code": "invalid_token"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.email_verified = True
    user.save(update_fields=["email_verified", "updated_at"])
    dispatch(
        user,
        NotificationCategory.VERIFICATION,
        "Email confirmed",
        "Your email address is verified.",
    )
    return Response({"detail": "Email verified."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_throttled("otp")
def set_phone(request):
    serializer = PhoneSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    request.user.phone_number = serializer.validated_data["phone_number"]
    request.user.phone_verified = False
    request.user.save(update_fields=["phone_number", "phone_verified", "updated_at"])

    _, code = SecurityToken.issue(
        request.user,
        SecurityToken.Purpose.PHONE_OTP,
        destination=request.user.phone_number,
        digits=6,
    )
    # The SMS provider is connected in a later phase. Until then the code is
    # logged in development only, and never returned in an API response.
    if settings.DEBUG:
        logging.getLogger(__name__).info("phone_otp user=%s code=%s", request.user.pk, code)
    return Response({"detail": "A verification code has been sent."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_throttled("otp")
def verify_phone(request):
    serializer = OTPSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    if not SecurityToken.consume(
        request.user, SecurityToken.Purpose.PHONE_OTP, serializer.validated_data["code"]
    ):
        return Response(
            {"detail": "That code is not valid.", "code": "invalid_code"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    request.user.phone_verified = True
    request.user.save(update_fields=["phone_verified", "updated_at"])
    return Response(UserSerializer(request.user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_identity(request):
    """Upload the national identity card for review.

    Required of every user, not only students, because the platform holds money
    on their behalf. The image is stored encrypted-at-rest in private storage
    and every subsequent view of it is logged.
    """
    uploaded = request.FILES.get("file")
    if uploaded is None:
        return Response(
            {"detail": "No file was provided.", "code": "invalid"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    record = filestore.store(uploaded, owner=request.user, purpose=StoredFile.Purpose.IDENTITY)
    request.user.identity_document = record
    request.user.identity_status = VerificationStatus.PENDING
    request.user.save(update_fields=["identity_document", "identity_status", "updated_at"])

    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.CREATE,
        target=record,
        request=request,
        justification="Identity document submitted for review.",
    )
    dispatch(
        request.user,
        NotificationCategory.VERIFICATION,
        "Identity document received",
        "We will review it shortly.",
    )
    return Response(UserSerializer(request.user).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def lookup_university(request):
    """Which university, if any, an email domain belongs to."""
    email = request.query_params.get("email", "")
    university = ApprovedEmailDomain.match(email) if "@" in email else None
    if university is None:
        return Response({"matched": False})
    return Response(
        {
            "matched": True,
            "university": {
                "id": university.id,
                "name": university.name,
                "short_code": university.short_code,
            },
        }
    )


# --- Passwords -------------------------------------------------------------


@api_view(["POST"])
@permission_classes([AllowAny])
@_throttled("password_reset")
def request_password_reset(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = User.objects.filter(email=serializer.validated_data["email"].lower()).first()
    if user is not None:
        _, raw = SecurityToken.issue(user, SecurityToken.Purpose.PASSWORD_RESET)
        link = f"{settings.FRONTEND_URL}/reset-password?token={raw}&email={user.email}"
        send_mail(
            subject="Reset your SkilRize password",
            message=f"Use this link within 30 minutes to set a new password:\n\n{link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

    # Section 6.1: recovery never reveals whether an address is registered, so
    # the response is identical either way.
    return Response({"detail": "If that address has an account, a reset link is on its way."})


@api_view(["POST"])
@permission_classes([AllowAny])
@_throttled("password_reset")
def confirm_password_reset(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    user = User.objects.filter(email=data["email"].lower()).first()
    if user is None or not SecurityToken.consume(
        user, SecurityToken.Purpose.PASSWORD_RESET, data["token"]
    ):
        return Response(
            {"detail": "This link is invalid or has expired.", "code": "invalid_token"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(data["password"])
    user.save(update_fields=["password", "updated_at"])
    # All active sessions are terminated on password reset.
    tokens.revoke_all(user, reason="password_reset")
    AuditLog.record(actor=user, action=AuditLog.Action.PASSWORD_RESET, target=user, request=request)
    dispatch(
        user,
        NotificationCategory.SECURITY,
        "Your password was changed",
        "If this was not you, contact support immediately.",
    )
    return Response({"detail": "Password updated. Please sign in."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = PasswordChangeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    if not request.user.check_password(serializer.validated_data["current_password"]):
        return Response(
            {"detail": "Current password is incorrect.", "code": "invalid_credentials"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    request.user.set_password(serializer.validated_data["new_password"])
    request.user.save(update_fields=["password", "updated_at"])
    tokens.revoke_all(request.user, reason="password_change")
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.PASSWORD_RESET,
        target=request.user,
        request=request,
    )

    # The caller stays signed in on this device; every other device is out.
    return _authenticated_response(request.user, request)


# --- Sessions --------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sessions(request):
    """Every active session, with device, location, and last-seen."""
    live = RefreshSession.objects.filter(
        user=request.user, revoked_at__isnull=True, expires_at__gt=timezone.now()
    )
    current = RefreshSession.objects.filter(
        token_hash=RefreshSession.hash_token(request.COOKIES.get(tokens.REFRESH_COOKIE, ""))
    ).first()
    serializer = SessionSerializer(
        live, many=True, context={"current_family": str(current.family) if current else None}
    )
    return Response(serializer.data)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def revoke_session(request, family: str):
    revoked = RefreshSession.objects.filter(
        user=request.user, family=family, revoked_at__isnull=True
    ).update(revoked_at=timezone.now())
    return Response({"revoked": revoked})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_all_sessions(request):
    count = tokens.revoke_all(request.user, reason="user_requested")
    return tokens.clear_auth_cookies(Response({"revoked": count}))


# --- Two-factor authentication --------------------------------------------


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def two_factor_setup(request):
    """Begin enrolment. Returns the secret and its provisioning URI."""
    device, _ = TwoFactorDevice.objects.get_or_create(
        user=request.user, defaults={"secret": pyotp.random_base32()}
    )
    if device.confirmed_at:
        return Response(
            {"detail": "Two-factor authentication is already enabled.", "code": "already_enabled"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    device.secret = pyotp.random_base32()
    device.save(update_fields=["secret", "updated_at"])
    return Response({"secret": device.secret, "otpauth_url": tokens.provisioning_uri(device)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def two_factor_confirm(request):
    """Finish enrolment by proving the authenticator works."""
    serializer = OTPSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    device = getattr(request.user, "two_factor", None)
    if device is None:
        return Response(
            {"detail": "Start enrolment first.", "code": "not_started"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not tokens.verify_totp(device, serializer.validated_data["code"]):
        return Response(
            {"detail": "That code is not valid.", "code": "invalid_code"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    codes = TwoFactorDevice.generate_recovery_codes()
    device.set_recovery_codes(codes)
    device.confirmed_at = timezone.now()
    device.save(update_fields=["recovery_code_hashes", "confirmed_at", "updated_at"])

    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.TWO_FACTOR_ENABLED,
        target=request.user,
        request=request,
    )
    # Shown exactly once. They are stored hashed and cannot be retrieved again.
    return Response({"recovery_codes": codes})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def two_factor_disable(request):
    """Turn off the second factor. Requires step-up authentication."""
    serializer = StepUpSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    if request.user.requires_two_factor:
        return Response(
            {
                "detail": "Two-factor authentication is mandatory for this account.",
                "code": "two_factor_mandatory",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if not tokens.verify_step_up(request.user, **serializer.validated_data):
        return Response(
            {"detail": "Verification failed.", "code": "step_up_failed"},
            status=status.HTTP_403_FORBIDDEN,
        )

    TwoFactorDevice.objects.filter(user=request.user).delete()
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.TWO_FACTOR_DISABLED,
        target=request.user,
        request=request,
    )
    dispatch(
        request.user,
        NotificationCategory.SECURITY,
        "Two-factor authentication disabled",
        "If this was not you, secure your account immediately.",
    )
    return Response({"detail": "Two-factor authentication disabled."})
