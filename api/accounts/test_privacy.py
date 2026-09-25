"""
Tests for data-subject rights: accepting the Terms, exporting your data, and
erasing your account.

The export tests guard what leaves the building — a JSON file that sits in
someone's Downloads folder must never carry a password hash or a two-factor
secret. The erasure tests guard the opposite failure: an "erased" account
that still identifies its owner, or one erased mid-transaction so somebody
loses money.
"""

from __future__ import annotations

import json
import time

import pyotp
import pytest
from rest_framework.test import APIClient

from accounts.models import LegalAcceptance, RefreshSession, TwoFactorDevice, User
from core.models import AuditLog
from gigs.tests import GIG_BODY, _order, publish_gig
from marketplace.tests import PASSWORD, make_user, sign_in
from payments.models import PayoutProfile


def _next_code(user) -> str:
    """A TOTP code from the next time-step. Signing in already spent the
    current one, and replay protection rightly refuses it a second time."""
    totp = pyotp.TOTP(user.two_factor.secret)
    return totp.at(int(time.time()) + totp.interval)


# --- Accepting the Terms -------------------------------------------------------


@pytest.mark.django_db
def test_signup_without_accepting_the_terms_is_refused():
    response = APIClient().post(
        "/api/v1/auth/signup/",
        {"email": "hasty@example.com", "password": PASSWORD, "accept_terms": False},
        format="json",
    )
    assert response.status_code == 400
    assert "accept_terms" in response.data
    assert not User.objects.filter(email="hasty@example.com").exists()


@pytest.mark.django_db
def test_signup_records_which_versions_were_accepted(settings):
    response = APIClient().post(
        "/api/v1/auth/signup/",
        {"email": "careful@example.com", "password": PASSWORD, "accept_terms": True},
        format="json",
        HTTP_USER_AGENT="pytest-browser",
    )
    assert response.status_code == 201

    user = User.objects.get(email="careful@example.com")
    accepted = {(row.document, row.version) for row in LegalAcceptance.objects.filter(user=user)}
    assert accepted == {
        ("terms", settings.LEGAL_TERMS_VERSION),
        ("privacy", settings.LEGAL_PRIVACY_VERSION),
    }
    assert LegalAcceptance.objects.filter(user=user, user_agent="pytest-browser").count() == 2


@pytest.mark.django_db
def test_config_publishes_the_current_legal_versions(settings):
    data = APIClient().get("/api/v1/config/").data
    assert data["legal"]["terms_version"] == settings.LEGAL_TERMS_VERSION
    assert data["legal"]["privacy_version"] == settings.LEGAL_PRIVACY_VERSION


# --- Export --------------------------------------------------------------------


@pytest.mark.django_db
def test_export_needs_the_password_again():
    user = make_user("exporter@example.com", two_factor=False)
    response = sign_in(user).post("/api/v1/auth/me/export/", {"password": "wrong"}, format="json")
    assert response.status_code == 403
    assert response.data["code"] == "step_up_failed"


@pytest.mark.django_db
def test_export_contains_the_users_data_and_no_secrets():
    user = make_user("exporter@example.com", full_name="Ayesha Khan")
    PayoutProfile.objects.create(
        user=user,
        bank_name="Meezan Bank",
        account_title="Ayesha Khan",
        account_number="PK36MEZN0001234567890123",
        cnic="3520212345671",
    )

    response = sign_in(user).post(
        "/api/v1/auth/me/export/", {"code": _next_code(user)}, format="json"
    )

    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
    body = response.data
    assert body["account"]["email"] == "exporter@example.com"
    assert body["account"]["full_name"] == "Ayesha Khan"

    payout = body["records"]["payments.payoutprofile (user)"][0]
    assert payout["bank_name"] == "Meezan Bank"
    # Masked, not omitted — and never in full.
    assert payout["account_number"] == "•••• 0123"
    assert payout["cnic"] == "•••• 5671"

    dumped = json.dumps(body, default=str)
    assert "PK36MEZN0001234567890123" not in dumped
    assert "3520212345671" not in dumped
    assert user.two_factor.secret not in dumped
    assert "argon2" not in dumped  # no password hash, in any form
    # Signing in created a session; its token hash is plumbing, not data.
    sessions = body["records"]["accounts.refreshsession (user)"]
    assert sessions and all("token_hash" not in row for row in sessions)

    assert AuditLog.objects.filter(
        actor=user, action=AuditLog.Action.READ_SENSITIVE, justification__icontains="export"
    ).exists()


