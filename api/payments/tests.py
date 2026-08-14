"""
Tests for Phase 3 payments — D41.

The rules worth guarding: a checksum that doesn't match must never be
trusted regardless of what the request claims, a callback can arrive twice
and must not double-fund, a payout never starts without a complete payout
profile, and nothing in `EscrowCharge`/`Payout` ever echoes an encrypted
field back through the API.
"""

from __future__ import annotations

import hashlib
import hmac
from unittest.mock import patch

import pytest
from django.test import override_settings

from contracts.models import Contract, ContractType, Milestone
from contracts.tests import _SWICH_TEST_SETTINGS, _fund_via_swich, _give_payout_profile
from core.scope import GLOBAL_SCOPE, use_scope
from marketplace.tests import make_user, sign_in

from .models import EscrowCharge, Payout
from .providers import swich
from .providers.base import SwichError, SwichUnavailable


@pytest.fixture(autouse=True)
def _reset_token_cache():
    """`swich.get_token()` caches its bearer token in module-level state
    (Phase 3, D41) — real across requests in production, but real across
    *tests* too unless cleared, which would make one test's cached token
    silently skip another test's mocked auth call."""
    swich._token_cache["token"] = None
    swich._token_cache["expires_at"] = 0.0
    yield
    swich._token_cache["token"] = None
    swich._token_cache["expires_at"] = 0.0


@pytest.fixture
def parties(db):
    return make_user("client@example.com"), make_user("freelancer@example.com")


@pytest.fixture
def funded_milestone(parties):
    """A milestone sitting in `AWAITING_PAYMENT` with a real `EscrowCharge`
    behind it — the state every callback test starts from."""
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


def _checksum(
    secret: str, customer_transaction_id: str, order_id: str, amount: str, status: str
) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        f"SWCallback:{customer_transaction_id}:{order_id}:{amount}:{status}".encode(),
        hashlib.sha256,
    ).hexdigest()


# --- Swich adapter: checksums and gating ------------------------------------


@override_settings(**_SWICH_TEST_SETTINGS)
def test_checkout_checksum_matches_swichs_documented_formula():
    checksum = swich.checkout_checksum(
        customer_transaction_id="fund-1", item="Milestone", amount="10.00"
    )
    expected = hmac.new(
        b"test-signing-key", b"Swich:fund-1:Milestone:10.00", hashlib.sha256
    ).hexdigest()
    assert checksum == expected


@override_settings(**_SWICH_TEST_SETTINGS)
def test_verify_callback_checksum_accepts_a_correctly_signed_callback():
    checksum = _checksum("test-signing-key", "fund-1", "ORDER-1", "10.00", "success")
    assert swich.verify_callback_checksum(
        customer_transaction_id="fund-1",
        order_id="ORDER-1",
        amount="10.00",
        status="success",
        checksum=checksum,
    )


@override_settings(**_SWICH_TEST_SETTINGS)
def test_verify_callback_checksum_rejects_a_forged_callback():
    """The one test that matters most in this file: a checksum computed for
    a *different* amount must never pass for this one — someone claiming a
    milestone was paid Rs 10 when they forged a callback for Rs 1 is exactly
    the attack this function exists to stop."""
    checksum = _checksum("test-signing-key", "fund-1", "ORDER-1", "1.00", "success")
    assert not swich.verify_callback_checksum(
        customer_transaction_id="fund-1",
        order_id="ORDER-1",
        amount="10.00",
        status="success",
        checksum=checksum,
    )


@override_settings(SWICH_ENABLED=False)
def test_swich_functions_refuse_to_run_when_not_enabled():
    """Off by default, same as every other provider in this codebase — and
    every entry point checks, not just the one a test happens to exercise.
    Forces the setting explicitly rather than relying on Django's own
    default, since this *environment* has real sandbox credentials
    configured (D41) and would otherwise make this test call the network."""
    with pytest.raises(SwichUnavailable):
        swich.get_token()
    with pytest.raises(SwichUnavailable):
        swich.build_checkout_url(
            customer_transaction_id="x",
            amount="10",
            item="x",
            description="x",
            payee_name="x",
            email="x@example.com",
            msisdn="03000000000",
        )
    with pytest.raises(SwichUnavailable):
        swich.create_payout(
            customer_transaction_id="x",
            account_number="x",
            account_title="x",
            amount="10",
            bank_code="x",
            bank_name="x",
            cnic="x",
            msisdn="x",
            name="x",
        )


