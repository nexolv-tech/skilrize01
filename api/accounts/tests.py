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
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import (
    ApprovedEmailDomain,
    RefreshSession,
    SecurityToken,
    StudentVerification,
    TwoFactorDevice,
    University,
    User,
    VerificationStatus,
)

PASSWORD = "Correct-Horse9-Battery"


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


@pytest.mark.parametrize(
    ("password", "why"),
    [
        ("Sh0rt-Aa", "under the 12-character floor"),
        ("noupperca5e-here", "no uppercase letter"),
        ("NOLOWERCA5E-HERE", "no lowercase letter"),
        ("No-Digits-Anywhere", "no digit"),
        ("NoSymbolsAnywhere9", "no symbol"),
        ("Passw0rd-Aaaa-Bb", "four repeated characters"),
        ("Passw0rd-abcd-Bb", "an alphabetical run"),
        ("Passw0rd-qwer-Bb", "a keyboard walk"),
    ],
)
@pytest.mark.django_db
def test_signup_rejects_passwords_failing_the_policy(client, password, why):
    response = client.post(
        "/api/v1/auth/signup/",
        {"email": "policy@example.com", "password": password},
        format="json",
    )
    assert response.status_code == 400, f"should have been rejected: {why}"
    assert not User.objects.filter(email="policy@example.com").exists()


@pytest.mark.django_db
def test_signup_accepts_a_password_meeting_every_rule(client):
    response = client.post(
        "/api/v1/auth/signup/",
        {"email": "strong@example.com", "password": "Tr0ubled-Marlin!Sky"},
        format="json",
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_signup_sends_email_confirmation(client):
    mail.outbox.clear()
    client.post(
        "/api/v1/auth/signup/",
        {"email": "confirm@example.com", "password": PASSWORD},
        format="json",
    )
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_signup_is_throttled_at_the_named_scope_rate():
    """Regression test for a real bug (D37): the `throttled("signup")`
    decorator used to set `throttle_scope` on the pre-wrap function, which
    `@api_view` never copies onto the view it builds — so this rate was a
    silent no-op and only the blanket anon rate ever applied.
    `DEFAULT_THROTTLE_RATES["signup"]` is 5/hour in production; the suite's
    own `_generous_scoped_throttles` fixture (`conftest.py`) widens it so
    the rest of the suite can re-authenticate freely, so this test sets it
    back to the real, shipped value before asserting on it — otherwise it
    would only prove the *widened* test rate works, not the real one. The
    6th signup from the same address in the same window must be rejected
    before it ever reaches the database.

    Mutated in place on `SimpleRateThrottle.THROTTLE_RATES`, not via the
    `settings` fixture — see `_generous_scoped_throttles` in `conftest.py`
    for why a `settings.REST_FRAMEWORK = ...` reassignment silently does not
    reach what the throttle actually reads. `_generous_scoped_throttles`
    restores the surrounding dict on teardown regardless of what this test
    sets mid-run.

    A fresh `APIClient` per call, deliberately — signup itself signs the
    caller in and sets an auth cookie, so reusing one client across calls
    would make each later request authenticate as the account the previous
    call just created. `ScopedRateThrottle` keys an authenticated request by
    user id, not address, so that would throttle five different one-request
    budgets instead of exercising the shared anonymous bucket a real spam
    script — one that does not carry a session forward — would actually hit.
    """
    from rest_framework.throttling import SimpleRateThrottle

    SimpleRateThrottle.THROTTLE_RATES["signup"] = "5/hour"

    for i in range(5):
        response = APIClient().post(
            "/api/v1/auth/signup/",
            {"email": f"throttle{i}@example.com", "password": PASSWORD},
            format="json",
        )
        assert response.status_code == 201

    sixth = APIClient().post(
        "/api/v1/auth/signup/",
        {"email": "throttle5@example.com", "password": PASSWORD},
        format="json",
    )
    assert sixth.status_code == 429
    assert not User.objects.filter(email="throttle5@example.com").exists()


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
def test_the_csrf_endpoint_returns_the_token_in_the_body(client):
    """A web client on a different domain than the API (D44's free
    Render+Vercel deployment) can never read `document.cookie` for a
    cookie the API's own domain set — only the response body works
    regardless of deployment topology, so that's what the client reads
    from. Caught live rather than by a test until now; see D45."""
    response = client.get("/api/v1/auth/csrf/")
    assert response.status_code == 200
    assert isinstance(response.data["csrfToken"], str)
    assert len(response.data["csrfToken"]) > 0


@pytest.mark.django_db
def test_an_unsafe_cookie_authenticated_request_needs_the_csrf_header(user):
    """The `client` fixture's default APIClient() never actually enforces
    CSRF (Django's test client bypasses it unless told not to), so the
    bug this fix closes — a client that cannot read the csrftoken cookie
    back off document.cookie stays permanently unable to make a second
    authenticated write — could pass every existing test while being
    completely broken live. A client built with enforce_csrf_checks=True
    exercises the real path CookieJWTAuthentication._enforce_csrf runs."""
    client = APIClient(enforce_csrf_checks=True)
    client.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")

    # The access cookie is now set, so this write is cookie-authenticated —
    # and refused without a CSRF header, the same refusal a client that
    # could never read the cookie back would hit on every write, forever.
    response = client.post("/api/v1/auth/logout/")
    assert response.status_code == 403
    assert "CSRF" in response.data["detail"]

    # The token straight from the /csrf/ response body — not read back off
    # a cookie — is what actually unblocks it.
    token = client.get("/api/v1/auth/csrf/").data["csrfToken"]
    response = client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200


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
def test_repeated_failures_lock_the_account(client, user, settings):
    settings.LOGIN_MAX_ATTEMPTS = 3

    for _ in range(3):
        rejected = client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "wrong-guess-here"},
            format="json",
        )
        assert rejected.status_code == 401

    locked = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "wrong-guess-here"},
        format="json",
    )
    assert locked.status_code == 429
    assert locked.data["code"] == "account_locked"
    assert locked["Retry-After"]

    # The lock holds even once the caller starts guessing correctly, which is
    # the whole point — otherwise the budget bounds nothing.
    still_locked = client.post(
        "/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json"
    )
    assert still_locked.status_code == 429


