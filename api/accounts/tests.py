"""
Tests for identity: registration, sign-in, token rotation, the second factor,
the profile-completion gate, and profile visibility.

The refresh-reuse test is the one to keep honest. Rotation without reuse
detection looks identical in every happy-path test and is worth almost nothing
against a stolen token.
"""

from __future__ import annotations

import time

import pyotp
import pytest
from django.core import mail
from rest_framework.test import APIClient

from accounts.models import (
    ApprovedEmailDomain,
    RefreshSession,
    SecurityToken,
    TwoFactorDevice,
    University,
    User,
    VerificationStatus,
)

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    account = User.objects.create_user("member@example.com", PASSWORD, full_name="Test Member")
    return account


@pytest.fixture
def signed_in(client, user):
    client.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")
    return client


# --- Registration ----------------------------------------------------------


@pytest.mark.django_db
def test_signup_creates_both_profile_faces_and_signs_in(client):
    response = client.post(
        "/api/v1/auth/signup/",
        {"email": "New.User@Example.com", "password": PASSWORD, "full_name": "New User"},
        format="json",
    )

    assert response.status_code == 201
    account = User.objects.get(email="new.user@example.com")
    # One account is a buyer and a seller from the start; no choice at signup.
    assert account.seller_profile and account.buyer_profile
    assert account.handle
    assert "skilrize_access" in response.cookies
    assert response.cookies["skilrize_refresh"]["httponly"]


@pytest.mark.django_db
def test_signup_rejects_a_weak_password(client):
    response = client.post(
        "/api/v1/auth/signup/",
        {"email": "weak@example.com", "password": "password"},
        format="json",
    )
    assert response.status_code == 400
    assert not User.objects.filter(email="weak@example.com").exists()


@pytest.mark.django_db
def test_signup_sends_email_confirmation(client):
    mail.outbox.clear()
    client.post(
        "/api/v1/auth/signup/",
        {"email": "confirm@example.com", "password": PASSWORD},
        format="json",
    )
    assert len(mail.outbox) == 1


# --- Sign-in ---------------------------------------------------------------


@pytest.mark.django_db
def test_login_succeeds_and_sets_httponly_cookies(client, user):
    response = client.post(
        "/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json"
    )

    assert response.status_code == 200
    assert response.data["user"]["email"] == user.email
    for name in ("skilrize_access", "skilrize_refresh"):
        assert response.cookies[name]["httponly"]


@pytest.mark.django_db
def test_login_with_a_wrong_password_is_rejected(client, user):
    response = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "not-the-password"},
        format="json",
    )
    assert response.status_code == 401
    assert response.data["code"] == "invalid_credentials"


@pytest.mark.django_db
def test_me_requires_authentication(client):
    assert client.get("/api/v1/auth/me/").status_code == 401


@pytest.mark.django_db
def test_me_returns_the_signed_in_account(signed_in, user):
    response = signed_in.get("/api/v1/auth/me/")
    assert response.status_code == 200
    assert response.data["email"] == user.email


# --- Token rotation and reuse detection ------------------------------------


@pytest.mark.django_db
def test_refresh_rotates_the_token(client, user):
    client.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")
    original = client.cookies["skilrize_refresh"].value

    response = client.post("/api/v1/auth/refresh/")

    assert response.status_code == 200
    assert client.cookies["skilrize_refresh"].value != original


@pytest.mark.django_db
def test_replaying_a_rotated_refresh_token_kills_the_whole_family(client, user):
    """A stolen token and the real user cannot both keep the session."""
    client.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")
    stolen = client.cookies["skilrize_refresh"].value

    # The legitimate device refreshes, which rotates `stolen` away.
    assert client.post("/api/v1/auth/refresh/").status_code == 200

    # The thief now presents the token they captured earlier.
    attacker = APIClient()
    attacker.cookies["skilrize_refresh"] = stolen
    replay = attacker.post("/api/v1/auth/refresh/")

    assert replay.status_code == 401
    assert replay.data["code"] == "token_reuse"

    # And the legitimate device is signed out too — the family is untrusted.
    assert client.post("/api/v1/auth/refresh/").status_code == 401
    assert not RefreshSession.objects.filter(user=user, revoked_at__isnull=True).exists()


@pytest.mark.django_db
def test_logout_revokes_the_session(client, user):
    client.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")
    assert client.post("/api/v1/auth/logout/").status_code == 200
    assert not RefreshSession.objects.filter(user=user, revoked_at__isnull=True).exists()


@pytest.mark.django_db
def test_sessions_are_listed_and_revocable(signed_in, user):
    listing = signed_in.get("/api/v1/auth/sessions/")
    assert listing.status_code == 200
    assert len(listing.data) == 1
    assert listing.data[0]["is_current"] is True

    family = listing.data[0]["family"]
    assert signed_in.delete(f"/api/v1/auth/sessions/{family}/").status_code == 200
    assert not RefreshSession.objects.filter(user=user, revoked_at__isnull=True).exists()


# --- Two-factor authentication --------------------------------------------


