"""
Tests for settlement: refunds on cancellation and the auto-release sweep.

Both close holes where money used to go missing. A cancelled order simply
vanished from the books — nothing recorded that the buyer was owed their
transfer back. And a delivery nobody answered held the seller's money
forever, despite both review windows being promised in notifications.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from contracts.models import Contract, Milestone
from contracts.tests import _activate, _fund
from gigs.models import Order
from gigs.tests import _active_order, _order
from marketplace.tests import sign_in
from payments.models import Payout, Refund
from payments.settlement import auto_release_lapsed, queue_payout

# --- Cancelling a gig order ----------------------------------------------------


@pytest.mark.django_db
def test_a_seller_cancelling_an_active_order_refunds_the_buyer_in_full(gig, buyer, seller):
    order = _active_order(gig, buyer)

    response = sign_in(seller).post(f"/api/v1/orders/{order.pk}/cancel/")

    assert response.status_code == 200, response.data
    order.refresh_from_db()
    assert order.status == Order.Status.CANCELLED
    assert order.contract.status == Contract.Status.CANCELLED
    milestone = order.contract.milestones.first()
    assert milestone.status == Milestone.Status.CANCELLED

    refund = Refund.objects.get(milestone=milestone)
    assert refund.client_id == buyer.pk
    assert refund.amount == order.price
    assert refund.status == Refund.Status.PENDING
    # And the buyer can see it on the order.
    assert response.data["refund"]["status"] == "pending"


@pytest.mark.django_db
def test_a_buyer_may_cancel_before_sending_requirements(gig, buyer):
    order_id = _order(gig, buyer).data["id"]

    response = sign_in(buyer).post(f"/api/v1/orders/{order_id}/cancel/")

    assert response.status_code == 200
    assert Refund.objects.filter(client=buyer, amount=15000).exists()


@pytest.mark.django_db
def test_a_buyer_cannot_cancel_work_the_seller_has_started(gig, buyer):
    """Once requirements are in, the seller is working on the buyer's word."""
    order = _active_order(gig, buyer)
    api = sign_in(buyer)

    detail = api.get(f"/api/v1/orders/{order.pk}/").data
    assert detail["can_cancel"] is False
    assert "due date" in detail["cancel_blocked_reason"]

    response = api.post(f"/api/v1/orders/{order.pk}/cancel/")
    assert response.status_code == 400
    assert response.data["code"] == "cancel_not_allowed"
    assert not Refund.objects.exists()


@pytest.mark.django_db
def test_a_buyer_may_cancel_a_late_order(gig, buyer):
    order = _active_order(gig, buyer)
    Order.objects.filter(pk=order.pk).update(due_at=timezone.now() - timedelta(hours=1))

    response = sign_in(buyer).post(f"/api/v1/orders/{order.pk}/cancel/")

    assert response.status_code == 200
    assert Refund.objects.filter(client=buyer).count() == 1


@pytest.mark.django_db
def test_refunds_are_listed_for_the_client_only(gig, buyer, seller):
    order = _active_order(gig, buyer)
    sign_in(seller).post(f"/api/v1/orders/{order.pk}/cancel/")

    mine = sign_in(buyer).get("/api/v1/payments/refunds/").data
    assert mine["count"] == 1
    assert mine["results"][0]["amount"] == "15000.00"
    assert sign_in(seller).get("/api/v1/payments/refunds/").data["count"] == 0


# --- Cancelling a funded project contract --------------------------------------


@pytest.mark.django_db
def test_a_freelancer_walking_away_refunds_the_client(awarded, parties):
    client_user, freelancer = parties
    milestone = _activate(awarded, freelancer)
    _fund(sign_in(client_user), awarded, milestone)

    response = sign_in(freelancer).post(f"/api/v1/contracts/{awarded.pk}/cancel/")

    assert response.status_code == 200, response.data
    awarded.refresh_from_db()
    assert awarded.status == Contract.Status.CANCELLED
    refund = Refund.objects.get(milestone=milestone)
    assert refund.client_id == client_user.pk
    assert refund.amount == 60000


@pytest.mark.django_db
def test_a_freelancer_cannot_cancel_with_a_delivery_awaiting_review(awarded, parties):
    client_user, freelancer = parties
    milestone = _activate(awarded, freelancer)
    _fund(sign_in(client_user), awarded, milestone)
    milestone.refresh_from_db()
    milestone.deliver()

    response = sign_in(freelancer).post(f"/api/v1/contracts/{awarded.pk}/cancel/")
    assert response.status_code == 400
    assert response.data["code"] == "delivery_pending"