@pytest.mark.django_db
def test_a_successful_login_clears_the_failure_count(client, user, settings):
    settings.LOGIN_MAX_ATTEMPTS = 3

    client.post(
        "/api/v1/auth/login/", {"email": user.email, "password": "wrong-guess"}, format="json"
    )
    client.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")

    # Two more failures would trip a counter that had not been reset.
    for _ in range(2):
        response = client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "wrong-guess"},
            format="json",
        )
        assert response.status_code == 401


@pytest.mark.django_db
def test_lockout_applies_to_unknown_addresses_too(client, settings):
    """Otherwise the lockout response itself enumerates accounts."""
    settings.LOGIN_MAX_ATTEMPTS = 2

    for _ in range(2):
        client.post(
            "/api/v1/auth/login/",
            {"email": "nobody@example.com", "password": "guessing"},
            format="json",
        )

    response = client.post(
        "/api/v1/auth/login/",
        {"email": "nobody@example.com", "password": "guessing"},
        format="json",
    )
    assert response.status_code == 429


@pytest.mark.django_db
def test_one_address_spraying_many_accounts_is_blocked(client, settings):
    """The attack the per-account budget cannot see.

    Ten guesses spread across ten different accounts never trips any single
    account's counter, so without a per-address budget it is unbounded.
    """
    settings.LOGIN_IP_MAX_FAILURES = 5
    settings.LOGIN_MAX_ATTEMPTS = 50  # high enough that only the IP rule fires

    for index in range(5):
        response = client.post(
            "/api/v1/auth/login/",
            {"email": f"victim{index}@example.com", "password": "one-guess-each"},
            format="json",
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/v1/auth/login/",
        {"email": "victim99@example.com", "password": "one-guess-each"},
        format="json",
    )
    assert blocked.status_code == 429
    assert blocked.data["code"] == "ip_blocked"


