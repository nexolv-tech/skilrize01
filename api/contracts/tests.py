"""
Tests for the contract lifecycle.

Four properties matter most, and each has cost someone real money on other
platforms when it was wrong: terms cannot change after acceptance, work cannot
be demanded before it is funded, money cannot be released twice, and neither
side can read the other's review before writing their own.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import date
from unittest.mock import patch

import pytest
from django.test import override_settings

from accounts.models import User
from contracts.models import Contract, ContractType, Milestone, Review, TimeEntry
from core.scope import GLOBAL_SCOPE, use_scope
from marketplace.models import Project, ProjectType, Proposal
from marketplace.tests import make_user, sign_in

#: Fund/release now round-trip through the real Swich adapter's checksum
#: logic (Phase 3, D41) — every test that funds or releases a milestone
#: through the API, not `Milestone.fund()` directly, needs this on.
_SWICH_TEST_SETTINGS = dict(
    SWICH_ENABLED=True,
    SWICH_CLIENT_ID="test-client",
    SWICH_CLIENT_SECRET="test-secret",
    SWICH_SECRET_KEY="test-signing-key",
)


def _fund_via_swich(client_api, contract, milestone) -> None:
    """Fund a milestone the way it actually happens now: create the
    checkout session through the real endpoint, then simulate Swich's own
    Pay In callback with a genuinely correct checksum — not a mock of the
    callback view, an actual request computed the same way Swich's server
    would compute it, so a broken checksum formula would fail this test
    too."""
    from payments.models import EscrowCharge

    response = client_api.post(f"/api/v1/contracts/{contract.pk}/milestones/{milestone.pk}/fund/")
    assert response.status_code == 200, response.data
    assert "checkout_url" in response.data

    charge = EscrowCharge.objects.get(milestone=milestone)
    order_id = "SANDBOX-ORDER-1"
    checksum = hmac.new(
        _SWICH_TEST_SETTINGS["SWICH_SECRET_KEY"].encode("utf-8"),
        f"SWCallback:{charge.customer_transaction_id}:{order_id}:{charge.amount}:success".encode(),
        hashlib.sha256,
    ).hexdigest()
    callback = client_api.get(
        "/api/v1/payments/callbacks/swich/payin/",
        {
            "CustomerTransactionId": charge.customer_transaction_id,
            "OrderId": order_id,
            "Amount": str(charge.amount),
            "Status": "success",
            "checksum": checksum,
        },
    )
    assert callback.status_code == 200, callback.data


def _give_payout_profile(freelancer) -> None:
    """A complete `PayoutProfile`, so `release_milestone` does not refuse
    to release for a reason unrelated to what the test is actually
    checking."""
    from payments.models import PayoutProfile

    PayoutProfile.objects.update_or_create(
        user=freelancer,
        defaults=dict(
            bank_code="HABB",
            bank_name="Habib Bank",
            account_number="PK00HABB0000001234567",
            verified_account_title=freelancer.display_name or "Test Freelancer",
            cnic="1234512345671",
            msisdn="03001234567",
        ),
    )


@pytest.fixture
def parties(db):
    return make_user("client@example.com"), make_user("freelancer@example.com")


@pytest.fixture
def awarded(parties):
    """A funded-ready fixed-price contract with one accepted proposal."""
    client_user, freelancer = parties

    with use_scope(GLOBAL_SCOPE):
        project = Project.objects.create(
            client=client_user,
            title="Build an ops dashboard",
            description="React front end, Django API.",
            project_type=ProjectType.FIXED,
            budget_max=60000,
            status=Project.Status.OPEN,
        )
    proposal = Proposal.objects.create(
        project=project,
        freelancer=freelancer,
        cover_letter="Done this before.",
        bid_amount=60000,
        estimated_days=21,
    )

    response = sign_in(client_user).post(
        "/api/v1/contracts/award/", {"proposal": proposal.id}, format="json"
    )
    assert response.status_code == 201
    return Contract.objects.unscoped().get(pk=response.data["id"])


# --- Awarding --------------------------------------------------------------


@pytest.mark.django_db
def test_awarding_creates_a_pending_contract_with_one_milestone(awarded, parties):
    client_user, freelancer = parties

    assert awarded.status == Contract.Status.PENDING
    assert awarded.contract_type == ContractType.FIXED
    assert awarded.total_amount == 60000
    # A single-payment fixed contract is modelled as one milestone, not a
    # special case.
    assert awarded.milestones.count() == 1
    assert awarded.milestones.first().amount == 60000
    assert awarded.freelancer_id == freelancer.pk


@pytest.mark.django_db
def test_only_the_posting_client_can_award(parties):
    client_user, freelancer = parties
    stranger = make_user("stranger@example.com")

    with use_scope(GLOBAL_SCOPE):
        project = Project.objects.create(
            client=client_user,
            title="A brief",
            description="x",
            project_type=ProjectType.FIXED,
            budget_max=1000,
            status=Project.Status.OPEN,
        )
    proposal = Proposal.objects.create(
        project=project, freelancer=freelancer, cover_letter="x", bid_amount=1000
    )

    response = sign_in(stranger).post(
        "/api/v1/contracts/award/", {"proposal": proposal.id}, format="json"
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_a_proposal_cannot_be_awarded_twice(awarded, parties):
    client_user, _ = parties

    response = sign_in(client_user).post(
        "/api/v1/contracts/award/", {"proposal": awarded.proposal_id}, format="json"
    )
    assert response.status_code == 400
    assert response.data["code"] == "already_awarded"


@pytest.mark.django_db
def test_milestone_amounts_must_add_up_to_the_agreed_price(parties):
    """Also guards against a real bug the fix for this replaced: the
    contract-creation logic used to create the `Contract` row *before*
    validating the milestone total, so a rejected 400 still left a real,
    permanent `Contract` behind — and since `Contract.proposal` is a
    OneToOneField, that zombie row occupied the slot forever and made the
    proposal un-awardable on every later attempt, correct amounts or not."""
    client_user, freelancer = parties

    with use_scope(GLOBAL_SCOPE):
        project = Project.objects.create(
            client=client_user,
            title="A brief",
            description="x",
            project_type=ProjectType.FIXED,
            budget_max=10000,
            status=Project.Status.OPEN,
        )
    proposal = Proposal.objects.create(
        project=project, freelancer=freelancer, cover_letter="x", bid_amount=10000
    )

    response = sign_in(client_user).post(
        "/api/v1/contracts/award/",
        {
            "proposal": proposal.id,
            "milestones": [
                {"title": "Phase one", "amount": "3000"},
                {"title": "Phase two", "amount": "3000"},
            ],
        },
        format="json",
    )
    assert response.status_code == 400
    assert "add up" in response.data["detail"]
    assert not Contract.objects.unscoped().filter(proposal=proposal).exists()

    # A second, correct attempt on the same proposal must succeed — nothing
    # from the rejected first attempt should be blocking it.
    retry = sign_in(client_user).post(
        "/api/v1/contracts/award/",
        {
            "proposal": proposal.id,
            "milestones": [
                {"title": "Phase one", "amount": "4000"},
                {"title": "Phase two", "amount": "6000"},
            ],
        },
        format="json",
    )
    assert retry.status_code == 201


# --- Acceptance freezes the terms -----------------------------------------


@pytest.mark.django_db
def test_acceptance_freezes_the_terms(awarded, parties):
    """Editing the brief afterwards must not rewrite what was agreed."""
    client_user, freelancer = parties

    assert sign_in(freelancer).post(f"/api/v1/contracts/{awarded.pk}/accept/").status_code == 200

    awarded.refresh_from_db()
    assert awarded.status == Contract.Status.ACTIVE
    assert awarded.terms["total_amount"] == "60000.00"
    original_description = awarded.terms["project_description"]

    project = awarded.project
    project.description = "Actually, please also rebuild the mobile app."
    project.save(update_fields=["description"])

    awarded.refresh_from_db()
    assert awarded.terms["project_description"] == original_description


@pytest.mark.django_db
def test_only_the_freelancer_can_accept(awarded, parties):
    client_user, _ = parties
    response = sign_in(client_user).post(f"/api/v1/contracts/{awarded.pk}/accept/")
    assert response.status_code == 403


# --- Funding and delivery --------------------------------------------------


def _activate(contract, freelancer):
    sign_in(freelancer).post(f"/api/v1/contracts/{contract.pk}/accept/")
    contract.refresh_from_db()
    return contract.milestones.first()


@pytest.mark.django_db
def test_work_cannot_be_delivered_before_it_is_funded(awarded, parties):
    """The freelancer is told plainly not to begin an unfunded milestone."""
    _, freelancer = parties
    milestone = _activate(awarded, freelancer)

    response = sign_in(freelancer).post(
        f"/api/v1/contracts/{awarded.pk}/milestones/{milestone.pk}/deliver/"
    )
    assert response.status_code == 400
    assert response.data["code"] == "not_funded"


@pytest.mark.django_db
@override_settings(**_SWICH_TEST_SETTINGS)
def test_the_full_funding_delivery_release_loop(awarded, parties):
    client_user, freelancer = parties
    milestone = _activate(awarded, freelancer)
    _give_payout_profile(freelancer)

    client_api, freelancer_api = sign_in(client_user), sign_in(freelancer)

    _fund_via_swich(client_api, awarded, milestone)
    milestone.refresh_from_db()
    assert milestone.status == Milestone.Status.FUNDED
    awarded.refresh_from_db()
    assert awarded.funded_amount == 60000

    assert (
        freelancer_api.post(
            f"/api/v1/contracts/{awarded.pk}/milestones/{milestone.pk}/deliver/",
            {"note": "Dashboard is live on staging."},
            format="json",
        ).status_code
        == 200
    )
    milestone.refresh_from_db()
    assert milestone.status == Milestone.Status.DELIVERED
    awarded.refresh_from_db()
    # A delivery starts the client's review clock.
    assert awarded.review_deadline is not None

    with patch(
        "payments.providers.swich.create_payout", return_value={"data": {"transactionId": "1"}}
    ):
        release_response = client_api.post(
            f"/api/v1/contracts/{awarded.pk}/milestones/{milestone.pk}/release/"
        )
    assert release_response.status_code == 200, release_response.data

    milestone.refresh_from_db()
    awarded.refresh_from_db()
    assert milestone.status == Milestone.Status.RELEASED
    assert awarded.released_amount == 60000
    assert awarded.funded_amount == 0
    # Nothing left outstanding, so the contract closes itself.
    assert awarded.status == Contract.Status.COMPLETED

    from payments.models import Payout

    payout = Payout.objects.get(milestone=milestone)
    assert payout.status == Payout.Status.PAID


@pytest.mark.django_db
def test_a_freelancer_cannot_release_their_own_payment(awarded, parties):
    _, freelancer = parties
    milestone = _activate(awarded, freelancer)
    milestone.fund()
    milestone.deliver()

    response = sign_in(freelancer).post(
        f"/api/v1/contracts/{awarded.pk}/milestones/{milestone.pk}/release/"
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_a_stranger_cannot_see_or_touch_a_contract(awarded):
    stranger = make_user("nosy@example.com")
    api = sign_in(stranger)

    assert api.get(f"/api/v1/contracts/{awarded.pk}/").status_code == 404
    assert api.get("/api/v1/contracts/").data["count"] == 0


@pytest.mark.django_db
def test_a_contract_with_funds_held_cannot_be_cancelled(awarded, parties):
    client_user, freelancer = parties
    milestone = _activate(awarded, freelancer)
    milestone.fund()

    response = sign_in(client_user).post(f"/api/v1/contracts/{awarded.pk}/cancel/")
    assert response.status_code == 400
    assert response.data["code"] == "funds_held"


# --- Hourly work diary -----------------------------------------------------


@pytest.fixture
def hourly(parties):
    client_user, freelancer = parties

    with use_scope(GLOBAL_SCOPE):
        project = Project.objects.create(
            client=client_user,
            title="Ongoing maintenance",
            description="x",
            project_type=ProjectType.HOURLY,
            rate_min=2000,
            rate_max=3000,
            weekly_hours=10,
            status=Project.Status.OPEN,
        )
    proposal = Proposal.objects.create(
        project=project, freelancer=freelancer, cover_letter="x", hourly_rate=2500
    )
    contract_id = (
        sign_in(client_user)
        .post("/api/v1/contracts/award/", {"proposal": proposal.id}, format="json")
        .data["id"]
    )

    contract = Contract.objects.unscoped().get(pk=contract_id)
    sign_in(freelancer).post(f"/api/v1/contracts/{contract.pk}/accept/")
    contract.refresh_from_db()
    return contract


@pytest.mark.django_db
def test_hourly_contracts_carry_a_rate_and_no_milestones(hourly):
    assert hourly.contract_type == ContractType.HOURLY
    assert hourly.hourly_rate == 2500
    assert hourly.weekly_hour_limit == 10
    assert hourly.milestones.count() == 0


@pytest.mark.django_db
def test_logging_time_accrues_value(hourly, parties):
    _, freelancer = parties

    response = sign_in(freelancer).post(
        f"/api/v1/contracts/{hourly.pk}/time/",
        {"worked_on": str(date.today()), "minutes": 120, "memo": "Auth refactor"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["hours"] == 2.0
    hourly.refresh_from_db()
    assert hourly.logged_amount == 5000  # two hours at 2500


@pytest.mark.django_db
def test_the_weekly_hour_cap_is_enforced(hourly, parties):
    """A client cannot be surprised by an unbounded invoice."""
    _, freelancer = parties
    api = sign_in(freelancer)
    today = str(date.today())

    assert (
        api.post(
            f"/api/v1/contracts/{hourly.pk}/time/",
            {"worked_on": today, "minutes": 9 * 60, "memo": "Long week"},
            format="json",
        ).status_code
        == 201
    )

    over = api.post(
        f"/api/v1/contracts/{hourly.pk}/time/",
        {"worked_on": today, "minutes": 2 * 60, "memo": "Two more"},
        format="json",
    )
    assert over.status_code == 400
    assert over.data["code"] == "weekly_limit"


@pytest.mark.django_db
def test_manual_time_is_disputable_and_tracked_time_is_not(hourly, parties):
    """The asymmetry that makes hourly protection credible."""
    client_user, freelancer = parties

    manual = TimeEntry.objects.create(
        contract=hourly,
        freelancer=freelancer,
        worked_on=date.today(),
        minutes=60,
        memo="Added by hand",
        source=TimeEntry.Source.MANUAL,
    )
    tracked = TimeEntry.objects.create(
        contract=hourly,
        freelancer=freelancer,
        worked_on=date.today(),
        minutes=60,
        memo="Captured by the tracker",
        source=TimeEntry.Source.TRACKER,
        activity_level=74,
    )

    assert manual.is_protected is False
    assert tracked.is_protected is True

    api = sign_in(client_user)
    assert (
        api.post(
            f"/api/v1/contracts/{hourly.pk}/time/{manual.pk}/dispute/",
            {"note": "I did not ask for this."},
            format="json",
        ).status_code
        == 200
    )

    refused = api.post(
        f"/api/v1/contracts/{hourly.pk}/time/{tracked.pk}/dispute/", {}, format="json"
    )
    assert refused.status_code == 400
    assert refused.data["code"] == "time_protected"


@pytest.mark.django_db
def test_time_cannot_be_logged_by_the_client(hourly, parties):
    client_user, _ = parties
    response = sign_in(client_user).post(
        f"/api/v1/contracts/{hourly.pk}/time/",
        {"worked_on": str(date.today()), "minutes": 60, "memo": "Nope"},
        format="json",
    )
    assert response.status_code == 403


# --- Messaging -------------------------------------------------------------


@pytest.mark.django_db
def test_both_parties_share_one_contract_timeline(awarded, parties):
    client_user, freelancer = parties
    _activate(awarded, freelancer)

    sign_in(freelancer).post(
        f"/api/v1/contracts/{awarded.pk}/events/", {"body": "Starting today."}, format="json"
    )

    timeline = sign_in(client_user).get(f"/api/v1/contracts/{awarded.pk}/events/").data
    bodies = [event["body"] for event in timeline]
    assert "Starting today." in bodies
    # Status changes share the stream with messages, which is what makes it
    # readable as a single history.
    assert any(event["kind"] == "status" for event in timeline)


# --- Double-blind reviews --------------------------------------------------


def _complete(contract, client_user, freelancer):
    """Callers must apply `@override_settings(**_SWICH_TEST_SETTINGS)` —
    fund and release now round-trip through the real Swich checksum logic
    (Phase 3, D41)."""
    milestone = _activate(contract, freelancer)
    _give_payout_profile(freelancer)
    client_api = sign_in(client_user)
    _fund_via_swich(client_api, contract, milestone)
    sign_in(freelancer).post(f"/api/v1/contracts/{contract.pk}/milestones/{milestone.pk}/deliver/")
    with patch(
        "payments.providers.swich.create_payout", return_value={"data": {"transactionId": "1"}}
    ):
        client_api.post(f"/api/v1/contracts/{contract.pk}/milestones/{milestone.pk}/release/")
    contract.refresh_from_db()
    return contract


CLIENT_REVIEW = {
    "overall": 5,
    "communication": 5,
    "quality": 5,
    "deadline": 4,
    "value": 5,
    "comment": "Delivered exactly what was agreed.",
}
FREELANCER_REVIEW = {
    "overall": 5,
    "communication": 4,
    "clarity": 5,
    "payment_promptness": 5,
    "comment": "Clear brief, paid on time.",
}


@pytest.mark.django_db
@override_settings(**_SWICH_TEST_SETTINGS)
def test_a_review_stays_hidden_until_both_sides_submit(awarded, parties):
    client_user, freelancer = parties
    contract = _complete(awarded, client_user, freelancer)

    first = sign_in(client_user).post(
        f"/api/v1/contracts/{contract.pk}/review/", CLIENT_REVIEW, format="json"
    )
    assert first.status_code == 201
    assert first.data["published"] is False

    # Nothing is public yet, and the freelancer cannot read it early.
    assert sign_in(freelancer).get(f"/api/v1/contracts/{contract.pk}/review/").data == []
    detail = sign_in(freelancer).get(f"/api/v1/contracts/{contract.pk}/").data
    assert detail["counterparty_review"] is None

    second = sign_in(freelancer).post(
        f"/api/v1/contracts/{contract.pk}/review/", FREELANCER_REVIEW, format="json"
    )
    assert second.data["published"] is True
    assert len(sign_in(client_user).get(f"/api/v1/contracts/{contract.pk}/review/").data) == 2


@pytest.mark.django_db
def test_an_incomplete_contract_cannot_be_reviewed(awarded, parties):
    client_user, _ = parties
    response = sign_in(client_user).post(
        f"/api/v1/contracts/{awarded.pk}/review/", CLIENT_REVIEW, format="json"
    )
    assert response.status_code == 400
    assert response.data["code"] == "not_completed"


@pytest.mark.django_db
@override_settings(**_SWICH_TEST_SETTINGS)
def test_a_party_cannot_review_twice(awarded, parties):
    client_user, freelancer = parties
    contract = _complete(awarded, client_user, freelancer)
    api = sign_in(client_user)

    assert (
        api.post(
            f"/api/v1/contracts/{contract.pk}/review/", CLIENT_REVIEW, format="json"
        ).status_code
        == 201
    )
    repeat = api.post(f"/api/v1/contracts/{contract.pk}/review/", CLIENT_REVIEW, format="json")
    assert repeat.status_code == 400
    assert repeat.data["code"] == "already_reviewed"


@pytest.mark.django_db
@override_settings(**_SWICH_TEST_SETTINGS)
def test_each_side_answers_only_its_own_sub_ratings(awarded, parties):
    """A freelancer cannot rate their own quality of work."""
    client_user, freelancer = parties
    contract = _complete(awarded, client_user, freelancer)

    response = sign_in(freelancer).post(
        f"/api/v1/contracts/{contract.pk}/review/", CLIENT_REVIEW, format="json"
    )
    assert response.status_code == 400
    assert "clarity" in response.data

    saved = sign_in(client_user).post(
        f"/api/v1/contracts/{contract.pk}/review/", CLIENT_REVIEW, format="json"
    )
    assert saved.status_code == 201
    review = Review.objects.get(pk=saved.data["id"])
    # Sub-ratings that do not apply to the author's role are cleared, not left
    # to carry a misleading value.
    assert review.clarity is None
    assert review.quality == 5


# --- Admin console (Phase 9) -------------------------------------------------


@pytest.mark.django_db
def test_admin_contract_list_is_not_scoped_to_the_caller(awarded, parties):
    """Finance Admin needs the whole book, not their own deals — unlike the
    party-scoped `ContractViewSet`, an admin who is neither the client nor
    the freelancer must still see this contract."""
    finance_admin = make_user("finance-admin@example.com", admin_role=User.AdminRole.FINANCE_ADMIN)
    response = sign_in(finance_admin).get("/api/v1/admin/contracts/")
    assert response.status_code == 200
    assert any(row["id"] == awarded.id for row in response.data["results"])


@pytest.mark.django_db
def test_non_finance_admin_cannot_reach_admin_contracts(parties):
    client_user, freelancer = parties
    assert sign_in(client_user).get("/api/v1/admin/contracts/").status_code == 403

    moderator = make_user("moderator@example.com", admin_role=User.AdminRole.MODERATOR)
    assert sign_in(moderator).get("/api/v1/admin/contracts/").status_code == 403


@pytest.mark.django_db
def test_finance_admin_can_force_fund_a_milestone(awarded, parties):
    _, freelancer = parties
    milestone = _activate(awarded, freelancer)
    finance_admin = make_user("finance-admin2@example.com", admin_role=User.AdminRole.FINANCE_ADMIN)
    assert milestone.status == Milestone.Status.PENDING

    response = sign_in(finance_admin).post(
        f"/api/v1/admin/contracts/{awarded.id}/milestones/{milestone.id}/fund/",
        {"reason": "Client paid by bank transfer, confirmed manually."},
        format="json",
    )
    assert response.status_code == 200
    milestone.refresh_from_db()
    assert milestone.status == Milestone.Status.FUNDED


@pytest.mark.django_db
def test_cannot_force_fund_before_the_contract_is_active(awarded):
    """The admin override is for *how* a milestone gets funded, not licence
    to fund one on a contract the freelancer has not even accepted yet."""
    finance_admin = make_user("finance-admin3@example.com", admin_role=User.AdminRole.FINANCE_ADMIN)
    milestone = awarded.milestones.first()

    response = sign_in(finance_admin).post(
        f"/api/v1/admin/contracts/{awarded.id}/milestones/{milestone.id}/fund/"
    )
    assert response.status_code == 400
    milestone.refresh_from_db()
    assert milestone.status == Milestone.Status.PENDING


@pytest.mark.django_db
def test_cannot_force_fund_an_already_funded_milestone(awarded, parties):
    _, freelancer = parties
    milestone = _activate(awarded, freelancer)
    milestone.fund()
    finance_admin = make_user("finance-admin4@example.com", admin_role=User.AdminRole.FINANCE_ADMIN)

    response = sign_in(finance_admin).post(
        f"/api/v1/admin/contracts/{awarded.id}/milestones/{milestone.id}/fund/"
    )
    assert response.status_code == 400