@pytest.mark.django_db
def test_two_factor_enrolment_then_challenge_on_login(client, signed_in, user):
    setup = signed_in.post("/api/v1/auth/2fa/setup/")
    assert setup.status_code == 200
    totp = pyotp.TOTP(setup.data["secret"])

    confirm = signed_in.post("/api/v1/auth/2fa/confirm/", {"code": totp.now()}, format="json")
    assert confirm.status_code == 200
    # Recovery codes are returned exactly once, at enrolment.
    assert len(confirm.data["recovery_codes"]) == 10

    user.refresh_from_db()
    assert user.has_two_factor

    # A password alone no longer produces a session.
    fresh = APIClient()
    first = fresh.post(
        "/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json"
    )
    assert first.data["two_factor_required"] is True
    assert "skilrize_access" not in first.cookies

    second = fresh.post(
        "/api/v1/auth/login/2fa/",
        # A code from the next time step: the one just spent on enrolment
        # cannot be presented again.
        {"challenge": first.data["challenge"], "code": totp.at(time.time() + totp.interval)},
        format="json",
    )
    assert second.status_code == 200
    assert second.cookies["skilrize_access"]


@pytest.mark.django_db
def test_a_totp_code_cannot_be_used_twice(signed_in, user):
    """Replay inside the code's own validity window must fail."""
    from accounts.auth import verify_totp

    totp = pyotp.TOTP(signed_in.post("/api/v1/auth/2fa/setup/").data["secret"])
    code = totp.now()
    signed_in.post("/api/v1/auth/2fa/confirm/", {"code": code}, format="json")

    device = TwoFactorDevice.objects.get(user=user)
    assert verify_totp(device, code) is False


