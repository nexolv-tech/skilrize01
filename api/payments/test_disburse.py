"""
Tests for paying freelancers and refunding buyers through Swich (D56).

Swich itself is replaced by stand-ins for its four calls, so what is tested
is this side's rules: money goes out only when Swich says so, never twice,
never to an account whose name does not match, and a refusal is left for a
person with Swich's reason rather than retried blindly.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core.models import Notification
from gigs.tests import _active_order
from marketplace.tests import make_user, sign_in

from .disburse import names_agree, send_payout
from .models import Payout, PayoutProfile, Refund
from .swich import SwichError


@pytest.fixture
def payouts_on(settings):
    settings.SWICH_PAYOUTS_ENABLED = True
    settings.SWICH_CLIENT_SECRET = "test-client-secret"  # noqa: S105 — a test fixture
    return settings


def _profile(user, **overrides):
    values = {
        "bank_code": "MEZN",
        "bank_name": "Meezan Bank",
        "account_title": "Seller Khan",
        "account_number": "PK36MEZN0000001234567890",
        "cnic": "3520212345671",
        "msisdn": "03001234567",
    }
    values.update(overrides)
    return PayoutProfile.objects.create(user=user, **values)


def _approve(gig, buyer, seller, capture):
    """Deliver and accept an order; the release queues its payout."""
    order = _active_order(gig, buyer)
    sign_in(seller).post(f"/api/v1/orders/{order.pk}/deliver/", {"note": "Done."}, format="json")
    with capture(execute=True):
        sign_in(buyer).post(f"/api/v1/orders/{order.pk}/accept/")
    return Payout.objects.get(freelancer=seller)


# --- Payouts ---------------------------------------------------------------------


@pytest.mark.django_db
def test_an_approved_payout_is_sent_through_swich(
    gig, buyer, seller, payouts_on, django_capture_on_commit_callbacks
):
    _profile(seller)
    with (
        patch("payments.swich.fetch_title", return_value="SELLER KHAN") as title,
        patch("payments.swich.send_ibft", return_value="225") as ibft,
    ):
        payout = _approve(gig, buyer, seller, django_capture_on_commit_callbacks)

    payout.refresh_from_db()
    assert payout.status == Payout.Status.PAID
    assert payout.note == "Swich IBFT 225"
    title.assert_called_once()
    sent = ibft.call_args.kwargs
    assert sent["amount"] == payout.net_amount
    assert sent["bank_code"] == "MEZN"
    assert sent["reference"] == payout.swich_reference
    assert Notification.objects.filter(user=seller, title="Payment sent").exists()


@pytest.mark.django_db
def test_money_is_never_sent_to_an_account_in_someone_elses_name(
    gig, buyer, seller, payouts_on, django_capture_on_commit_callbacks
):
    _profile(seller)
    with (
        patch("payments.swich.fetch_title", return_value="ALI RAZA TRADERS"),
        patch("payments.swich.send_ibft") as ibft,
    ):
        payout = _approve(gig, buyer, seller, django_capture_on_commit_callbacks)

    payout.refresh_from_db()
    ibft.assert_not_called()
    assert payout.status == Payout.Status.PENDING
    assert "belongs to" in payout.last_error


@pytest.mark.django_db
def test_a_refused_payout_waits_with_swichs_reason(
    gig, buyer, seller, payouts_on, django_capture_on_commit_callbacks
):
    _profile(seller)
    with (
        patch("payments.swich.fetch_title", return_value=""),
        patch("payments.swich.send_ibft", side_effect=SwichError("Swich: No bank found", "0007")),
    ):
        payout = _approve(gig, buyer, seller, django_capture_on_commit_callbacks)

    payout.refresh_from_db()
    assert payout.status == Payout.Status.PENDING
    assert payout.last_error == "Swich: No bank found"


@pytest.mark.django_db
def test_a_resend_asks_swich_about_the_last_attempt_first(
    gig, buyer, seller, payouts_on, django_capture_on_commit_callbacks
):
    """The last request may have gone through even though no answer came
    back. Sending again without asking could pay the freelancer twice."""
    _profile(seller)
    with patch("payments.swich.fetch_title", side_effect=SwichError("timeout")):
        payout = _approve(gig, buyer, seller, django_capture_on_commit_callbacks)
    Payout.objects.filter(pk=payout.pk).update(swich_reference=f"SRPO{payout.pk:07d}-1")

    with (
        patch("payments.swich.inquire_payout", return_value={"id": "9", "status_text": "Success"}),
        patch("payments.swich.send_ibft") as ibft,
    ):
        assert send_payout(payout.pk) == "paid"

    ibft.assert_not_called()
    payout.refresh_from_db()
    assert payout.status == Payout.Status.PAID


@pytest.mark.django_db
def test_a_freelancer_without_payout_details_is_asked_for_them(
    gig, buyer, seller, payouts_on, django_capture_on_commit_callbacks
):
    _profile(seller, bank_code="")  # typed in by hand, not a Swich destination
    with patch("payments.swich.send_ibft") as ibft:
        payout = _approve(gig, buyer, seller, django_capture_on_commit_callbacks)

    payout.refresh_from_db()
    ibft.assert_not_called()
    assert payout.status == Payout.Status.PENDING
    assert Notification.objects.filter(user=seller, title="Add where to send your payment").exists()


@pytest.mark.django_db
def test_nothing_goes_out_while_swich_payouts_are_off(
    gig, buyer, seller, django_capture_on_commit_callbacks
):
    _profile(seller)
    with patch("payments.swich.send_ibft") as ibft:
        payout = _approve(gig, buyer, seller, django_capture_on_commit_callbacks)

    ibft.assert_not_called()
    assert payout.status == Payout.Status.PENDING
    assert send_payout(payout.pk) == "disabled"


def test_names_agree_loosely_but_not_with_a_stranger():
    assert names_agree("Seller Khan", "MR SELLER KHAN S/O AHMED")
    assert names_agree("Seller Khan", "")
    assert not names_agree("Seller Khan", "ALI RAZA TRADERS")


# --- Refunds -------------------------------------------------------------------------


def _cancel(gig, buyer, seller, capture):
    order = _active_order(gig, buyer)
    with capture(execute=True):
        sign_in(seller).post(f"/api/v1/orders/{order.pk}/cancel/")
    return Refund.objects.get(client=buyer)


@pytest.mark.django_db
def test_a_cancelled_order_is_refunded_to_the_card_or_wallet(
    gig, buyer, seller, payouts_on, django_capture_on_commit_callbacks
):
    with patch("payments.swich.refund_payin") as refund_call:
        refund = _cancel(gig, buyer, seller, django_capture_on_commit_callbacks)

    refund.refresh_from_db()
    assert refund.status == Refund.Status.REFUNDED
    assert refund_call.call_args.kwargs["amount"] == refund.amount
    assert refund_call.call_args.kwargs["swich_order_id"].startswith("SW-")
    assert Notification.objects.filter(user=buyer, title="Refund sent").exists()


@pytest.mark.django_db
def test_a_method_swich_cannot_refund_is_left_for_a_person(
    gig, buyer, seller, payouts_on, django_capture_on_commit_callbacks
):
    with patch(
        "payments.swich.refund_payin",
        side_effect=SwichError("Swich: No refund policy applies to this transaction", "0009"),
    ):
        refund = _cancel(gig, buyer, seller, django_capture_on_commit_callbacks)

    refund.refresh_from_db()
    assert refund.status == Refund.Status.PENDING
    assert "No refund policy" in refund.last_error


# --- Console and profile -------------------------------------------------------------


@pytest.mark.django_db
def test_finance_can_resend_a_payout_from_the_console(
    gig, buyer, seller, payouts_on, django_capture_on_commit_callbacks
):
    _profile(seller, bank_code="")
    payout = _approve(gig, buyer, seller, django_capture_on_commit_callbacks)
    PayoutProfile.objects.filter(user=seller).update(bank_code="MEZN")
    finance = make_user("finance@skilrize.test", admin_role="finance_admin")

    with (
        patch("payments.swich.fetch_title", return_value="Seller Khan"),
        patch("payments.swich.send_ibft", return_value="301"),
    ):
        response = sign_in(finance).post(f"/api/v1/admin/payments/payouts/{payout.pk}/send-swich/")

    assert response.data["outcome"] == "paid"
    assert response.data["payout"]["status"] == "paid"


@pytest.mark.django_db
def test_a_payout_profile_takes_a_listed_bank_or_wallet(seller):
    api = sign_in(seller)

    wallet = api.patch(
        "/api/v1/payments/payout-profile/",
        {
            "bank_code": "tmfb",
            "account_title": "Seller Khan",
            "account_number": "03001234567",
            "cnic": "3520212345671",
            "msisdn": "03001234567",
        },
        format="json",
    )
    unknown = api.patch("/api/v1/payments/payout-profile/", {"bank_code": "XXXX"}, format="json")

    assert wallet.data["bank_code"] == "TMFB"
    assert wallet.data["bank_name"] == "Easypaisa"
    assert wallet.data["swich_ready"] is True
    assert unknown.status_code == 400
    assert api.get("/api/v1/payments/payout-institutions/").data[0]["name"] == "Easypaisa"


def test_the_adapter_signs_in_once_and_reads_swichs_verdict(payouts_on):
    """A 200 from Swich is not success on its own: its body says "failed"
    with a code when a payout is refused, and that must reach the caller."""
    from unittest.mock import MagicMock

    from . import swich

    swich._token.update(value="", expires=0.0)
    token = MagicMock(status_code=200)
    token.json.return_value = {"access_token": "abc", "expires_in": 3600}
    refused = MagicMock(status_code=200, reason="OK")
    refused.json.return_value = {"status": "failed", "code": "0007", "message": "No bank found"}
    balance = MagicMock(status_code=200, reason="OK")
    balance.json.return_value = {"status": "success", "code": "0000", "data": {"balance": 150.5}}

    with (
        patch.object(swich._http, "post", return_value=token) as sign_in_call,
        patch.object(swich._http, "request", side_effect=[refused, balance]) as calls,
    ):
        with pytest.raises(swich.SwichError) as refusal:
            swich.fetch_title(
                bank_code="XXXX", bank_name="X", account_number="1", msisdn="0", amount=1
            )
        assert str(swich.payout_balance()) == "150.5"

    assert refusal.value.code == "0007"
    assert sign_in_call.call_count == 1  # the token is reused
    assert calls.call_args.kwargs["headers"] == {"Authorization": "Bearer abc"}
    swich._token.update(value="", expires=0.0)
