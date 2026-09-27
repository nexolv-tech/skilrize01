"""
Settlement — the only two ways money leaves escrow.

**Release** sends a milestone's money forward to the freelancer, minus the
platform's commission, as a `Payout`. **Refund** sends it back to the client,
as a `Refund`. Money comes in through Swich (`payments.checkout`, D55); an
operator sends payouts and refunds and records them in the admin console.
What lives here is the bookkeeping, and it lives here once.

Every path that settles escrow goes through these functions: a client
releasing a milestone, a buyer accepting a gig order, the auto-release sweep
when a delivery goes unanswered, and every kind of cancellation. Before this
module the release arithmetic was copied into two views and the refund side
did not exist at all.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Payout, Refund

#: Milestone states in which the client's money is sitting in escrow.
HELD_STATES = ("funded", "in_progress", "delivered")


def commission_percent() -> Decimal:
    return Decimal(str(settings.PLATFORM_COMMISSION_PERCENT))


def queue_payout(milestone) -> Payout:
    """Release a delivered milestone and record the freelancer's payout.

    Idempotent against a second call for the same milestone: a milestone has
    at most one payout (`Payout.milestone` is one-to-one), so a double release
    returns the existing row instead of raising.
    """
    existing = Payout.objects.filter(milestone=milestone).first()
    if existing is not None:
        return existing

    milestone.release()
    payout = Payout.compute(
        milestone=milestone,
        freelancer=milestone.contract.freelancer,
        commission_percent=commission_percent(),
    )
    payout.save()
    # Paid automatically through Swich once this release is committed (D56).
    from .disburse import queue_payout_sending

    queue_payout_sending(payout)
    return payout


def queue_refund(milestone, *, reason: str, actor=None) -> Refund | None:
    """Cancel a funded, undelivered milestone and record the client's refund.

    Returns `None` for a milestone that never held money (nothing to give
    back), so callers can cancel every milestone on a contract without
    checking each one first.
    """
    from contracts.models import Milestone

    if milestone.status not in HELD_STATES:
        if milestone.status == Milestone.Status.PENDING:
            milestone.status = Milestone.Status.CANCELLED
            milestone.save(update_fields=["status", "updated_at"])
        return None

    funding = getattr(milestone, "funding", None)
    amount = funding.amount if funding is not None else milestone.amount

    milestone.status = Milestone.Status.CANCELLED
    milestone.save(update_fields=["status", "updated_at"])
    refund = Refund.objects.create(
        milestone=milestone,
        client=milestone.contract.client,
        amount=amount,
        reason=reason[:200],
        requested_by=actor,
    )
    # Returned to the card or wallet automatically through Swich (D56).
    from .disburse import queue_refund_sending

    queue_refund_sending(refund)
    return refund


@transaction.atomic
def void_unpaid_order(order, *, actor, note: str = "") -> bool:
    """Cancel an order whose payment never arrived — without a refund.

    An order starts on the buyer's word that they paid (D42). When the money
    never reaches the platform's account, the Terms let the platform cancel
    the order after three business days. Every other cancellation path goes
    through `queue_refund`, which would record a refund owed for money that
    was never received; this one closes the order and its contract with
    nothing owed either way. Delivered or finished orders are refused: by
    then the question is a dispute, not a missing payment.
    """
    from contracts.models import Contract, ContractEvent, Milestone
    from core.models import AuditLog, NotificationCategory
    from core.notify import dispatch
    from gigs.models import Order

    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in (Order.Status.PENDING_REQUIREMENTS, Order.Status.ACTIVE):
        return False

    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    if order.contract is not None:
        order.contract.milestones.exclude(
            status__in=(Milestone.Status.RELEASED, Milestone.Status.CANCELLED)
        ).update(status=Milestone.Status.CANCELLED, updated_at=timezone.now())
        order.contract.status = Contract.Status.CANCELLED
        order.contract.ended_at = timezone.now()
        order.contract.save(update_fields=["status", "ended_at", "updated_at"])
        ContractEvent.log(
            order.contract,
            ContractEvent.Kind.STATUS,
            actor=actor,
            body="Order cancelled: the buyer's payment was never received.",
        )

    AuditLog.record(
        actor=actor,
        action=AuditLog.Action.UPDATE,
        target=order,
        justification=("Order voided, payment not received. " + note).strip()[:500],
    )
    for party, text in (
        (
            order.buyer,
            f"We did not receive your payment for “{order.gig.title}”, so the order was "
            "cancelled. If you did pay, reply with your payment reference.",
        ),
        (
            order.seller,
            f"The buyer's payment for “{order.gig.title}” never arrived, so the order was "
            "cancelled. Please stop any work on it.",
        ),
    ):
        dispatch(
            party,
            NotificationCategory.ORDER,
            "Order cancelled — payment not received",
            text,
            data={"order_id": order.id},
        )
    return True


# --- The auto-release sweep --------------------------------------------------


@transaction.atomic
def _auto_complete_order(order) -> bool:
    """Accept a delivered gig order on the buyer's behalf once the acceptance
    window has lapsed. Mirrors `OrderViewSet.accept` exactly, because the
    promise it keeps is the one that endpoint's notification made."""
    from contracts.models import ContractEvent, Milestone
    from core.models import AuditLog, NotificationCategory
    from core.notify import dispatch
    from gigs.models import Order

    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != Order.Status.DELIVERED:
        return False

    milestone = order.contract.milestones.first() if order.contract else None
    if milestone and milestone.status == Milestone.Status.DELIVERED:
        queue_payout(milestone)
    if order.contract:
        order.contract.complete()
    order.complete()

    if order.contract:
        ContractEvent.log(
            order.contract,
            ContractEvent.Kind.RELEASED,
            body=(
                f"No response within {Order.ACCEPTANCE_WINDOW_DAYS} days of delivery — "
                f"the order was accepted automatically and Rs {order.price} released from escrow."
            ),
        )
    AuditLog.record(
        action=AuditLog.Action.UPDATE,
        target=order,
        justification="Gig order auto-accepted after the acceptance window lapsed.",
    )
    for party in (order.buyer, order.seller):
        dispatch(
            party,
            NotificationCategory.ORDER,
            "Order completed automatically",
            f"“{order.gig.title}” was accepted automatically after the review window closed.",
            data={"order_id": order.id, "contract_id": order.contract_id},
        )
    return True