@override_settings(**_SWICH_TEST_SETTINGS)
def test_get_token_is_cached_across_calls():
    with patch("payments.providers.swich.session.post") as mocked_post:
        mocked_post.return_value.status_code = 200
        mocked_post.return_value.json.return_value = {"access_token": "abc", "expires_in": 3600}
        swich.get_token()
        swich.get_token()
    assert mocked_post.call_count == 1


@override_settings(**_SWICH_TEST_SETTINGS)
def test_create_payout_raises_swich_error_on_a_non_200():
    with (
        patch("payments.providers.swich.get_token", return_value="tok"),
        patch("payments.providers.swich.session.post") as mocked_post,
    ):
        mocked_post.return_value.status_code = 400
        mocked_post.return_value.text = '{"message": "bad account"}'
        mocked_post.return_value.content = b'{"message": "bad account"}'
        mocked_post.return_value.json.return_value = {"message": "bad account"}
        with pytest.raises(SwichError):
            swich.create_payout(
                customer_transaction_id="x",
                account_number="x",
                account_title="x",
                amount="10",
                bank_code="x",
                bank_name="x",
                cnic="x",
                msisdn="x",
                name="x",
            )


# --- Pay In callback ---------------------------------------------------------


@pytest.mark.django_db
@override_settings(**_SWICH_TEST_SETTINGS)
def test_a_correctly_signed_success_callback_funds_the_milestone(funded_milestone):
    contract, milestone, client_user, freelancer = funded_milestone
    client_api = sign_in(client_user)
    _fund_via_swich(client_api, contract, milestone)

    milestone.refresh_from_db()
    assert milestone.status == Milestone.Status.FUNDED
    charge = EscrowCharge.objects.get(milestone=milestone)
    assert charge.status == EscrowCharge.Status.PAID
    assert charge.swich_order_id == "SANDBOX-ORDER-1"


@pytest.mark.django_db
@override_settings(**_SWICH_TEST_SETTINGS)
def test_a_correctly_signed_failure_callback_reverts_to_pending(funded_milestone):
    contract, milestone, client_user, freelancer = funded_milestone
    client_api = sign_in(client_user)

    fund_response = client_api.post(
        f"/api/v1/contracts/{contract.pk}/milestones/{milestone.pk}/fund/"
    )
    assert fund_response.status_code == 200
    charge = EscrowCharge.objects.get(milestone=milestone)

    checksum = _checksum(
        "test-signing-key", charge.customer_transaction_id, "ORDER-2", str(charge.amount), "failed"
    )
    response = client_api.get(
        "/api/v1/payments/callbacks/swich/payin/",
        {
            "CustomerTransactionId": charge.customer_transaction_id,
            "OrderId": "ORDER-2",
            "Amount": str(charge.amount),
            "Status": "failed",
            "checksum": checksum,
        },
    )
    assert response.status_code == 200
    milestone.refresh_from_db()
    assert milestone.status == Milestone.Status.PENDING
    charge.refresh_from_db()
    assert charge.status == EscrowCharge.Status.FAILED


@pytest.mark.django_db
@override_settings(**_SWICH_TEST_SETTINGS)
def test_a_callback_with_a_wrong_checksum_is_rejected_and_changes_nothing(funded_milestone):
    contract, milestone, client_user, freelancer = funded_milestone
    client_api = sign_in(client_user)
    client_api.post(f"/api/v1/contracts/{contract.pk}/milestones/{milestone.pk}/fund/")
    charge = EscrowCharge.objects.get(milestone=milestone)

    response = client_api.get(
        "/api/v1/payments/callbacks/swich/payin/",
        {
            "CustomerTransactionId": charge.customer_transaction_id,
            "OrderId": "ORDER-3",
            "Amount": str(charge.amount),
            "Status": "success",
            "checksum": "not-a-real-checksum",
        },
    )
    assert response.status_code == 400
    milestone.refresh_from_db()
    assert milestone.status == Milestone.Status.AWAITING_PAYMENT
    charge.refresh_from_db()
    assert charge.status == EscrowCharge.Status.CREATED


@pytest.mark.django_db
@override_settings(**_SWICH_TEST_SETTINGS)
def test_a_replayed_callback_does_not_fund_twice(funded_milestone):
    contract, milestone, client_user, freelancer = funded_milestone
    client_api = sign_in(client_user)
    _fund_via_swich(client_api, contract, milestone)
    charge = EscrowCharge.objects.get(milestone=milestone)

    # The exact same callback Swich might resend if our first 2xx never
    # reached them.
    checksum = _checksum(
        "test-signing-key",
        charge.customer_transaction_id,
        "SANDBOX-ORDER-1",
        str(charge.amount),
        "success",
    )
    replay = client_api.get(
        "/api/v1/payments/callbacks/swich/payin/",
        {
            "CustomerTransactionId": charge.customer_transaction_id,
            "OrderId": "SANDBOX-ORDER-1",
            "Amount": str(charge.amount),
            "Status": "success",
            "checksum": checksum,
        },
    )
    assert replay.status_code == 200
    assert replay.data == {"status": "already processed"}