@pytest.mark.django_db
def test_export_reaches_orders_across_apps():
    seller = make_user("seller@example.com")
    buyer = make_user("buyer@example.com")
    created = sign_in(seller).post("/api/v1/gigs/", GIG_BODY, format="json")
    publish_gig(sign_in(seller), created.data["id"])
    from gigs.models import Gig

    _order(Gig.objects.unscoped().get(pk=created.data["id"]), buyer)

    body = (
        sign_in(buyer)
        .post("/api/v1/auth/me/export/", {"code": _next_code(buyer)}, format="json")
        .data
    )
    assert len(body["records"]["gigs.order (buyer)"]) == 1


# --- Erasure -------------------------------------------------------------------


@pytest.mark.django_db
def test_the_delete_preview_lists_what_is_kept():
    user = make_user("leaving@example.com", two_factor=False)
    data = sign_in(user).get("/api/v1/auth/me/delete/").data
    assert data["blockers"] == []
    assert any("tax" in line for line in data["retained"])


@pytest.mark.django_db
def test_deletion_needs_a_typed_confirmation_and_the_password():
    user = make_user("leaving@example.com", two_factor=False)
    api = sign_in(user)

    unconfirmed = api.post("/api/v1/auth/me/delete/", {"password": PASSWORD}, format="json")
    assert unconfirmed.status_code == 400
    assert unconfirmed.data["code"] == "confirmation_required"

    wrong = api.post(
        "/api/v1/auth/me/delete/", {"password": "nope", "confirm": "DELETE"}, format="json"
    )
    assert wrong.status_code == 403
    user.refresh_from_db()
    assert user.deleted_at is None


@pytest.mark.django_db
def test_an_open_order_blocks_deletion():
    seller = make_user("seller@example.com")
    buyer = make_user("buyer@example.com")
    created = sign_in(seller).post("/api/v1/gigs/", GIG_BODY, format="json")
    publish_gig(sign_in(seller), created.data["id"])
    from gigs.models import Gig

    _order(Gig.objects.unscoped().get(pk=created.data["id"]), buyer)

    response = sign_in(buyer).post(
        "/api/v1/auth/me/delete/", {"code": _next_code(buyer), "confirm": "DELETE"}, format="json"
    )
    assert response.status_code == 409
    assert response.data["code"] == "erasure_blocked"
    assert any("open order" in line for line in response.data["blockers"])
    buyer.refresh_from_db()
    assert buyer.deleted_at is None


@pytest.mark.django_db
def test_deletion_removes_everything_that_identifies_the_person():
    user = make_user("leaving@example.com", full_name="Bilal Ahmed", phone_number="+923001234567")
    PayoutProfile.objects.create(user=user, bank_name="HBL", account_number="1234567890", cnic="1")
    api = sign_in(user)

    response = api.post(
        "/api/v1/auth/me/delete/", {"code": _next_code(user), "confirm": "delete"}, format="json"
    )

    assert response.status_code == 200, response.data
    user.refresh_from_db()
    assert user.deleted_at is not None
    assert not user.is_active
    assert user.full_name == "Deleted user"
    assert user.email.endswith("@erased.invalid")
    assert "leaving" not in user.email and "leaving" not in user.handle
    assert user.phone_number == ""
    assert not user.has_usable_password()
    # Secrets, sessions and payout details are gone outright.
    assert not TwoFactorDevice.objects.filter(user=user).exists()
    assert not RefreshSession.objects.filter(user=user).exists()
    assert not PayoutProfile.objects.filter(user=user).exists()
    # Cookies are cleared, and the old address can no longer sign in.
    assert response.cookies["skilrize_access"].value == ""
    login = APIClient().post(
        "/api/v1/auth/login/",
        {"email": "leaving@example.com", "password": PASSWORD},
        format="json",
    )
    assert login.status_code == 401
    assert AuditLog.objects.filter(
        actor=user, action=AuditLog.Action.DELETE, justification__icontains="Art. 17"
    ).exists()


@pytest.mark.django_db
def test_an_erased_account_cannot_be_reactivated_by_an_admin():
    from accounts.privacy import erase_user

    admin = make_user("root@example.com", is_staff=True, admin_role=User.AdminRole.SUPER_ADMIN)
    user = make_user("gone@example.com", two_factor=False)
    erase_user(user)

    response = sign_in(admin).post(f"/api/v1/auth/admin/users/{user.pk}/reactivate/")
    assert response.status_code == 400
    assert response.data["code"] == "account_erased"


@pytest.mark.django_db
def test_administrators_cannot_erase_themselves():
    admin = make_user("root@example.com", is_staff=True, admin_role=User.AdminRole.SUPER_ADMIN)
    data = sign_in(admin).get("/api/v1/auth/me/delete/").data
    assert any("Administrator" in line for line in data["blockers"])