@transaction.atomic
def _auto_release_milestone(milestone) -> bool:
    """Release a contract milestone whose review window has lapsed."""
    from contracts.models import Contract, ContractEvent, Milestone
    from core.models import AuditLog, NotificationCategory
    from core.notify import dispatch

    milestone = Milestone.objects.select_for_update().get(pk=milestone.pk)
    if milestone.status != Milestone.Status.DELIVERED:
        return False

    contract = milestone.contract
    queue_payout(milestone)
    ContractEvent.log(
        contract,
        ContractEvent.Kind.RELEASED,
        body=(
            f"No response within {Contract.REVIEW_WINDOW_DAYS} days of delivery — "
            f"“{milestone.title}” was released from escrow automatically."
        ),
        milestone_id=milestone.id,
        amount=str(milestone.amount),
    )
    AuditLog.record(
        action=AuditLog.Action.UPDATE,
        target=milestone,
        justification="Milestone auto-released after the review window lapsed.",
    )

    outstanding = contract.milestones.exclude(
        status__in=[Milestone.Status.RELEASED, Milestone.Status.CANCELLED]
    ).exists()
    if not outstanding:
        contract.complete()
        ContractEvent.log(contract, ContractEvent.Kind.STATUS, body="Contract completed.")

    for party in (contract.client, contract.freelancer):
        dispatch(
            party,
            NotificationCategory.PAYMENT,
            "Payment released automatically",
            f"“{milestone.title}” was released after the review window closed.",
            data={"contract_id": contract.id},
        )
    return True


def auto_release_lapsed(*, now=None, limit: int = 200) -> dict:
    """Settle every delivery nobody answered in time.

    Escrow that only one side can end is not escrow, it is a hostage: a
    client who simply never responds to a delivery would otherwise hold the
    freelancer's money forever. Both review windows were defined from the
    start (`Order.ACCEPTANCE_WINDOW_DAYS`, `Contract.REVIEW_WINDOW_DAYS`) and
    promised to users in notifications — nothing enforced them until this.

    A revision request resets the window (`Order.request_revision` clears
    `accept_by`), so only genuinely unanswered deliveries are released.
    """
    from contracts.models import Contract, Milestone
    from gigs.models import Order

    now = now or timezone.now()

    orders = list(
        Order.objects.filter(status=Order.Status.DELIVERED, accept_by__lte=now)
        .select_related("gig", "buyer", "seller", "contract")
        .order_by("accept_by")[:limit]
    )
    orders_done = sum(1 for order in orders if _auto_complete_order(order))

    # Gig-order milestones are settled through their order above; this pass
    # is for milestones on project contracts only.
    cutoff = now - timedelta(days=Contract.REVIEW_WINDOW_DAYS)
    milestones = list(
        Milestone.objects.filter(
            status=Milestone.Status.DELIVERED,
            delivered_at__lte=cutoff,
            contract__gig_order__isnull=True,
        )
        .select_related("contract")
        .order_by("delivered_at")[:limit]
    )
    milestones_done = sum(1 for milestone in milestones if _auto_release_milestone(milestone))

    return {"orders": orders_done, "milestones": milestones_done}