# --- The auto-release sweep ------------------------------------------------------


def _delivered(gig, buyer, seller):
    order = _active_order(gig, buyer)
    sign_in(seller).post(f"/api/v1/orders/{order.pk}/deliver/", {"note": "Done."}, format="json")
    order.refresh_from_db()
    return order


@pytest.mark.django_db
def test_an_unanswered_delivery_is_accepted_when_the_window_lapses(gig, buyer, seller):
    order = _delivered(gig, buyer, seller)

    result = auto_release_lapsed(now=order.accept_by + timedelta(minutes=1))

    assert result["orders"] == 1
    order.refresh_from_db()
    assert order.status == Order.Status.COMPLETED
    payout = Payout.objects.get(milestone=order.contract.milestones.first())
    assert payout.freelancer_id == seller.pk
    assert payout.net_amount == payout.gross_amount - payout.commission_amount


@pytest.mark.django_db
def test_nothing_is_released_before_the_window_closes(gig, buyer, seller):
    order = _delivered(gig, buyer, seller)

    result = auto_release_lapsed(now=order.accept_by - timedelta(minutes=1))

    assert result == {"orders": 0, "milestones": 0}
    order.refresh_from_db()
    assert order.status == Order.Status.DELIVERED


@pytest.mark.django_db
def test_a_revision_request_stops_the_clock(gig, buyer, seller):
    order = _delivered(gig, buyer, seller)
    sign_in(buyer).post(
        f"/api/v1/orders/{order.pk}/request-revision/", {"note": "Tighter spacing."}, format="json"
    )

    auto_release_lapsed(now=timezone.now() + timedelta(days=30))

    order.refresh_from_db()
    assert order.status == Order.Status.REVISION
    assert not Payout.objects.exists()


@pytest.mark.django_db
def test_a_contract_milestone_auto_releases_after_seven_days(awarded, parties):
    client_user, freelancer = parties
    milestone = _activate(awarded, freelancer)
    _fund(sign_in(client_user), awarded, milestone)
    sign_in(freelancer).post(
        f"/api/v1/contracts/{awarded.pk}/milestones/{milestone.pk}/deliver/",
        {"note": "Shipped."},
        format="json",
    )
    milestone.refresh_from_db()

    early = auto_release_lapsed(now=milestone.delivered_at + timedelta(days=6))
    late = auto_release_lapsed(now=milestone.delivered_at + timedelta(days=7, minutes=1))

    assert early["milestones"] == 0
    assert late["milestones"] == 1
    milestone.refresh_from_db()
    awarded.refresh_from_db()
    assert milestone.status == Milestone.Status.RELEASED
    assert awarded.status == Contract.Status.COMPLETED
    assert Payout.objects.filter(milestone=milestone, freelancer=freelancer).exists()


@pytest.mark.django_db
def test_releasing_twice_never_creates_a_second_payout(gig, buyer, seller):
    order = _delivered(gig, buyer, seller)
    milestone = order.contract.milestones.first()

    first = queue_payout(milestone)
    second = queue_payout(milestone)

    assert first.pk == second.pk
    assert Payout.objects.filter(milestone=milestone).count() == 1


# --- No bank account configured ------------------------------------------------


@pytest.mark.django_db
def test_an_order_is_refused_when_there_is_no_account_to_pay_into(gig, buyer, settings):
    """A blank account on the checkout page must not still accept "I've paid"."""
    settings.PLATFORM_BANK_ACCOUNT_NUMBER = ""

    response = _order(gig, buyer)

    assert response.status_code == 503
    assert response.data["code"] == "payments_unavailable"
    assert not Order.objects.exists()


@pytest.mark.django_db
def test_a_milestone_is_not_funded_when_there_is_no_account_to_pay_into(awarded, parties, settings):
    client_user, freelancer = parties
    milestone = _activate(awarded, freelancer)
    settings.PLATFORM_BANK_NAME = ""

    response = sign_in(client_user).post(
        f"/api/v1/contracts/{awarded.pk}/milestones/{milestone.pk}/fund/", {}, format="json"
    )

    assert response.status_code == 503
    milestone.refresh_from_db()
    assert milestone.status == Milestone.Status.PENDING


@pytest.mark.django_db
def test_the_payment_instructions_say_whether_payment_is_possible(buyer, settings):
    api = sign_in(buyer)
    assert api.get("/api/v1/payments/bank-transfer-instructions/").data["available"] is True

    settings.PLATFORM_BANK_ACCOUNT_TITLE = ""
    assert api.get("/api/v1/payments/bank-transfer-instructions/").data["available"] is False
