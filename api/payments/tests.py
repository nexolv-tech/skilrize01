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

from .models import EscrowFunding, Payout, PayoutProfile


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


# --- bank_transfer_instructions ----------------------------------------------


@pytest.mark.django_db
@override_settings(
    PLATFORM_BANK_NAME="Habib Bank",
    PLATFORM_BANK_ACCOUNT_TITLE="SkilRize Pvt Ltd",
    PLATFORM_BANK_ACCOUNT_NUMBER="PK00HABB0000009999999",
    PLATFORM_COMMISSION_PERCENT="12.5",
)
def test_bank_transfer_instructions_returns_the_platform_account(parties):
    client_user, _ = parties
    response = sign_in(client_user).get("/api/v1/payments/bank-transfer-instructions/")
    assert response.status_code == 200
    assert response.data == {
        "available": True,
        "bank_name": "Habib Bank",
        "account_title": "SkilRize Pvt Ltd",
        "account_number": "PK00HABB0000009999999",
        "commission_percent": "12.5",
    }


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
def test_funding_a_milestone_records_the_escrow_funding_and_marks_it_funded(funded_milestone):
    contract, milestone, client_user, _ = funded_milestone
    client_api = sign_in(client_user)

    response = client_api.post(
        f"/api/v1/contracts/{contract.pk}/milestones/{milestone.pk}/fund/",
        {"reference_note": "IBFT ref 12345"},
        format="json",
    )
    assert response.status_code == 200

    milestone.refresh_from_db()
    assert milestone.status == Milestone.Status.FUNDED
    funding = EscrowFunding.objects.get(milestone=milestone)
    assert funding.amount == milestone.amount
    assert funding.funded_by_id == client_user.pk
    assert funding.reference_note == "IBFT ref 12345"


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
