"""
Tests for Phase 3 payments — D42.

There is no gateway here to test a checksum or a callback against — funding
and release are declarations, not verified transactions (see the module
docstring on `payments.models`). What still needs guarding: the commission
split arithmetic is exactly right and snapshotted rather than recomputed
later, a payout profile's encrypted fields never echo back through the API,
release refuses without somewhere to actually send the money, and only the
right party can fund or release in the first place.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import override_settings

from contracts.models import Contract, ContractType, Milestone
from contracts.tests import _fund, _give_payout_profile
from core.scope import GLOBAL_SCOPE, use_scope
from marketplace.tests import make_user, sign_in

from .models import Charge, EscrowFunding, Payout, PayoutProfile, Refund
from .testing import swich_pays, swich_says


def _release(client_api, contract, milestone):
    return client_api.post(f"/api/v1/contracts/{contract.pk}/milestones/{milestone.pk}/release/")


@pytest.fixture
def parties(db):
    return make_user("client@example.com"), make_user("freelancer@example.com")


@pytest.fixture
def funded_milestone(parties):
    """An active contract with one pending milestone — the state every
    fund/release test here starts from."""
    client_user, freelancer = parties
    with use_scope(GLOBAL_SCOPE):
        contract = Contract.objects.create(
            client=client_user,
            freelancer=freelancer,
            title="Landing page",
            contract_type=ContractType.FIXED,
            status=Contract.Status.ACTIVE,
            total_amount=1000,
        )
        milestone = Milestone.objects.create(contract=contract, title="Homepage", amount=1000)
    return contract, milestone, client_user, freelancer


# --- Payout.compute — the commission split arithmetic -----------------------


@pytest.mark.django_db
def test_payout_compute_splits_gross_into_commission_and_net(funded_milestone):
    _, milestone, _, freelancer = funded_milestone

    payout = Payout.compute(
        milestone=milestone, freelancer=freelancer, commission_percent=Decimal("10")
    )

    assert payout.gross_amount == 1000
    assert payout.commission_amount == Decimal("100.00")
    assert payout.net_amount == Decimal("900.00")
    assert payout.net_amount == payout.gross_amount - payout.commission_amount


@pytest.mark.django_db
def test_payout_compute_does_not_save(funded_milestone):
    """`compute` builds the object; the caller decides whether it is real."""
    _, milestone, _, freelancer = funded_milestone
    Payout.compute(milestone=milestone, freelancer=freelancer, commission_percent=Decimal("10"))
    assert not Payout.objects.filter(milestone=milestone).exists()


# --- PayoutProfile.is_complete -----------------------------------------------


@pytest.mark.django_db
def test_a_payout_profile_is_incomplete_until_every_field_is_set(parties):
    _, freelancer = parties
    profile = PayoutProfile.objects.create(user=freelancer, bank_name="Habib Bank")
    assert profile.is_complete is False

    profile.account_title = "Test Freelancer"
    profile.account_number = "PK00HABB0000001234567"
    profile.cnic = "1234512345671"
    profile.save()
    assert profile.is_complete is True


# --- What a buyer can pay with ----------------------------------------------


@pytest.mark.django_db
@override_settings(PLATFORM_COMMISSION_PERCENT="12.5")
def test_the_payment_options_name_swich_and_its_methods(client):
    response = client.get("/api/v1/payments/options/")
    assert response.status_code == 200
    assert response.data["available"] is True
    assert response.data["provider"] == "Swich"
    assert [m["id"] for m in response.data["methods"]] == ["card", "easypaisa", "jazzcash", "1bill"]
    assert response.data["commission_percent"] == "12.5"


# --- Payout profile -----------------------------------------------------------


@pytest.mark.django_db
def test_a_payout_profile_never_echoes_the_encrypted_fields_back(parties):
    _, freelancer = parties
    _give_payout_profile(freelancer)

    response = sign_in(freelancer).get("/api/v1/payments/payout-profile/")
    assert response.status_code == 200
    assert "account_number" not in response.data
    assert "cnic" not in response.data
    assert response.data["is_complete"] is True


@pytest.mark.django_db
def test_saving_a_payout_profile_requires_two_factor(db):
    """`CanMoveMoney`, the same gate funding and releasing sit behind —
    where the freelancer's money actually goes is exactly the kind of
    account change that gate exists for."""
    no_2fa_user = make_user("no-2fa@example.com", two_factor=False)
    response = sign_in(no_2fa_user).patch(
        "/api/v1/payments/payout-profile/", {"bank_name": "Habib Bank"}, format="json"
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_saving_a_payout_profile_round_trips_the_plain_fields(parties):
    _, freelancer = parties
    response = sign_in(freelancer).patch(
        "/api/v1/payments/payout-profile/",
        {
            "bank_name": "Meezan Bank",
            "account_title": "A Freelancer",
            "account_number": "PK00MEZN0000001234567",
            "cnic": "3520212345671",
            "msisdn": "03001234567",
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.data["bank_name"] == "Meezan Bank"
    assert response.data["is_complete"] is True

    profile = PayoutProfile.objects.get(user=freelancer)
    assert profile.account_number == "PK00MEZN0000001234567"
    assert profile.cnic == "3520212345671"


# --- fund_milestone -----------------------------------------------------------


@pytest.mark.django_db
def test_a_milestone_is_funded_only_once_swich_confirms_the_payment(funded_milestone):
    contract, milestone, client_user, freelancer = funded_milestone
    client_api = sign_in(client_user)

    response = client_api.post(f"/api/v1/contracts/{contract.pk}/milestones/{milestone.pk}/fund/")
    assert response.status_code == 200
    assert "checksum=" in response.data["checkout_url"]
    # Sent to Swich, but nothing is held until Swich says it was paid.
    milestone.refresh_from_db()
    assert milestone.status == Milestone.Status.PENDING

    assert swich_pays(response).data["status"] == "paid"

    milestone.refresh_from_db()
    assert milestone.status == Milestone.Status.FUNDED
    funding = EscrowFunding.objects.get(milestone=milestone)
    assert funding.amount == milestone.amount
    assert funding.funded_by_id == client_user.pk
    assert funding.confirmed_at is not None
    assert funding.reference_note.startswith("Swich ")


@pytest.mark.django_db
def test_only_the_client_can_fund_a_milestone(funded_milestone):
    contract, milestone, _, freelancer = funded_milestone

    response = sign_in(freelancer).post(
        f"/api/v1/contracts/{contract.pk}/milestones/{milestone.pk}/fund/"
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_a_milestone_cannot_be_funded_twice(funded_milestone):
    contract, milestone, client_user, _ = funded_milestone
    client_api = sign_in(client_user)
    _fund(client_api, contract, milestone)

    response = client_api.post(f"/api/v1/contracts/{contract.pk}/milestones/{milestone.pk}/fund/")
    assert response.status_code == 400
    assert EscrowFunding.objects.filter(milestone=milestone).count() == 1


# --- release_milestone --------------------------------------------------------


@pytest.mark.django_db
@override_settings(PLATFORM_COMMISSION_PERCENT="10")
def test_release_computes_the_commission_split_and_queues_a_pending_payout(funded_milestone):
    contract, milestone, client_user, freelancer = funded_milestone
    _give_payout_profile(freelancer)
    client_api = sign_in(client_user)
    _fund(client_api, contract, milestone)
    sign_in(freelancer).post(f"/api/v1/contracts/{contract.pk}/milestones/{milestone.pk}/deliver/")

    response = _release(client_api, contract, milestone)
    assert response.status_code == 200

    payout = Payout.objects.get(milestone=milestone)
    assert payout.freelancer_id == freelancer.pk
    assert payout.status == Payout.Status.PENDING
    assert payout.gross_amount == milestone.amount
    assert payout.commission_percent == Decimal("10.00")
    assert payout.commission_amount == Decimal("100.00")
    assert payout.net_amount == Decimal("900.00")
    assert payout.paid_at is None


@pytest.mark.django_db
def test_release_refuses_without_a_complete_payout_profile(funded_milestone):
    contract, milestone, client_user, freelancer = funded_milestone
    client_api = sign_in(client_user)
    _fund(client_api, contract, milestone)
    sign_in(freelancer).post(f"/api/v1/contracts/{contract.pk}/milestones/{milestone.pk}/deliver/")

    response = _release(client_api, contract, milestone)
    assert response.status_code == 400
    assert response.data["code"] == "payout_profile_incomplete"
    milestone.refresh_from_db()
    assert milestone.status == Milestone.Status.DELIVERED
    assert not Payout.objects.filter(milestone=milestone).exists()


@pytest.mark.django_db
def test_release_refuses_before_delivery(funded_milestone):
    contract, milestone, client_user, freelancer = funded_milestone
    _give_payout_profile(freelancer)
    client_api = sign_in(client_user)
    _fund(client_api, contract, milestone)

    response = _release(client_api, contract, milestone)
    assert response.status_code == 400


# --- MyPayoutsView -------------------------------------------------------------


@pytest.mark.django_db
def test_my_payouts_lists_only_the_callers_own_payouts(funded_milestone):
    _, milestone, _, freelancer = funded_milestone
    stranger = make_user("stranger-payouts@example.com")

    Payout.compute(
        milestone=milestone, freelancer=freelancer, commission_percent=Decimal("10")
    ).save()

    mine = sign_in(freelancer).get("/api/v1/payments/payouts/")
    assert mine.data["count"] == 1
    assert mine.data["results"][0]["milestone_title"] == "Homepage"

    assert sign_in(stranger).get("/api/v1/payments/payouts/").data["count"] == 0


# --- Swich: the callback is the only thing that funds (D55) ----------------------


def _start_order(gig, buyer):
    from gigs.tests import _place

    response = _place(gig, buyer)
    assert response.status_code == 201, response.data
    return response


@pytest.mark.django_db
def test_an_order_waits_for_payment_and_the_seller_does_not_see_it(gig, buyer, seller):
    from gigs.models import Order

    response = _start_order(gig, buyer)

    order = Order.objects.get(pk=response.data["order"]["id"])
    assert order.status == Order.Status.AWAITING_PAYMENT
    assert order.contract.milestones.get().status == Milestone.Status.PENDING
    assert sign_in(seller).get("/api/v1/orders/").data["count"] == 0
    gig.refresh_from_db()
    assert gig.orders_count == 0

    swich_pays(response)

    order.refresh_from_db()
    assert order.status == Order.Status.PENDING_REQUIREMENTS
    assert sign_in(seller).get("/api/v1/orders/").data["count"] == 1
    gig.refresh_from_db()
    assert gig.orders_count == 1


@pytest.mark.django_db
def test_a_forged_callback_funds_nothing(gig, buyer):
    from gigs.models import Order

    response = _start_order(gig, buyer)
    reference = response.data["payment_reference"]

    forged = sign_in(buyer).get(
        "/api/v1/payments/swich/callback/",
        {
            "CustomerTransactionId": reference,
            "OrderId": "X",
            "Amount": "15000.00",
            "Status": "Success",
            "checksum": "0" * 64,
        },
    )

    assert forged.status_code == 400
    assert Order.objects.get(pk=response.data["order"]["id"]).status == "awaiting_payment"
    assert Charge.objects.get(reference=reference).status == Charge.Status.CREATED


@pytest.mark.django_db
def test_a_repeated_callback_is_applied_once(gig, buyer):
    from gigs.models import Order

    response = _start_order(gig, buyer)
    reference = response.data["payment_reference"]

    assert swich_says(reference).data["status"] == "paid"
    assert swich_says(reference).data["status"] == "duplicate"

    order = Order.objects.get(pk=response.data["order"]["id"])
    assert EscrowFunding.objects.filter(milestone__contract=order.contract).count() == 1
    gig.refresh_from_db()
    assert gig.orders_count == 1


@pytest.mark.django_db
def test_a_failed_payment_can_be_tried_again(gig, buyer):
    from gigs.models import Order

    response = _start_order(gig, buyer)
    order_id = response.data["order"]["id"]

    assert swich_says(response.data["payment_reference"], "Failed").data["status"] == "failed"
    assert Order.objects.get(pk=order_id).status == Order.Status.AWAITING_PAYMENT

    retry = sign_in(buyer).post(f"/api/v1/orders/{order_id}/pay/")
    assert retry.status_code == 200
    assert retry.data["payment_reference"] != response.data["payment_reference"]
    swich_pays(retry)
    assert Order.objects.get(pk=order_id).status == Order.Status.PENDING_REQUIREMENTS


@pytest.mark.django_db
def test_a_different_amount_is_never_funded(gig, buyer):
    from gigs.models import Order

    response = _start_order(gig, buyer)

    outcome = swich_says(response.data["payment_reference"], amount="1.00")

    assert outcome.data["status"] == "amount_mismatch"
    assert Order.objects.get(pk=response.data["order"]["id"]).status == "awaiting_payment"


@pytest.mark.django_db
def test_an_unpaid_order_is_cancelled_by_the_buyer_without_a_refund(gig, buyer):
    from gigs.models import Order

    response = _start_order(gig, buyer)
    order_id = response.data["order"]["id"]

    cancelled = sign_in(buyer).post(f"/api/v1/orders/{order_id}/cancel/")

    assert cancelled.status_code == 200
    assert Order.objects.get(pk=order_id).status == Order.Status.CANCELLED
    assert not Refund.objects.exists()


@pytest.mark.django_db
def test_a_payment_for_an_order_already_closed_is_owed_back(gig, buyer):
    from gigs.models import Order

    response = _start_order(gig, buyer)
    sign_in(buyer).post(f"/api/v1/orders/{response.data['order']['id']}/cancel/")

    swich_pays(response)

    assert Order.objects.get(pk=response.data["order"]["id"]).status == Order.Status.CANCELLED
    assert Refund.objects.get(client=buyer).amount == 15000


@pytest.mark.django_db
def test_unpaid_orders_close_after_the_window(gig, buyer, settings):
    from datetime import timedelta

    from django.utils import timezone

    from gigs.models import Order

    from .checkout import expire_unpaid

    response = _start_order(gig, buyer)

    early = expire_unpaid()
    late = expire_unpaid(now=timezone.now() + timedelta(hours=settings.UNPAID_ORDER_HOURS + 1))

    assert early == {"charges": 0, "orders": 0}
    assert late == {"charges": 1, "orders": 1}
    assert Order.objects.get(pk=response.data["order"]["id"]).status == Order.Status.CANCELLED


@pytest.mark.django_db
def test_nothing_is_taken_while_swich_is_off(gig, buyer, settings):
    from gigs.models import Order

    settings.SWICH_ENABLED = False

    from gigs.tests import _place

    response = _place(gig, buyer)

    assert response.status_code == 503
    assert response.data["code"] == "payments_unavailable"
    assert not Order.objects.exists()
    assert sign_in(buyer).get("/api/v1/payments/options/").data["available"] is False


@pytest.mark.django_db
def test_only_the_payer_can_read_a_charge(gig, buyer, seller):
    response = _start_order(gig, buyer)
    url = f"/api/v1/payments/charges/{response.data['payment_reference']}/"

    assert sign_in(seller).get(url).status_code == 404
    mine = sign_in(buyer).get(url)
    assert mine.status_code == 200
    assert mine.data["status"] == "created"
    assert mine.data["order_id"] == response.data["order"]["id"]
