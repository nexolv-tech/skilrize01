"""Identity endpoints: signup, sign-in, verification, sessions, and profiles."""

from __future__ import annotations

import logging

import pyotp
from django.conf import settings
from django.contrib.auth import authenticate
from django.core import signing
from django.core.mail import send_mail
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core import files as filestore
from core.models import AuditLog, NotificationCategory, StoredFile, client_ip
from core.notify import dispatch
from core.pagination import StandardPagination
from core.throttling import throttled as _throttled

from . import auth as tokens
from . import devices, lockout
from .auth import require_admin_role
from .models import (
    ApprovedEmailDomain,
    BuyerProfile,
    RefreshSession,
    SecurityToken,
    SellerProfile,
    StudentVerification,
    TwoFactorDevice,
    User,
    VerificationStatus,
)
from .serializers import (
    AdminAuditLogSerializer,
    AdminRejectVerificationSerializer,
    AdminStudentVerificationSerializer,
    AdminSuspendUserSerializer,
    AdminUserSerializer,
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
    StudentEmailSerializer,
    StudentVerificationSerializer,
    TwoFactorChallengeSerializer,
    UniversitySerializer,
    UserSerializer,
)

security_log = logging.getLogger("skilrize.security")

CHALLENGE_SALT = "skilrize.2fa.challenge"
CHALLENGE_MAX_AGE = 300  # A partially-authenticated state should be brief.


#: A client that declares itself non-browser gets its tokens in the response
#: body as well as in cookies, because it has no cookie jar worth relying on
#: and authenticates with `Authorization: Bearer` instead — the path
#: `accounts.auth.CookieJWTAuthentication` has documented since Phase 0 but
#: which nothing could actually reach, since no endpoint ever handed a
#: non-browser client a token to send (found building the Flutter client,
#: Phase 7 / D38).
#:
#: Gating on a header is enough *here* and only here: reaching this code at
#: all costs a correct password, or a correct second factor, or a valid
#: enrolment challenge. Script injected into the web app has none of those,
#: so it cannot mint itself a body-delivered token by setting a header. The
#: refresh endpoint is the one that would be trivially abusable that way and
#: is gated differently — see `refresh`.
NATIVE_CLIENT_HEADER = "HTTP_X_SKILRIZE_CLIENT"


def _wants_tokens_in_body(request) -> bool:
    return request.META.get(NATIVE_CLIENT_HEADER, "").strip().lower() == "native"