@pytest.mark.django_db
def test_an_address_block_outranks_valid_credentials(client, user, settings):
    settings.LOGIN_IP_MAX_FAILURES = 2
    settings.LOGIN_MAX_ATTEMPTS = 50

    for _ in range(2):
        client.post(
            "/api/v1/auth/login/",
            {"email": "someone@example.com", "password": "guessing"},
            format="json",
        )

    response = client.post(
        "/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 429
    assert response.data["code"] == "ip_blocked"


# --- Student verification --------------------------------------------------


@pytest.fixture
def comsats(db):
    from accounts.models import ApprovedEmailDomain

    uni = University.objects.create(name="COMSATS University", short_code="CUI")
    ApprovedEmailDomain.objects.create(university=uni, domain="cuiatd.edu.pk")
    return uni


def _emailed_otp() -> str:
    import re

    match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
    assert match, f"no code in: {mail.outbox[-1].body!r}"
    return match.group(1)


@pytest.mark.django_db
def test_the_code_goes_to_the_claimed_address_not_the_account(signed_in, user, comsats):
    """Sending it to the account address would prove nothing about the claim."""
    mail.outbox.clear()
    response = signed_in.post(
        "/api/v1/auth/student/email/",
        {"university_email": "fa21-bcs-001@cuiatd.edu.pk"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["application"]["status"] == "email_pending"
    assert mail.outbox[-1].to == ["fa21-bcs-001@cuiatd.edu.pk"]
    assert mail.outbox[-1].to != [user.email]


@pytest.mark.django_db
def test_an_unknown_domain_is_refused(signed_in, comsats):
    response = signed_in.post(
        "/api/v1/auth/student/email/", {"university_email": "me@gmail.com"}, format="json"
    )
    assert response.status_code == 400
    assert response.data["code"] == "unknown_university_domain"


@pytest.mark.django_db
def test_the_full_verification_journey_opens_the_portal(signed_in, user, comsats):
    from accounts.models import StudentVerification

    mail.outbox.clear()
    signed_in.post(
        "/api/v1/auth/student/email/",
        {"university_email": "fa21-bcs-001@cuiatd.edu.pk"},
        format="json",
    )

    confirmed = signed_in.post(
        "/api/v1/auth/student/email/verify/", {"code": _emailed_otp()}, format="json"
    )
    assert confirmed.status_code == 200
    # COMSATS requires an ID card, so email alone is not enough.
    assert confirmed.data["application"]["next_step"] == "upload_id_card"

    user.refresh_from_db()
    assert not user.is_verified_student, "a portal must not open before review"

    application = StudentVerification.objects.get(user=user)
    application.approve()

    user.refresh_from_db()
    assert user.is_verified_student
    assert user.university_id == comsats.pk

    surfaces = signed_in.get("/api/v1/auth/me/").data["surfaces"]
    assert [s["kind"] for s in surfaces] == ["global", "university"]


@pytest.mark.django_db
def test_a_wrong_code_does_not_advance_the_application(signed_in, comsats):
    signed_in.post(
        "/api/v1/auth/student/email/",
        {"university_email": "fa21-bcs-001@cuiatd.edu.pk"},
        format="json",
    )
    response = signed_in.post(
        "/api/v1/auth/student/email/verify/", {"code": "000000"}, format="json"
    )
    assert response.status_code == 400
    assert response.data["code"] == "invalid_code"


@pytest.mark.django_db
def test_a_university_address_cannot_be_claimed_by_two_accounts(client, signed_in, comsats):
    signed_in.post(
        "/api/v1/auth/student/email/",
        {"university_email": "shared@cuiatd.edu.pk"},
        format="json",
    )

    other = User.objects.create_user("other@example.com", PASSWORD)
    client.post("/api/v1/auth/login/", {"email": other.email, "password": PASSWORD}, format="json")
    response = client.post(
        "/api/v1/auth/student/email/",
        {"university_email": "shared@cuiatd.edu.pk"},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["code"] == "email_taken"


@pytest.mark.django_db
def test_an_id_card_cannot_be_uploaded_before_the_email_is_confirmed(signed_in, comsats):
    from django.core.files.uploadedfile import SimpleUploadedFile

    signed_in.post(
        "/api/v1/auth/student/email/",
        {"university_email": "fa21-bcs-001@cuiatd.edu.pk"},
        format="json",
    )
    response = signed_in.post(
        "/api/v1/auth/student/id-card/",
        {"file": SimpleUploadedFile("card.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")},
        format="multipart",
    )
    assert response.status_code == 400
    assert response.data["code"] == "email_not_verified"


@pytest.mark.django_db
def test_a_university_that_waives_the_card_skips_that_step(signed_in, user, comsats):
    comsats.require_id_card = False
    comsats.save(update_fields=["require_id_card"])

    mail.outbox.clear()
    signed_in.post(
        "/api/v1/auth/student/email/",
        {"university_email": "fa21-bcs-001@cuiatd.edu.pk"},
        format="json",
    )
    confirmed = signed_in.post(
        "/api/v1/auth/student/email/verify/", {"code": _emailed_otp()}, format="json"
    )
    assert confirmed.data["application"]["next_step"] == "wait_for_review"


@pytest.mark.django_db
def test_surfaces_lists_only_global_for_a_non_student(signed_in):
    assert [s["kind"] for s in signed_in.get("/api/v1/auth/me/").data["surfaces"]] == ["global"]


# --- New-device email verification -----------------------------------------


def _emailed_code() -> str:
    """Pull the six-digit code out of the most recent email."""
    import re

    match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
    assert match, f"no six-digit code in: {mail.outbox[-1].body!r}"
    return match.group(1)


@pytest.fixture
def verifying(settings):
    """Turn the emailed new-device check back on for one test."""
    settings.REQUIRE_NEW_DEVICE_VERIFICATION = True
    return settings


@pytest.mark.django_db
def test_a_new_device_without_2fa_must_pass_an_emailed_code(client, user, verifying):
    mail.outbox.clear()

    first = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
        HTTP_USER_AGENT="Mozilla/5.0 (UnknownMachine)",
    )

    # A correct password alone does not produce a session.
    assert first.status_code == 200
    assert first.data["device_verification_required"] is True
    assert "skilrize_access" not in first.cookies
    assert len(mail.outbox) == 1
    # The address is hinted, never echoed in full.
    assert first.data["sent_to"].endswith("@example.com")
    assert user.email not in first.data["sent_to"]

    second = client.post(
        "/api/v1/auth/login/device/",
        {"challenge": first.data["challenge"], "code": _emailed_code()},
        format="json",
        HTTP_USER_AGENT="Mozilla/5.0 (UnknownMachine)",
    )
    assert second.status_code == 200
    assert second.cookies["skilrize_access"]


@pytest.mark.django_db
def test_a_recognised_device_skips_the_emailed_code(client, user, verifying):
    agent = "Mozilla/5.0 (TheUsualLaptop)"
    first = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
        HTTP_USER_AGENT=agent,
    )
    client.post(
        "/api/v1/auth/login/device/",
        {"challenge": first.data["challenge"], "code": _emailed_code()},
        format="json",
        HTTP_USER_AGENT=agent,
    )

    # Second sign-in from the same device: straight through, no code.
    again = APIClient()
    response = again.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
        HTTP_USER_AGENT=agent,
    )
    assert response.status_code == 200
    assert "device_verification_required" not in response.data
    assert response.cookies["skilrize_access"]


@pytest.mark.django_db
def test_a_wrong_emailed_code_yields_no_session(client, user, verifying):
    first = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
        HTTP_USER_AGENT="Mozilla/5.0 (UnknownMachine)",
    )

    response = client.post(
        "/api/v1/auth/login/device/",
        {"challenge": first.data["challenge"], "code": "000000"},
        format="json",
    )
    assert response.status_code == 401
    assert "skilrize_access" not in response.cookies