@pytest.mark.django_db
@override_settings(**_SWICH_TEST_SETTINGS)
def test_an_unknown_transaction_id_is_a_404_not_a_silent_success(funded_milestone):
    _, _, client_user, _ = funded_milestone
    client_api = sign_in(client_user)
    checksum = _checksum("test-signing-key", "never-existed", "ORDER-4", "10.00", "success")
    response = client_api.get(
        "/api/v1/payments/callbacks/swich/payin/",
        {
            "CustomerTransactionId": "never-existed",
            "OrderId": "ORDER-4",
            "Amount": "10.00",
            "Status": "success",
            "checksum": checksum,
        },
    )
    assert response.status_code == 404


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
        "/api/v1/payments/payout-profile/", {"bank_code": "HABB"}, format="json"
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_verify_title_requires_all_fields():
    client_user = make_user("client2@example.com")
    response = sign_in(client_user).post(
        "/api/v1/payments/payout-profile/verify-title/", {"bank_code": "HABB"}, format="json"
    )
    assert response.status_code == 400


# --- process_payout task -----------------------------------------------------


@pytest.mark.django_db
@override_settings(**_SWICH_TEST_SETTINGS)
def test_process_payout_pays_and_notifies_on_success(parties):
    from .tasks import process_payout

    _, freelancer = parties
    _give_payout_profile(freelancer)
    with use_scope(GLOBAL_SCOPE):
        contract = Contract.objects.create(
            client=make_user("client3@example.com"),
            freelancer=freelancer,
            title="X",
            contract_type=ContractType.FIXED,
            status=Contract.Status.ACTIVE,
            total_amount=500,
        )
        milestone = Milestone.objects.create(contract=contract, title="M", amount=500)
    payout = Payout.objects.create(
        milestone=milestone,
        freelancer=freelancer,
        customer_transaction_id="payout-test-1",
        amount=500,
    )

    with patch(
        "payments.providers.swich.create_payout",
        return_value={"data": {"transactionId": "999", "stan": "1"}},
    ) as mocked:
        process_payout.apply(args=[payout.id])

    mocked.assert_called_once()
    payout.refresh_from_db()
    assert payout.status == Payout.Status.PAID
    assert payout.swich_response["data"]["transactionId"] == "999"


@pytest.mark.django_db
@override_settings(**_SWICH_TEST_SETTINGS)
def test_process_payout_fails_cleanly_without_a_payout_profile(parties):
    from .tasks import process_payout

    client_user, freelancer = parties
    with use_scope(GLOBAL_SCOPE):
        contract = Contract.objects.create(
            client=client_user,
            freelancer=freelancer,
            title="X",
            contract_type=ContractType.FIXED,
            status=Contract.Status.ACTIVE,
            total_amount=500,
        )
        milestone = Milestone.objects.create(contract=contract, title="M", amount=500)
    payout = Payout.objects.create(
        milestone=milestone,
        freelancer=freelancer,
        customer_transaction_id="payout-test-2",
        amount=500,
    )

    process_payout.apply(args=[payout.id])

    payout.refresh_from_db()
    assert payout.status == Payout.Status.FAILED
    assert "profile" in payout.failure_reason.lower()


# --- release_milestone requires a complete payout profile --------------------


@pytest.mark.django_db
@override_settings(**_SWICH_TEST_SETTINGS)
def test_release_refuses_without_a_complete_payout_profile(funded_milestone):
    contract, milestone, client_user, freelancer = funded_milestone
    client_api = sign_in(client_user)
    _fund_via_swich(client_api, contract, milestone)
    sign_in(freelancer).post(
        f"/api/v1/contracts/{contract.pk}/milestones/{milestone.pk}/deliver/",
        {"note": "done"},
        format="json",
    )

    response = client_api.post(
        f"/api/v1/contracts/{contract.pk}/milestones/{milestone.pk}/release/"
    )
    assert response.status_code == 400
    assert response.data["code"] == "payout_profile_incomplete"
    milestone.refresh_from_db()
    assert milestone.status == Milestone.Status.DELIVERED