def _authenticated_response(
    user, request, *, created: bool = False, verified_by_email: bool = False
):
    """Issue tokens, set cookies, and return the user.

    Also the single place a sign-in is attributed to a device, so the new-device
    alert and cool-off cannot be forgotten by one of the several paths that end
    in an authenticated session — and, since Phase 7, the single place a native
    client is handed its bearer tokens.
    """
    device, is_new = devices.register(user, request)
    if is_new and not created and not verified_by_email:
        # Skipped on signup: the account was created seconds ago from this very
        # device, and "we noticed a new device" would be nonsense as the first
        # thing a new user reads.
        #
        # Skipped after an emailed code too: that email went to the same inbox
        # moments ago and already carried the warning. The cool-off still
        # applies in both cases.
        devices.send_new_device_alert(user, request, device)

    access, refresh = tokens.issue(user, request)
    payload = UserSerializer(user).data
    body = {
        "user": payload,
        # Surfaced so the client can explain the hold up front rather than
        # letting the user discover it when a purchase fails.
        "device_cooloff_seconds": device.seconds_until_trusted if device else 0,
    }
    if _wants_tokens_in_body(request):
        body["access"] = access
        body["refresh"] = refresh
    response = Response(
        body,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
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
    ip = client_ip(request)

    # The address block comes first: a sprayer is trying many accounts, so it
    # would never trip any single account's counter, and it should be turned
    # away before it costs a database lookup.
    if (blocked := lockout.ip_blocked_for(ip)) > 0:
        security_log.warning("login_ip_blocked ip=%s", ip)
        return Response(
            {
                "detail": "Too many failed sign-in attempts from this network. Try again later.",
                "code": "ip_blocked",
                "retry_after": blocked,
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(blocked)},
        )

    # Then the account budget, checked before the password is looked at, so a
    # locked account costs an attacker a request without yielding a hash
    # comparison to time.
    if (remaining := lockout.locked_for(email)) > 0:
        security_log.warning("login_locked email=%s ip=%s", email, ip)
        return Response(
            {
                "detail": "Too many failed attempts. Try again later.",
                "code": "account_locked",
                "retry_after": remaining,
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(remaining)},
        )

    user = authenticate(request, username=email, password=serializer.validated_data["password"])
    if user is None:
        attempts = lockout.record_failure(email)
        ip_failures, ip_now_blocked = lockout.record_ip_failure(ip)
        security_log.info(
            "login_failed email=%s ip=%s attempts=%s ip_failures=%s",
            email,
            ip,
            attempts,
            ip_failures,
        )
        if ip_now_blocked:
            security_log.error("login_ip_block_applied ip=%s failures=%s", ip, ip_failures)
        AuditLog.record(
            action=AuditLog.Action.LOGIN_FAILED, request=request, after={"email": email}
        )
        return Response(
            {"detail": "Email or password is incorrect.", "code": "invalid_credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    lockout.clear(email)

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
        # Administrative roles must enrol before they can hold a session —
        # but a password proven correct a moment ago is what earns the right
        # to *do* that enrolling. Same challenge envelope as `two_factor_
        # required` above, and deliberately the same 200 status: this is an
        # actionable next step, not a terminal error, exactly like that
        # branch — a 403 here makes the frontend API client throw before the
        # login page's own code ever gets to inspect `two_factor_enrolment_
        # required` and offer the enrolment flow. Marked `enrol` so the
        # challenge can only ever be redeemed at `/auth/login/2fa/enrol/...`,
        # never mistaken for a real second factor. Before Phase 11 (D37),
        # this branch was a genuine dead end — no challenge was issued, and
        # an admin without an authenticator already confirmed had no path
        # back in short of a database fix.
        challenge = signing.dumps({"uid": user.pk, "enrol": True}, salt=CHALLENGE_SALT)
        return Response(
            {
                "two_factor_enrolment_required": True,
                "challenge": challenge,
            }
        )

    # No authenticator enrolled, and a device this account has never used. The
    # emailed code stands in for the second factor the user does not have, so
    # a password on its own is never sufficient from somewhere unfamiliar.
    # Checked with `current` rather than `register` so a failed attempt cannot
    # enrol the attacker's device as known.
    if settings.REQUIRE_NEW_DEVICE_VERIFICATION and devices.current(user, request) is None:
        _send_device_verification(user, request)
        challenge = signing.dumps({"uid": user.pk, "dv": True}, salt=CHALLENGE_SALT)
        return Response(
            {
                "device_verification_required": True,
                "challenge": challenge,
                # Enough to reassure the right person and useless to anyone else.
                "sent_to": _mask_email(user.email),
            }
        )

    AuditLog.record(actor=user, action=AuditLog.Action.LOGIN, target=user, request=request)
    return _authenticated_response(user, request)


def _mask_email(email: str) -> str:
    """`ahmed@example.com` -> `a•••d@example.com`."""
    name, _, domain = email.partition("@")
    if len(name) <= 2:
        return f"{name[:1]}•••@{domain}"
    return f"{name[0]}•••{name[-1]}@{domain}"


def _send_device_verification(user, request) -> None:
    _, raw = SecurityToken.issue(user, SecurityToken.Purpose.DEVICE_VERIFY, digits=6)
    send_mail(
        subject="Your SkilRize sign-in code",
        message=(
            f"Your sign-in code is {raw}\n\n"
            f"It expires in 10 minutes and can be used once.\n\n"
            f"This code was requested when signing in from a device your account "
            f"has not used before"
            f"{f' ({client_ip(request)})' if client_ip(request) else ''}.\n\n"
            f"If you did not try to sign in, someone else may know your password. "
            f"Do not share this code with anyone — change your password instead."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@_throttled("otp")
def login_device_verify(request):
    """Finish a sign-in from an unrecognised device with the emailed code.

    Mirrors `login_two_factor` deliberately: same challenge envelope, same
    per-account attempt budget, same refusal to say whether the account exists.
    The only difference is where the code came from.
    """
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

    # A 2FA challenge must not be redeemable here: that would let an account
    # with an authenticator be entered with an email code instead, quietly
    # downgrading its second factor to whatever the inbox is worth.
    if not payload.get("dv"):
        return Response(
            {"detail": "Wrong verification method for this sign-in.", "code": "invalid_challenge"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    lock_id = f"device:{payload.get('uid')}"
    if (remaining := lockout.locked_for(lock_id)) > 0:
        security_log.warning("device_verify_locked user=%s", payload.get("uid"))
        return Response(
            {
                "detail": "Too many failed attempts. Try again later.",
                "code": "account_locked",
                "retry_after": remaining,
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(remaining)},
        )

    user = User.objects.filter(pk=payload["uid"], is_active=True).first()
    code = serializer.validated_data["code"]
    if user is None or not SecurityToken.consume(user, SecurityToken.Purpose.DEVICE_VERIFY, code):
        attempts = lockout.record_failure(lock_id)
        lockout.record_ip_failure(client_ip(request))
        security_log.warning(
            "device_verify_failed user=%s attempts=%s", payload.get("uid"), attempts
        )
        return Response(
            {"detail": "That code is not valid.", "code": "invalid_code"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    lockout.clear(lock_id)
    AuditLog.record(actor=user, action=AuditLog.Action.LOGIN, target=user, request=request)
    # `verified_by_email` suppresses the separate "new device" alert: the code
    # that just cleared went to the same inbox, so a second email saying a new
    # device signed in would be telling them what they already did.
    return _authenticated_response(user, request, verified_by_email=True)


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

    # A six-digit code is a 1-in-a-million guess, which is only strong while the
    # number of guesses is bounded. The budget is keyed to the account, not the
    # challenge, so minting fresh challenges does not buy more attempts.
    lock_id = f"2fa:{payload.get('uid')}"
    if (remaining := lockout.locked_for(lock_id)) > 0:
        security_log.warning("two_factor_locked user=%s", payload.get("uid"))
        return Response(
            {
                "detail": "Too many failed attempts. Try again later.",
                "code": "account_locked",
                "retry_after": remaining,
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(remaining)},
        )

    if user is None or not tokens.verify_second_factor(user, serializer.validated_data["code"]):
        attempts = lockout.record_failure(lock_id)
        lockout.record_ip_failure(client_ip(request))
        security_log.warning("two_factor_failed user=%s attempts=%s", payload.get("uid"), attempts)
        return Response(
            {"detail": "That code is not valid.", "code": "invalid_code"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    lockout.clear(lock_id)
    AuditLog.record(actor=user, action=AuditLog.Action.LOGIN, target=user, request=request)
    return _authenticated_response(user, request)


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh(request):
    # Which source the token came from decides whether the rotated pair is
    # returned in the body, so this is read as two separate things rather
    # than one `or` (Phase 7 / D38).
    from_cookie = request.COOKIES.get(tokens.REFRESH_COOKIE)
    from_body = request.data.get("refresh")
    raw = from_cookie or from_body
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

    # The rotated pair goes in the body **only** when the caller supplied the
    # old one in the body — that is, only to something that already held the
    # token out-of-band. Deliberately not gated on a header like the sign-in
    # paths above: script injected into the web app cannot read the HttpOnly
    # refresh cookie, so it cannot present one here, so it can never turn
    # this endpoint into a way to lift a long-lived token out of a browser
    # session it has otherwise only transient control of.
    body = {"detail": "ok"}
    if not from_cookie and from_body:
        body["access"] = access
        body["refresh"] = new_refresh
    return tokens.set_auth_cookies(Response(body), access, new_refresh)


@api_view(["POST"])
@permission_classes([AllowAny])
def logout(request):
    # A native client has no cookie to read, so it hands its refresh token
    # back explicitly — otherwise signing out would clear local state while
    # leaving a valid, revocable session alive on the server (Phase 7 / D38).
    raw = request.COOKIES.get(tokens.REFRESH_COOKIE) or request.data.get("refresh")
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

    payload = UserSerializer(request.user).data
    # Attached here rather than on the serializer: it is a property of the
    # calling device, not of the account, and the same user answers differently
    # from two browsers.
    payload["device_cooloff_seconds"] = devices.cooloff_remaining(request.user, request)
    # The surfaces this user may ask for. The client renders the switcher from
    # this list rather than deciding for itself who is a student — and the
    # server re-checks entitlement on every request regardless, so a client
    # that ignores it gains nothing.
    payload["surfaces"] = _surfaces_for(request.user)
    return Response(payload)


def _surfaces_for(user) -> list[dict]:
    surfaces = [{"kind": "global", "label": "Global marketplace", "university": None}]
    if user.is_verified_student and user.university:
        surfaces.append(
            {
                "kind": "university",
                "label": f"{user.university.short_code} campus",
                "university": UniversitySerializer(user.university).data,
            }
        )
    return surfaces


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


# --- Student verification --------------------------------------------------
#
# Three steps, in order: prove the university address, prove the ID card where
# the university asks for one, then a human decision. The portal only opens on
# `StudentVerification.approve()`, which is the single place `User.university`
# is ever written — everything else here moves an application toward that one
# call or away from it.


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def student_verification(request):
    """The caller's current or most recent application."""
    row = StudentVerification.objects.filter(user=request.user).select_related("university").first()
    if row is None:
        return Response({"application": None})
    return Response({"application": StudentVerificationSerializer(row).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_throttled("otp")
def student_email_request(request):
    """Start an application by claiming a university address."""
    serializer = StudentEmailSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    address = serializer.validated_data["university_email"].strip().lower()

    university = ApprovedEmailDomain.match(address)
    if university is None:
        return Response(
            {
                "detail": "That address does not belong to a university on SkilRize yet.",
                "code": "unknown_university_domain",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # One account per university address. Without this, several students could
    # each claim the same address and every one of them would land inside the
    # same portal on the strength of one inbox.
    taken = (
        StudentVerification.objects.filter(university_email=address)
        .exclude(user=request.user)
        .exclude(status=StudentVerification.Status.REJECTED)
        .exists()
    )
    if taken:
        security_log.warning("student_email_contested email=%s user=%s", address, request.user.pk)
        return Response(
            {
                "detail": "That university address is already linked to another account.",
                "code": "email_taken",
            },
            status=status.HTTP_409_CONFLICT,
        )

    # Restarting replaces any open attempt rather than stacking a second one,
    # which the partial unique constraint would refuse anyway.
    StudentVerification.objects.filter(
        user=request.user,
        status__in=[
            StudentVerification.Status.EMAIL_PENDING,
            StudentVerification.Status.AWAITING_ID,
            StudentVerification.Status.UNDER_REVIEW,
        ],
    ).delete()

    application = StudentVerification.objects.create(
        user=request.user, university=university, university_email=address
    )

    _, raw = SecurityToken.issue(
        request.user,
        SecurityToken.Purpose.STUDENT_EMAIL_OTP,
        destination=address,
        digits=6,
    )
    send_mail(
        subject=f"Confirm your {university.short_code} email",
        message=(
            f"Your SkilRize verification code is {raw}\n\n"
            f"It expires in 10 minutes.\n\n"
            f"Entering it links your account to {university.name} and, once approved, "
            f"opens your campus marketplace."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        # Deliberately the claimed address, not the account address — sending
        # the code anywhere else would prove nothing about who controls it.
        recipient_list=[address],
        fail_silently=False,
    )

    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.CREATE,
        target=application,
        request=request,
        justification=f"Student verification started for {university.short_code}.",
    )
    return Response(
        {"application": StudentVerificationSerializer(application).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_throttled("otp")
def student_email_verify(request):
    """Confirm the emailed code and advance the application."""
    serializer = OTPSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    application = (
        StudentVerification.objects.filter(
            user=request.user, status=StudentVerification.Status.EMAIL_PENDING
        )
        .select_related("university")
        .first()
    )
    if application is None:
        return Response(
            {"detail": "There is no email confirmation pending.", "code": "not_started"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not SecurityToken.consume(
        request.user, SecurityToken.Purpose.STUDENT_EMAIL_OTP, serializer.validated_data["code"]
    ):
        return Response(
            {"detail": "That code is not valid.", "code": "invalid_code"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    application.mark_email_verified()
    return Response({"application": StudentVerificationSerializer(application).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def student_id_card(request):
    """Attach the student ID card and hand the application to a reviewer."""
    application = (
        StudentVerification.objects.filter(
            user=request.user,
            status__in=[
                StudentVerification.Status.AWAITING_ID,
                StudentVerification.Status.UNDER_REVIEW,
            ],
        )
        .select_related("university")
        .first()
    )
    if application is None:
        return Response(
            {"detail": "Confirm your university email first.", "code": "email_not_verified"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    uploaded = request.FILES.get("file")
    if uploaded is None:
        return Response(
            {"detail": "No file was provided.", "code": "invalid"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    record = filestore.store(uploaded, owner=request.user, purpose=StoredFile.Purpose.IDENTITY)
    application.id_card = record
    application.status = StudentVerification.Status.UNDER_REVIEW
    application.save(update_fields=["id_card", "status", "updated_at"])

    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.CREATE,
        target=record,
        request=request,
        justification="Student ID card submitted for review.",
    )
    dispatch(
        request.user,
        NotificationCategory.VERIFICATION,
        "Student ID received",
        f"We will review your {application.university.short_code} verification shortly.",
    )
    return Response(
        {"application": StudentVerificationSerializer(application).data},
        status=status.HTTP_201_CREATED,
    )


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


def _begin_two_factor_enrolment(user) -> tuple[dict | None, Response | None]:
    """Shared by the authenticated settings-page flow (`two_factor_setup`)
    and the challenge-token flow an unauthenticated-but-password-proven
    admin uses to enrol at login (`login_two_factor_enrol_setup`, D37) — the
    device row, the idempotency rule, and the error case are identical
    either way; only how `user` gets resolved differs between the two
    callers.

    Returns `(data, None)` on success or `(None, error_response)`.

    **Idempotent while enrolment is pending.** An earlier version minted a fresh
    secret on every call, which quietly broke the feature: the client starts
    enrolment from an effect, React runs effects twice in development, and the
    second call overwrote the secret behind the QR code the first had already
    rendered. The user scanned a valid QR, typed the code their authenticator
    showed, and was told it was wrong — because the server had thrown that
    secret away.

    It was never only a development problem. Any second call — a remount, a
    back-navigation, a second click on "set up" — invalidated a QR the user may
    already have scanned. Rotating an *unconfirmed* secret protects nothing:
    it is reachable only by the session (or challenge) that just created it, and
    it becomes real only once confirmation proves the authenticator holds it. So
    the secret is minted once and reused until enrolment completes.
    """
    device, _ = TwoFactorDevice.objects.get_or_create(
        user=user, defaults={"secret": pyotp.random_base32()}
    )
    if device.confirmed_at:
        return None, Response(
            {"detail": "Two-factor authentication is already enabled.", "code": "already_enabled"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Only if a previous attempt somehow left the row without one.
    if not device.secret:
        device.secret = pyotp.random_base32()
        device.save(update_fields=["secret", "updated_at"])

    return {
        # The QR is the path everyone actually uses; the secret is the
        # fallback for authenticators that cannot scan, and is shown behind
        # a disclosure rather than printed next to the code.
        "qr_svg": tokens.provisioning_qr(device),
        "secret": device.secret,
        "otpauth_url": tokens.provisioning_uri(device),
    }, None


def _finish_two_factor_enrolment(user, code: str) -> tuple[list[str] | None, Response | None]:
    """The confirm-side counterpart to `_begin_two_factor_enrolment` — see
    its docstring. Returns `(recovery_codes, None)` on success or
    `(None, error_response)`."""
    device = getattr(user, "two_factor", None)
    if device is None:
        return None, Response(
            {"detail": "Start enrolment first.", "code": "not_started"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not tokens.verify_totp(device, code):
        return None, Response(
            {"detail": "That code is not valid.", "code": "invalid_code"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    codes = TwoFactorDevice.generate_recovery_codes()
    device.set_recovery_codes(codes)
    device.confirmed_at = timezone.now()
    device.save(update_fields=["recovery_code_hashes", "confirmed_at", "updated_at"])
    return codes, None


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def two_factor_setup(request):
    """Begin enrolment. Returns the secret and its provisioning URI."""
    data, error = _begin_two_factor_enrolment(request.user)
    return error or Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def two_factor_confirm(request):
    """Finish enrolment by proving the authenticator works."""
    serializer = OTPSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    codes, error = _finish_two_factor_enrolment(request.user, serializer.validated_data["code"])
    if error:
        return error

    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.TWO_FACTOR_ENABLED,
        target=request.user,
        request=request,
    )
    # Shown exactly once. They are stored hashed and cannot be retrieved again.
    return Response({"recovery_codes": codes})


def _resolve_enrolment_challenge(raw_challenge: str):
    """Verify a login-issued enrolment challenge and return the user it was
    minted for, or `(None, error_response)`.

    Mirrors `login_two_factor`/`login_device_verify`'s own challenge
    handling — same signed envelope, same `CHALLENGE_SALT`/`CHALLENGE_MAX_AGE`
    — but checks `enrol` rather than `dv`, so a normal 2FA-verify challenge
    can never be redeemed here to skip actually enrolling, and this
    challenge can never be redeemed at `/auth/login/2fa/` either.
    """
    try:
        payload = signing.loads(raw_challenge, salt=CHALLENGE_SALT, max_age=CHALLENGE_MAX_AGE)
    except signing.BadSignature:
        return None, Response(
            {
                "detail": "This sign-in attempt has expired. Start again.",
                "code": "challenge_expired",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not payload.get("enrol"):
        return None, Response(
            {"detail": "Wrong verification method for this sign-in.", "code": "invalid_challenge"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = User.objects.filter(pk=payload["uid"], is_active=True).first()
    if user is None or not user.requires_two_factor or user.has_two_factor:
        # The account was suspended, its role changed, or it already
        # finished enrolling from another tab between issuing this
        # challenge and redeeming it — in every case, this challenge no
        # longer describes a real pending enrolment.
        return None, Response(
            {
                "detail": "This sign-in attempt is no longer valid. Start again.",
                "code": "invalid_challenge",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return user, None


@api_view(["POST"])
@permission_classes([AllowAny])
@_throttled("otp")
def login_two_factor_enrol_setup(request):
    """Begin enrolment for an admin account that has never held a session —
    the fix for the gap D35/D37 both name: an admin's password proves who
    they are, but `requires_two_factor` blocks a session before they can
    reach the (authenticated) settings page that would normally start
    enrolment. Same shape as `login_two_factor`/`login_device_verify`: a
    signed challenge stands in for the session those need.
    """
    challenge = request.data.get("challenge")
    if not challenge:
        return Response({"detail": "challenge is required."}, status=status.HTTP_400_BAD_REQUEST)

    user, error = _resolve_enrolment_challenge(challenge)
    if error:
        return error

    data, error = _begin_two_factor_enrolment(user)
    return error or Response(data)


@api_view(["POST"])
@permission_classes([AllowAny])
@_throttled("otp")
def login_two_factor_enrol_confirm(request):
    """Finish enrolment and sign in in the same motion — the admin proved
    their password to get here and just proved they hold the authenticator
    they scanned the QR into; asking for the password a third time would be
    friction with no security the second factor doesn't already cover.
    """
    serializer = TwoFactorChallengeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user, error = _resolve_enrolment_challenge(serializer.validated_data["challenge"])
    if error:
        return error

    # A six-digit code is a 1-in-a-million guess, bounded the same way the
    # sibling challenge flows bound theirs.
    lock_id = f"2fa-enrol:{user.pk}"
    if (remaining := lockout.locked_for(lock_id)) > 0:
        security_log.warning("two_factor_enrol_locked user=%s", user.pk)
        return Response(
            {
                "detail": "Too many failed attempts. Try again later.",
                "code": "account_locked",
                "retry_after": remaining,
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(remaining)},
        )

    codes, error = _finish_two_factor_enrolment(user, serializer.validated_data["code"])
    if error:
        lockout.record_failure(lock_id)
        return error
    lockout.clear(lock_id)

    AuditLog.record(
        actor=user, action=AuditLog.Action.TWO_FACTOR_ENABLED, target=user, request=request
    )
    response = _authenticated_response(user, request, verified_by_email=False)
    # `_authenticated_response` already rendered its own payload shape; add
    # the recovery codes to it rather than sending a second response — this
    # is the one time enrolling and signing in are the same request, and the
    # codes are shown exactly once regardless of which path enrolled.
    response.data["recovery_codes"] = codes
    return response


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


# --- Admin console (Phase 9) -------------------------------------------------
#
# Everything below is real operator tooling, not a developer convenience —
# Django admin carried this load until now (`config/settings.py`). Two things
# this deliberately does not cover: resolving a contract dispute (nothing in
# the product raises one yet, so there is nothing to resolve — see
# `contracts.views` for the same restraint) and impersonation (`AuditLog`
# has carried an `IMPERSONATE` action choice since Phase 0 with no code that
# ever writes it; acting *as* another user is a materially riskier feature
# than anything else here and deserves its own review, not a bolt-on).

_VERIFICATION_ROLES = (User.AdminRole.VERIFICATION_OFFICER,)
_SUPPORT_ROLES = (User.AdminRole.SUPPORT_AGENT,)


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*_VERIFICATION_ROLES)])
def admin_verification_queue(request):
    """Applications awaiting a decision, oldest first — a queue, not a
    browse list, so nothing sits unreviewed just because a newer one is
    easier to find."""
    status_filter = request.query_params.get("status", StudentVerification.Status.UNDER_REVIEW)
    queryset = (
        StudentVerification.objects.filter(status=status_filter)
        .select_related("user", "university", "reviewed_by")
        .order_by("created_at")
    )
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        AdminStudentVerificationSerializer(page, many=True).data
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*_VERIFICATION_ROLES)])
def admin_verification_approve(request, pk):
    application = get_object_or_404(StudentVerification, pk=pk)
    if not application.is_open:
        return Response(
            {"detail": "This application has already been decided."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    application.approve(reviewer=request.user)
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=application,
        request=request,
        justification="Student verification approved.",
    )
    dispatch(
        application.user,
        NotificationCategory.VERIFICATION,
        "Campus verification approved",
        f"You now have access to {application.university.name}'s campus portal.",
    )
    return Response(AdminStudentVerificationSerializer(application).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*_VERIFICATION_ROLES)])
def admin_verification_reject(request, pk):
    application = get_object_or_404(StudentVerification, pk=pk)
    if not application.is_open:
        return Response(
            {"detail": "This application has already been decided."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = AdminRejectVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    reason = serializer.validated_data["reason"]

    application.reject(reason, reviewer=request.user)
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=application,
        request=request,
        justification=f"Student verification rejected: {reason}",
    )
    dispatch(
        application.user,
        NotificationCategory.VERIFICATION,
        "Campus verification not approved",
        reason,
    )
    return Response(AdminStudentVerificationSerializer(application).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*_SUPPORT_ROLES)])
def admin_users(request):
    query = request.query_params.get("q", "").strip()
    queryset = User.objects.select_related("university").order_by("-created_at")
    if query:
        queryset = queryset.filter(
            Q(email__icontains=query) | Q(handle__icontains=query) | Q(full_name__icontains=query)
        )
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(AdminUserSerializer(page, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(*_SUPPORT_ROLES)])
def admin_user_detail(request, pk):
    user = get_object_or_404(User.objects.select_related("university"), pk=pk)
    return Response(AdminUserSerializer(user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*_SUPPORT_ROLES)])
def admin_user_suspend(request, pk):
    user = get_object_or_404(User, pk=pk)
    # An admin account is not something a Support Agent can silence from
    # here — that needs a Super Admin acting deliberately, not a support
    # workflow's suspend button.
    if user.admin_role or user.is_staff:
        return Response(
            {"detail": "Cannot suspend another admin account from here."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not user.is_active:
        return Response(
            {"detail": "This account is already suspended."}, status=status.HTTP_400_BAD_REQUEST
        )

    serializer = AdminSuspendUserSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    reason = serializer.validated_data["reason"]

    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=user,
        request=request,
        justification=f"Account suspended: {reason}",
    )
    dispatch(user, NotificationCategory.SECURITY, "Your account has been suspended", reason)
    return Response(AdminUserSerializer(user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, require_admin_role(*_SUPPORT_ROLES)])
def admin_user_reactivate(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.is_active:
        return Response(
            {"detail": "This account is already active."}, status=status.HTTP_400_BAD_REQUEST
        )

    user.is_active = True
    user.save(update_fields=["is_active", "updated_at"])
    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.UPDATE,
        target=user,
        request=request,
        justification="Account reactivated.",
    )
    dispatch(
        user,
        NotificationCategory.SECURITY,
        "Your account has been reactivated",
        "You can sign in normally again.",
    )
    return Response(AdminUserSerializer(user).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated, require_admin_role(User.AdminRole.SUPER_ADMIN)])
def admin_audit_log(request):
    """The append-only administrative log — Super Admin only. Everyone else
    on the console acts within their own role's data; reading a record of
    *everyone's* actions, including IP addresses, is a materially different
    level of access than any single-purpose screen needs."""
    queryset = AuditLog.objects.select_related("actor").order_by("-created_at")

    if action := request.query_params.get("action"):
        queryset = queryset.filter(action=action)
    if actor_email := request.query_params.get("actor"):
        queryset = queryset.filter(actor__email__icontains=actor_email)
    if target_type := request.query_params.get("target_type"):
        queryset = queryset.filter(target_type__iexact=target_type)
    if since := request.query_params.get("since"):
        queryset = queryset.filter(created_at__gte=since)

    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(AdminAuditLogSerializer(page, many=True).data)