@pytest.mark.django_db
def test_an_account_with_2fa_gets_the_authenticator_not_an_email(client, user, verifying):
    """The two paths are mutually exclusive, and 2FA wins.

    An enrolled account must never be admitted by an email code — that would
    quietly downgrade its second factor to whatever the inbox is worth.
    """
    device = TwoFactorDevice.objects.create(
        user=user, secret=pyotp.random_base32(), confirmed_at=timezone.now()
    )
    mail.outbox.clear()

    response = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
        HTTP_USER_AGENT="Mozilla/5.0 (UnknownMachine)",
    )

    assert response.data["two_factor_required"] is True
    assert "device_verification_required" not in response.data
    assert mail.outbox == []

    # And the 2FA challenge cannot be redeemed at the email-code endpoint.
    crossover = client.post(
        "/api/v1/auth/login/device/",
        {"challenge": response.data["challenge"], "code": pyotp.TOTP(device.secret).now()},
        format="json",
    )
    assert crossover.status_code == 400
    assert crossover.data["code"] == "invalid_challenge"


@pytest.mark.django_db
def test_emailed_codes_are_single_use(client, user, verifying):
    first = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
        HTTP_USER_AGENT="Mozilla/5.0 (UnknownMachine)",
    )
    code = _emailed_code()
    challenge = first.data["challenge"]

    assert (
        client.post(
            "/api/v1/auth/login/device/",
            {"challenge": challenge, "code": code},
            format="json",
            HTTP_USER_AGENT="Mozilla/5.0 (UnknownMachine)",
        ).status_code
        == 200
    )

    replay = APIClient().post(
        "/api/v1/auth/login/device/",
        {"challenge": challenge, "code": code},
        format="json",
        HTTP_USER_AGENT="Mozilla/5.0 (SomewhereElse)",
    )
    assert replay.status_code == 401


# --- New-device cool-off ---------------------------------------------------


@pytest.mark.django_db
def test_signing_in_records_the_device_and_reports_the_hold(client, user, settings):
    from accounts.models import KnownDevice

    settings.DEVICE_COOLOFF_SECONDS = 7200

    response = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
        HTTP_USER_AGENT="Mozilla/5.0 (TestDevice)",
    )

    assert response.status_code == 200
    assert response.data["device_cooloff_seconds"] > 0
    assert KnownDevice.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_a_returning_device_is_not_held_again(client, user, settings):
    from accounts.models import KnownDevice

    settings.DEVICE_COOLOFF_SECONDS = 7200
    agent = "Mozilla/5.0 (TestDevice)"

    for _ in range(2):
        client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": PASSWORD},
            format="json",
            HTTP_USER_AGENT=agent,
        )

    # Same fingerprint, so one row and one alert — not one per sign-in.
    assert KnownDevice.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_a_new_device_alerts_the_owner(client, user, settings):
    from core.models import Notification, NotificationCategory

    settings.DEVICE_COOLOFF_SECONDS = 7200

    client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
        HTTP_USER_AGENT="Mozilla/5.0 (UnfamiliarDevice)",
    )

    alert = Notification.objects.filter(user=user, category=NotificationCategory.SECURITY).first()
    assert alert is not None
    assert alert.data["kind"] == "new_device"


@pytest.mark.django_db
def test_a_device_in_cooloff_may_browse_but_not_transact(client, settings):
    """The shape of the control: read everything, move nothing."""
    from marketplace.models import Category

    settings.DEVICE_COOLOFF_SECONDS = 7200

    account = User.objects.create_user("trader@example.com", PASSWORD, full_name="Trader")
    account.email_verified = True
    account.phone_verified = True
    account.identity_status = VerificationStatus.VERIFIED
    account.save()
    assert account.can_transact

    client.post(
        "/api/v1/auth/login/",
        {"email": account.email, "password": PASSWORD},
        format="json",
        HTTP_USER_AGENT="Mozilla/5.0 (BrandNewDevice)",
    )

    # Browsing is untouched.
    assert client.get("/api/v1/projects/").status_code == 200

    category = Category.objects.create(name="Development & IT", slug="development-it")
    blocked = client.post(
        "/api/v1/projects/",
        {
            "title": "A project posted from a brand new device",
            "description": "x" * 120,
            "category": category.pk,
            "project_type": "fixed",
            "budget_min": "10000",
            "budget_max": "20000",
        },
        format="json",
    )
    assert blocked.status_code == 403
    assert blocked.data["code"] == "device_cooloff"