@pytest.mark.django_db
def test_two_factor_login_rejects_a_bad_code(client, signed_in, user):
    secret = signed_in.post("/api/v1/auth/2fa/setup/").data["secret"]
    signed_in.post("/api/v1/auth/2fa/confirm/", {"code": pyotp.TOTP(secret).now()}, format="json")

    fresh = APIClient()
    challenge = fresh.post(
        "/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json"
    ).data["challenge"]

    response = fresh.post(
        "/api/v1/auth/login/2fa/", {"challenge": challenge, "code": "000000"}, format="json"
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_recovery_code_works_once(signed_in, user):
    secret = signed_in.post("/api/v1/auth/2fa/setup/").data["secret"]
    codes = signed_in.post(
        "/api/v1/auth/2fa/confirm/", {"code": pyotp.TOTP(secret).now()}, format="json"
    ).data["recovery_codes"]

    device = TwoFactorDevice.objects.get(user=user)
    assert device.consume_recovery_code(codes[0]) is True
    assert device.consume_recovery_code(codes[0]) is False


@pytest.mark.django_db
def test_admin_accounts_cannot_disable_two_factor(signed_in, user):
    secret = signed_in.post("/api/v1/auth/2fa/setup/").data["secret"]
    signed_in.post("/api/v1/auth/2fa/confirm/", {"code": pyotp.TOTP(secret).now()}, format="json")

    user.admin_role = User.AdminRole.MODERATOR
    user.save(update_fields=["admin_role"])

    response = signed_in.post(
        "/api/v1/auth/2fa/disable/", {"code": pyotp.TOTP(secret).now()}, format="json"
    )
    assert response.status_code == 403
    assert response.data["code"] == "two_factor_mandatory"


# --- Passwords -------------------------------------------------------------


@pytest.mark.django_db
def test_password_reset_does_not_reveal_whether_an_account_exists(client, user):
    known = client.post("/api/v1/auth/password/reset/", {"email": user.email}, format="json")
    unknown = client.post(
        "/api/v1/auth/password/reset/", {"email": "nobody@example.com"}, format="json"
    )
    assert known.status_code == unknown.status_code == 200
    assert known.data == unknown.data


@pytest.mark.django_db
def test_password_reset_completes_and_terminates_every_session(client, user):
    client.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")
    _, raw = SecurityToken.issue(user, SecurityToken.Purpose.PASSWORD_RESET)

    response = APIClient().post(
        "/api/v1/auth/password/reset/confirm/",
        {"email": user.email, "token": raw, "password": "an-entirely-new-passphrase"},
        format="json",
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("an-entirely-new-passphrase")
    assert not RefreshSession.objects.filter(user=user, revoked_at__isnull=True).exists()


@pytest.mark.django_db
def test_a_reset_token_cannot_be_used_twice(client, user):
    _, raw = SecurityToken.issue(user, SecurityToken.Purpose.PASSWORD_RESET)
    body = {"email": user.email, "token": raw, "password": "an-entirely-new-passphrase"}

    endpoint = "/api/v1/auth/password/reset/confirm/"
    assert client.post(endpoint, body, format="json").status_code == 200
    assert client.post(endpoint, body, format="json").status_code == 400


@pytest.mark.django_db
def test_otp_is_burned_after_five_failed_attempts(user):
    SecurityToken.issue(user, SecurityToken.Purpose.PHONE_OTP, digits=6)
    for _ in range(SecurityToken.MAX_ATTEMPTS):
        assert SecurityToken.consume(user, SecurityToken.Purpose.PHONE_OTP, "000000") is False

    token = SecurityToken.objects.filter(user=user).latest("created_at")
    assert token.is_usable is False


# --- Verification and the profile gate -------------------------------------


@pytest.mark.django_db
def test_email_confirmation_marks_the_address_verified(client, user):
    _, raw = SecurityToken.issue(user, SecurityToken.Purpose.EMAIL_VERIFY)

    response = client.post(
        "/api/v1/auth/email/confirm/", {"email": user.email, "token": raw}, format="json"
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.email_verified


@pytest.mark.django_db
def test_setting_a_phone_number_issues_an_otp_and_clears_verification(signed_in, user):
    user.phone_verified = True
    user.save(update_fields=["phone_verified"])

    response = signed_in.post(
        "/api/v1/auth/phone/", {"phone_number": "+923001234567"}, format="json"
    )

    assert response.status_code == 200
    # The code itself is never returned by the API.
    assert "code" not in response.data
    assert SecurityToken.objects.filter(
        user=user, purpose=SecurityToken.Purpose.PHONE_OTP, used_at__isnull=True
    ).exists()

    user.refresh_from_db()
    # Changing the number must drop the old verification, not carry it over.
    assert user.phone_number == "+923001234567"
    assert user.phone_verified is False


@pytest.mark.django_db
def test_phone_is_verified_with_the_issued_code(signed_in, user):
    # Issue the token directly: it is stored hashed, so this is the only way to
    # hold the plaintext the SMS would have carried.
    _, code = SecurityToken.issue(
        user, SecurityToken.Purpose.PHONE_OTP, destination="+923001234567", digits=6
    )

    assert (
        signed_in.post("/api/v1/auth/phone/verify/", {"code": code}, format="json").status_code
        == 200
    )

    user.refresh_from_db()
    assert user.phone_verified is True


@pytest.mark.django_db
def test_phone_verification_rejects_a_wrong_code(signed_in, user):
    SecurityToken.issue(user, SecurityToken.Purpose.PHONE_OTP, digits=6)

    response = signed_in.post("/api/v1/auth/phone/verify/", {"code": "000000"}, format="json")

    assert response.status_code == 400
    user.refresh_from_db()
    assert user.phone_verified is False


@pytest.mark.django_db
def test_profile_completion_gate(user):
    """Browsing is always allowed; transacting is not, until all three pass."""
    assert user.can_transact is False
    assert set(user.missing_profile_requirements()) == {"email", "phone", "identity"}

    user.email_verified = True
    user.phone_verified = True
    user.save()
    assert user.can_transact is False  # Identity is still outstanding.

    user.identity_status = VerificationStatus.VERIFIED
    user.save()
    assert user.can_transact is True
    assert user.missing_profile_requirements() == []


@pytest.mark.django_db
def test_me_reports_what_is_still_missing(signed_in):
    response = signed_in.get("/api/v1/auth/me/")
    assert response.data["can_transact"] is False
    assert set(response.data["missing_requirements"]) == {"email", "phone", "identity"}
    assert 0 <= response.data["profile_strength"] <= 100


# --- Universities ----------------------------------------------------------


@pytest.mark.django_db
def test_email_domain_matches_a_university_including_subdomains():
    university = University.objects.create(name="COMSATS", short_code="CUI")
    ApprovedEmailDomain.objects.create(university=university, domain="cuiatd.edu.pk")

    assert ApprovedEmailDomain.match("student@cuiatd.edu.pk") == university
    # A departmental subdomain resolves without its own record.
    assert ApprovedEmailDomain.match("student@cs.cuiatd.edu.pk") == university
    assert ApprovedEmailDomain.match("someone@gmail.com") is None


@pytest.mark.django_db
def test_university_lookup_endpoint(client):
    university = University.objects.create(name="FAST", short_code="FAST")
    ApprovedEmailDomain.objects.create(university=university, domain="nu.edu.pk")

    matched = client.get("/api/v1/auth/universities/lookup/?email=me@nu.edu.pk")
    assert matched.data["matched"] is True
    assert matched.data["university"]["short_code"] == "FAST"

    unmatched = client.get("/api/v1/auth/universities/lookup/?email=me@gmail.com")
    assert unmatched.data["matched"] is False


# --- Profile visibility ----------------------------------------------------


@pytest.mark.django_db
def test_private_profiles_are_not_served(client, user):
    user.profile_visibility = User.Visibility.PRIVATE
    user.save()
    assert client.get(f"/api/v1/auth/users/{user.handle}/").status_code == 404


@pytest.mark.django_db
def test_platform_only_profiles_require_sign_in(client, user):
    user.profile_visibility = User.Visibility.PLATFORM
    user.save()
    assert client.get(f"/api/v1/auth/users/{user.handle}/").status_code == 401


@pytest.mark.django_db
def test_public_profile_never_exposes_contact_details(client, user):
    user.phone_number = "+923001234567"
    user.save()

    response = client.get(f"/api/v1/auth/users/{user.handle}/")

    assert response.status_code == 200
    assert "email" not in response.data
    assert "phone_number" not in response.data