@pytest.mark.django_db
def test_transactions_unlock_once_the_hold_expires(client, settings):
    from accounts.models import KnownDevice

    settings.DEVICE_COOLOFF_SECONDS = 7200

    account = User.objects.create_user("patient@example.com", PASSWORD, full_name="Patient")
    account.email_verified = True
    account.phone_verified = True
    account.identity_status = VerificationStatus.VERIFIED
    account.save()

    client.post(
        "/api/v1/auth/login/",
        {"email": account.email, "password": PASSWORD},
        format="json",
        HTTP_USER_AGENT="Mozilla/5.0 (PatientDevice)",
    )

    # Wind the clock forward rather than sleeping for two hours.
    KnownDevice.objects.filter(user=account).update(trusted_at=timezone.now())

    response = client.get("/api/v1/proposals/quota/")
    assert response.status_code == 200


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


# --- Native (bearer) clients — Phase 7 / D38 --------------------------------


@pytest.mark.django_db
def test_a_browser_login_never_puts_tokens_in_the_body(client, user):
    """The web client authenticates by HttpOnly cookie precisely so that
    script running in the page cannot read a token. Putting them in the body
    unconditionally would hand that back."""
    response = client.post(
        "/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json"
    )

    assert response.status_code == 200
    assert "access" not in response.data
    assert "refresh" not in response.data
    assert "skilrize_access" in response.cookies


@pytest.mark.django_db
def test_a_native_client_gets_bearer_tokens_it_can_actually_use(user):
    """`CookieJWTAuthentication` has documented a bearer path since Phase 0,
    but nothing ever handed a non-browser client a token to send with it."""
    native = APIClient(HTTP_X_SKILRIZE_CLIENT="native")

    login = native.post(
        "/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json"
    )
    assert login.status_code == 200
    assert login.data["access"] and login.data["refresh"]

    # A completely fresh client, no cookies at all, authenticating purely on
    # the bearer token — the thing a phone actually does.
    bearer = APIClient()
    bearer.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    me = bearer.get("/api/v1/auth/me/")

    assert me.status_code == 200
    assert me.data["email"] == user.email


@pytest.mark.django_db
def test_refresh_returns_tokens_only_to_a_caller_that_supplied_one(client, user):
    """The rule that keeps this endpoint from becoming an exfiltration route:
    the rotated pair comes back in the body only when the *old* one arrived
    in the body. Script in a browser cannot read the HttpOnly refresh cookie,
    so it can never satisfy that — and a cookie-authenticated refresh keeps
    answering with cookies alone."""
    native = APIClient(HTTP_X_SKILRIZE_CLIENT="native")
    login = native.post(
        "/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json"
    )

    from_body = APIClient().post(
        "/api/v1/auth/refresh/", {"refresh": login.data["refresh"]}, format="json"
    )
    assert from_body.status_code == 200
    assert from_body.data["access"] and from_body.data["refresh"]

    # The browser path: token in the cookie, nothing in the body, and no
    # amount of asking changes that.
    client.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")
    from_cookie = client.post("/api/v1/auth/refresh/", HTTP_X_SKILRIZE_CLIENT="native")

    assert from_cookie.status_code == 200
    assert "access" not in from_cookie.data
    assert "refresh" not in from_cookie.data


@pytest.mark.django_db
def test_a_native_client_can_actually_revoke_its_session_on_sign_out(user):
    native = APIClient(HTTP_X_SKILRIZE_CLIENT="native")
    login = native.post(
        "/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json"
    )
    refresh_token = login.data["refresh"]

    logout = APIClient().post("/api/v1/auth/logout/", {"refresh": refresh_token}, format="json")
    assert logout.status_code == 200

    # The revoked token is dead, not merely forgotten by the client.
    replay = APIClient().post("/api/v1/auth/refresh/", {"refresh": refresh_token}, format="json")
    assert replay.status_code == 401
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
def test_setup_reuses_the_pending_secret_across_calls(signed_in, user):
    """Enrolment must survive the endpoint being called more than once.

    The client begins enrolment from an effect, and React runs effects twice in
    development. When setup minted a fresh secret per call, the second one
    replaced the secret behind the QR the first had already rendered — so a
    correctly scanned code was rejected as invalid. Any remount or second click
    did the same thing in production.
    """
    first = signed_in.post("/api/v1/auth/2fa/setup/")
    second = signed_in.post("/api/v1/auth/2fa/setup/")
    assert first.status_code == second.status_code == 200
    assert first.data["secret"] == second.data["secret"]

    # The code from the QR the user actually scanned still enrols them.
    code = pyotp.TOTP(first.data["secret"]).now()
    confirmed = signed_in.post("/api/v1/auth/2fa/confirm/", {"code": code}, format="json")
    assert confirmed.status_code == 200

    user.refresh_from_db()
    assert user.has_two_factor


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


# --- Admin self-enrolment at login (D37) ------------------------------------


@pytest.fixture
def unenrolled_admin(db):
    """An admin account before it has ever touched 2FA — the exact state
    that was previously an unrecoverable dead end (DECISIONS.md's
    "an admin cannot enrol 2FA through the product")."""
    return User.objects.create_user(
        "newadmin@example.com", PASSWORD, admin_role=User.AdminRole.SUPPORT_AGENT
    )


@pytest.mark.django_db
def test_login_issues_an_enrolment_challenge_for_an_unenrolled_admin(unenrolled_admin):
    response = APIClient().post(
        "/api/v1/auth/login/",
        {"email": unenrolled_admin.email, "password": PASSWORD},
        format="json",
    )
    # 200, not an error status — same as the sibling `two_factor_required`/
    # `device_verification_required` challenges: an actionable next step for
    # the frontend to branch on, not a terminal failure.
    assert response.status_code == 200
    assert response.data["two_factor_enrolment_required"] is True
    assert response.data["challenge"]


@pytest.mark.django_db
def test_an_unenrolled_admin_can_enrol_and_end_up_signed_in(unenrolled_admin):
    """The full path this phase closed: password → enrolment challenge →
    scan the QR → confirm the code → signed in, no separate second login."""
    anon = APIClient()
    challenge = anon.post(
        "/api/v1/auth/login/",
        {"email": unenrolled_admin.email, "password": PASSWORD},
        format="json",
    ).data["challenge"]

    setup = anon.post(
        "/api/v1/auth/login/2fa/enrol/setup/", {"challenge": challenge}, format="json"
    )
    assert setup.status_code == 200
    secret = setup.data["secret"]

    confirm = anon.post(
        "/api/v1/auth/login/2fa/enrol/confirm/",
        {"challenge": challenge, "code": pyotp.TOTP(secret).now()},
        format="json",
    )
    assert confirm.status_code == 200
    assert confirm.data["user"]["email"] == unenrolled_admin.email
    assert len(confirm.data["recovery_codes"]) > 0
    assert "skilrize_access" in confirm.cookies

    device = TwoFactorDevice.objects.get(user=unenrolled_admin)
    assert device.confirmed_at is not None

    # Actually signed in, not just told it worked.
    me = anon.get("/api/v1/auth/me/")
    assert me.status_code == 200
    assert me.data["email"] == unenrolled_admin.email


@pytest.mark.django_db
def test_enrolment_confirm_rejects_a_bad_code(unenrolled_admin):
    anon = APIClient()
    challenge = anon.post(
        "/api/v1/auth/login/",
        {"email": unenrolled_admin.email, "password": PASSWORD},
        format="json",
    ).data["challenge"]
    anon.post("/api/v1/auth/login/2fa/enrol/setup/", {"challenge": challenge}, format="json")

    response = anon.post(
        "/api/v1/auth/login/2fa/enrol/confirm/",
        {"challenge": challenge, "code": "000000"},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "invalid_code"
    assert not TwoFactorDevice.objects.filter(
        user=unenrolled_admin, confirmed_at__isnull=False
    ).exists()


@pytest.mark.django_db
def test_a_normal_two_factor_challenge_cannot_be_redeemed_as_an_enrolment(client, signed_in, user):
    """The `enrol` flag is what stops a stolen mid-login 2FA challenge from
    being replayed against the enrolment endpoints instead — they are
    intentionally not interchangeable."""
    secret = signed_in.post("/api/v1/auth/2fa/setup/").data["secret"]
    signed_in.post("/api/v1/auth/2fa/confirm/", {"code": pyotp.TOTP(secret).now()}, format="json")

    ordinary_challenge = (
        APIClient()
        .post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")
        .data["challenge"]
    )

    response = APIClient().post(
        "/api/v1/auth/login/2fa/enrol/setup/", {"challenge": ordinary_challenge}, format="json"
    )
    assert response.status_code == 400
    assert response.data["code"] == "invalid_challenge"


@pytest.mark.django_db
def test_enrolment_challenge_cannot_be_redeemed_as_an_ordinary_two_factor_login(unenrolled_admin):
    """The reverse of the test above — an enrolment challenge is not a
    general-purpose "I have a valid challenge for this user" token.
    `login_two_factor` does not need its own explicit `enrol` check to stay
    safe here: an unenrolled account has no confirmed device for
    `verify_second_factor` to check *any* code against, so this fails
    regardless of what is typed — just with a generic "wrong code" rather
    than the more specific "wrong challenge type" the sibling flows use."""
    challenge = (
        APIClient()
        .post(
            "/api/v1/auth/login/",
            {"email": unenrolled_admin.email, "password": PASSWORD},
            format="json",
        )
        .data["challenge"]
    )

    response = APIClient().post(
        "/api/v1/auth/login/2fa/", {"challenge": challenge, "code": "000000"}, format="json"
    )
    assert response.status_code == 401
    assert not User.objects.get(pk=unenrolled_admin.pk).has_two_factor


@pytest.mark.django_db
def test_enrolment_confirm_locks_out_after_repeated_bad_codes(settings, unenrolled_admin):
    settings.LOGIN_MAX_ATTEMPTS = 2
    anon = APIClient()
    challenge = anon.post(
        "/api/v1/auth/login/",
        {"email": unenrolled_admin.email, "password": PASSWORD},
        format="json",
    ).data["challenge"]
    anon.post("/api/v1/auth/login/2fa/enrol/setup/", {"challenge": challenge}, format="json")

    for _ in range(2):
        anon.post(
            "/api/v1/auth/login/2fa/enrol/confirm/",
            {"challenge": challenge, "code": "000000"},
            format="json",
        )

    locked = anon.post(
        "/api/v1/auth/login/2fa/enrol/confirm/",
        {"challenge": challenge, "code": "000000"},
        format="json",
    )
    assert locked.status_code == 429


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
        {"email": user.email, "token": raw, "password": "An-Entirely7-New-Passphrase"},
        format="json",
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("An-Entirely7-New-Passphrase")
    assert not RefreshSession.objects.filter(user=user, revoked_at__isnull=True).exists()


@pytest.mark.django_db
def test_a_reset_token_cannot_be_used_twice(client, user):
    _, raw = SecurityToken.issue(user, SecurityToken.Purpose.PASSWORD_RESET)
    body = {"email": user.email, "token": raw, "password": "An-Entirely7-New-Passphrase"}

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
    # The OTP itself is never returned by the API — only, at most, the
    # machine-readable reason no SMS went out.
    assert response.data.get("code") in (None, "sms_unavailable")
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
def test_profile_completion_gate(user, settings):
    """Browsing is always allowed; transacting is not, until all three pass —
    when an SMS provider makes the phone step possible at all."""
    settings.PHONE_VERIFICATION_REQUIRED = True
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
def test_me_reports_what_is_still_missing(signed_in, settings):
    settings.PHONE_VERIFICATION_REQUIRED = True
    response = signed_in.get("/api/v1/auth/me/")
    assert response.data["can_transact"] is False
    assert set(response.data["missing_requirements"]) == {"email", "phone", "identity"}
    assert 0 <= response.data["profile_strength"] <= 100


@pytest.mark.django_db
def test_without_an_sms_provider_the_phone_is_not_required(user, settings):
    """No SMS provider means no phone code can ever arrive. Requiring one
    anyway locked every production account out of transacting."""
    settings.PHONE_VERIFICATION_REQUIRED = False
    user.email_verified = True
    user.identity_status = VerificationStatus.VERIFIED
    user.save()
    assert user.missing_profile_requirements() == []
    assert user.can_transact is True


@pytest.mark.django_db
def test_production_says_plainly_that_no_sms_was_sent(signed_in, settings):
    settings.DEBUG = False
    settings.ENVIRONMENT = "production"
    response = signed_in.post(
        "/api/v1/auth/phone/", {"phone_number": "+923001234567"}, format="json"
    )
    assert response.status_code == 200
    assert response.data["code"] == "sms_unavailable"
    assert "sent" not in response.data["detail"]


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


# --- Admin console (Phase 9) -------------------------------------------------


def _login(email: str, password: str = PASSWORD) -> APIClient:
    api_client = APIClient()
    api_client.post("/api/v1/auth/login/", {"email": email, "password": password}, format="json")
    return api_client


def _make_admin(email: str, role: str) -> User:
    """An admin account, 2FA already enrolled and confirmed —
    `User.requires_two_factor` is mandatory for every admin role without
    exception, so a plain email+password login for one of these accounts
    always comes back asking for a second factor first. Creating the device
    directly through the ORM only skips the QR-scanning UI; `_login_admin`
    below still completes the real two-step challenge these accounts
    require, so the test exercises the actual enforcement, not a bypass of it."""
    user = User.objects.create_user(email, PASSWORD, admin_role=role)
    secret = pyotp.random_base32()
    TwoFactorDevice.objects.create(user=user, secret=secret, confirmed_at=timezone.now())
    user.raw_totp_secret = secret
    return user


def _login_admin(user: User, password: str = PASSWORD) -> APIClient:
    """Complete the two-step login every admin account requires."""
    api_client = APIClient()
    first = api_client.post(
        "/api/v1/auth/login/", {"email": user.email, "password": password}, format="json"
    )
    assert first.status_code == 200 and first.data.get("two_factor_required"), first.data
    code = pyotp.TOTP(user.raw_totp_secret).now()
    second = api_client.post(
        "/api/v1/auth/login/2fa/",
        {"challenge": first.data["challenge"], "code": code},
        format="json",
    )
    assert second.status_code == 200, second.data
    return api_client


@pytest.fixture
def verification_officer(db):
    return _make_admin("officer@example.com", User.AdminRole.VERIFICATION_OFFICER)


@pytest.fixture
def support_agent(db):
    return _make_admin("support@example.com", User.AdminRole.SUPPORT_AGENT)


@pytest.fixture
def super_admin(db):
    return _make_admin("superadmin@example.com", User.AdminRole.SUPER_ADMIN)


@pytest.fixture
def open_verification(db, user):
    university = University.objects.create(name="COMSATS", short_code="CUI")
    return StudentVerification.objects.create(
        user=user,
        university=university,
        university_email="student@cui.edu.pk",
        status=StudentVerification.Status.UNDER_REVIEW,
    )


@pytest.mark.django_db
def test_admin_endpoints_reject_a_plain_user(user, open_verification):
    api_client = _login(user.email)
    assert api_client.get("/api/v1/auth/admin/verifications/").status_code == 403
    assert api_client.get("/api/v1/auth/admin/users/").status_code == 403
    assert api_client.get("/api/v1/auth/admin/audit-log/").status_code == 403
    assert api_client.get("/api/v1/admin/contracts/").status_code == 403


@pytest.mark.django_db
def test_super_admin_bypasses_every_role_check(super_admin, open_verification):
    api_client = _login_admin(super_admin)
    assert api_client.get("/api/v1/auth/admin/verifications/").status_code == 200
    assert api_client.get("/api/v1/auth/admin/users/").status_code == 200
    assert api_client.get("/api/v1/auth/admin/audit-log/").status_code == 200
    assert api_client.get("/api/v1/admin/contracts/").status_code == 200


@pytest.mark.django_db
def test_a_role_does_not_grant_access_to_other_roles_surfaces(verification_officer):
    """A Verification Officer can review applications but cannot browse the
    audit log or reach contract operations — the roles are not one
    undivided 'is an admin' switch."""
    api_client = _login_admin(verification_officer)
    assert api_client.get("/api/v1/auth/admin/verifications/").status_code == 200
    assert api_client.get("/api/v1/auth/admin/audit-log/").status_code == 403
    assert api_client.get("/api/v1/auth/admin/users/").status_code == 403
    assert api_client.get("/api/v1/admin/contracts/").status_code == 403


@pytest.mark.django_db
def test_approving_a_verification_grants_the_university(
    verification_officer, open_verification, user
):
    api_client = _login_admin(verification_officer)
    response = api_client.post(f"/api/v1/auth/admin/verifications/{open_verification.id}/approve/")
    assert response.status_code == 200
    assert response.data["status"] == "approved"

    user.refresh_from_db()
    assert user.university_id == open_verification.university_id
    assert user.student_verification_status == VerificationStatus.VERIFIED


@pytest.mark.django_db
def test_rejecting_a_verification_requires_a_reason(verification_officer, open_verification, user):
    api_client = _login_admin(verification_officer)
    missing_reason = api_client.post(
        f"/api/v1/auth/admin/verifications/{open_verification.id}/reject/"
    )
    assert missing_reason.status_code == 400

    response = api_client.post(
        f"/api/v1/auth/admin/verifications/{open_verification.id}/reject/",
        {"reason": "ID card photo is unreadable."},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["status"] == "rejected"
    user.refresh_from_db()
    assert user.university_id is None


@pytest.mark.django_db
def test_cannot_decide_an_already_decided_verification(verification_officer, open_verification):
    api_client = _login_admin(verification_officer)
    api_client.post(f"/api/v1/auth/admin/verifications/{open_verification.id}/approve/")

    response = api_client.post(f"/api/v1/auth/admin/verifications/{open_verification.id}/approve/")
    assert response.status_code == 400


@pytest.mark.django_db
def test_support_agent_can_suspend_and_reactivate_a_user(support_agent, user):
    api_client = _login_admin(support_agent)

    suspend = api_client.post(
        f"/api/v1/auth/admin/users/{user.id}/suspend/",
        {"reason": "Reported for a scam attempt."},
        format="json",
    )
    assert suspend.status_code == 200
    user.refresh_from_db()
    assert user.is_active is False

    reactivate = api_client.post(f"/api/v1/auth/admin/users/{user.id}/reactivate/")
    assert reactivate.status_code == 200
    user.refresh_from_db()
    assert user.is_active is True


@pytest.mark.django_db
def test_cannot_suspend_another_admin(support_agent, verification_officer):
    api_client = _login_admin(support_agent)
    response = api_client.post(
        f"/api/v1/auth/admin/users/{verification_officer.id}/suspend/",
        {"reason": "x"},
        format="json",
    )
    assert response.status_code == 400
    verification_officer.refresh_from_db()
    assert verification_officer.is_active is True


@pytest.mark.django_db
def test_user_search_matches_email_and_handle(support_agent, user):
    api_client = _login_admin(support_agent)
    response = api_client.get(f"/api/v1/auth/admin/users/?q={user.handle}")
    assert response.status_code == 200
    assert any(row["id"] == user.id for row in response.data["results"])


@pytest.mark.django_db
def test_audit_log_records_admin_actions_and_is_filterable(support_agent, super_admin, user):
    api_client = _login_admin(support_agent)
    api_client.post(
        f"/api/v1/auth/admin/users/{user.id}/suspend/", {"reason": "test"}, format="json"
    )

    admin_client = _login_admin(super_admin)
    response = admin_client.get("/api/v1/auth/admin/audit-log/?action=update")
    assert response.status_code == 200
    assert any(row["actor_email"] == support_agent.email for row in response.data["results"])
