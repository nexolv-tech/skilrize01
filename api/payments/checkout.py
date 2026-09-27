"""
Taking a payment through Swich, and what happens once it lands (D55).

`start` records a `Charge` and returns the URL of Swich's hosted checkout.
Nothing is funded then: the buyer may never finish. `settle` runs from the
checksum-verified Swich callback only, and is what funds a milestone, opens
an order to its seller, or starts a plan. It runs at most once per charge,
since Swich retries callbacks it thinks were not received.
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from core.models import AuditLog, NotificationCategory
from core.notify import dispatch

from . import swich
from .models import Charge, EscrowFunding, SubscriptionPayment

logger = logging.getLogger(__name__)

#: Statuses Swich's callback uses for a completed payment. Anything else is a
#: failure: guessing that an unknown status meant success would fund work
#: nobody paid for.
SUCCESS_STATUSES = {"success", "paid", "successful", "completed"}

PAYMENTS_UNAVAILABLE = {
    "detail": (
        "Card and wallet payments are opening shortly. Nothing has been charged, and no "
        "order was placed."
    ),
    "code": "payments_unavailable",
}


def available() -> bool:
    return swich.is_enabled()


def _reference() -> str:
    return f"SR{timezone.now():%y%m%d}{secrets.token_hex(8).upper()}"


def start(
    *,
    purpose: str,
    payer,
    amount: Decimal,
    item: str,
    description: str,
    milestone=None,
    order=None,
    plan=None,
    interval: str = "",
) -> tuple[Charge, str]:
    """Record a charge and build the checkout URL the buyer is sent to.
    Raises `swich.SwichUnavailable` when payments are not configured."""
    if not available():
        raise swich.SwichUnavailable("Swich is not enabled on this server.")
    charge = Charge.objects.create(
        reference=_reference(),
        purpose=purpose,
        payer=payer,
        amount=amount,
        milestone=milestone,
        order=order,
        plan=plan,
        interval=interval,
    )
    url = swich.build_checkout_url(
        customer_transaction_id=charge.reference,
        amount=f"{charge.amount:.2f}",
        item=item[:100],
        description=description[:200],
        payee_name=payer.display_name,
        email=payer.email,
        msisdn=payer.phone_number or "",
        success_redirect_url=f"{settings.FRONTEND_URL}/payments/return?ref={charge.reference}",
    )
    return charge, url


def _same_amount(reported: str, expected: Decimal) -> bool:
    try:
        return Decimal(reported) == expected
    except (InvalidOperation, TypeError):
        return False


@transaction.atomic
def record_callback(
    *, reference: str, swich_order_id: str, amount: str, status: str, payload: dict
) -> str:
    """Apply a verified Swich callback. Returns what happened, for the log and
    the response: `paid`, `failed`, `duplicate`, `unknown` or `amount_mismatch`."""
    charge = Charge.objects.select_for_update().filter(reference=reference).first()
    if charge is None:
        return "unknown"
    if charge.status in (Charge.Status.PAID, Charge.Status.FAILED):
        return "duplicate"

    charge.swich_order_id = swich_order_id[:80]
    charge.callback_payload = payload
    if status.lower() not in SUCCESS_STATUSES:
        charge.status = Charge.Status.FAILED
        charge.save(update_fields=["status", "swich_order_id", "callback_payload", "updated_at"])
        dispatch(
            charge.payer,
            NotificationCategory.PAYMENT,
            "Payment not completed",
            "Your payment did not go through, and nothing was charged. You can try again from "
            "the same page.",
            data=_where(charge),
        )
        return "failed"
    if not _same_amount(amount, charge.amount):
        # A valid checksum over a different amount should be impossible; if it
        # happens, a person looks before anything is funded.
        logger.error(
            "swich_amount_mismatch ref=%s expected=%s reported=%s", reference, charge.amount, amount
        )
        charge.callback_payload = {**payload, "_mismatch": True}
        charge.save(update_fields=["swich_order_id", "callback_payload", "updated_at"])
        return "amount_mismatch"

    charge.status = Charge.Status.PAID
    charge.paid_at = timezone.now()
    charge.save(
        update_fields=["status", "swich_order_id", "callback_payload", "paid_at", "updated_at"]
    )
    {
        Charge.Purpose.ORDER: _settle_order,
        Charge.Purpose.MILESTONE: _settle_milestone,
        Charge.Purpose.PLAN: _settle_plan,
    }[charge.purpose](charge)
    AuditLog.record(
        actor=charge.payer,
        action=AuditLog.Action.CREATE,
        target=charge,
        justification=f"Paid through Swich ({charge.swich_order_id or 'no order id'}).",
    )
    return "paid"


def _where(charge: Charge) -> dict:
    if charge.order_id:
        return {"order_id": charge.order_id}
    if charge.milestone_id:
        return {"contract_id": charge.milestone.contract_id}
    return {"url": "/pricing"}


def _fund(charge: Charge, milestone) -> None:
    EscrowFunding.objects.update_or_create(
        milestone=milestone,
        defaults={
            "amount": charge.amount,
            "reference_note": f"Swich {charge.swich_order_id or charge.reference}"[:200],
            "funded_by": charge.payer,
            "confirmed_at": charge.paid_at,
            "confirmed_by": None,
        },
    )
    milestone.fund()


def _settle_order(charge: Charge) -> None:
    from contracts.models import Contract, ContractEvent, Milestone
    from gigs.models import Gig, Order

    order = (
        Order.objects.select_for_update(of=("self",))
        .select_related("gig", "contract")
        .get(pk=charge.order_id)
    )
    if order.status != Order.Status.AWAITING_PAYMENT:
        # Cancelled (or expired) while the buyer was on Swich's page: the
        # money came in for an order that no longer stands, so it goes back.
        _refund_orphan(charge, f"Order #{order.pk} was closed before its payment arrived.")
        return
    contract = order.contract
    milestone = contract.milestones.filter(status=Milestone.Status.PENDING).first()
    if contract.status == Contract.Status.PENDING:
        contract.accept()
    _fund(charge, milestone)
    order.status = Order.Status.PENDING_REQUIREMENTS
    order.save(update_fields=["status", "updated_at"])
    Gig.objects.filter(pk=order.gig_id).update(orders_count=F("orders_count") + 1)
    ContractEvent.log(
        contract,
        ContractEvent.Kind.FUNDED,
        actor=charge.payer,
        body="Order paid and held in escrow. Waiting for requirements.",
        milestone_id=milestone.id,
        amount=str(charge.amount),
    )
    dispatch(
        order.seller,
        NotificationCategory.ORDER,
        "New order received",
        f"{order.buyer.display_name} ordered “{order.gig.title}”. The payment is held in escrow.",
        data={"order_id": order.id},
    )
    dispatch(
        order.buyer,
        NotificationCategory.PAYMENT,
        "Payment received",
        f"Rs {charge.amount:,.0f} for “{order.gig.title}” is held in escrow until you accept "
        "the delivery. Next, send the seller your requirements.",
        data={"order_id": order.id},
    )


def _settle_milestone(charge: Charge) -> None:
    from contracts.models import Contract, ContractEvent, Milestone

    milestone = (
        Milestone.objects.select_for_update().select_related("contract").get(pk=charge.milestone_id)
    )
    contract = milestone.contract
    if milestone.status != Milestone.Status.PENDING or contract.status != Contract.Status.ACTIVE:
        _refund_orphan(
            charge, f"“{milestone.title}” could no longer be funded when payment arrived."
        )
        return
    _fund(charge, milestone)
    ContractEvent.log(
        contract,
        ContractEvent.Kind.FUNDED,
        actor=charge.payer,
        body=f"“{milestone.title}” paid and held in escrow.",
        milestone_id=milestone.id,
        amount=str(charge.amount),
    )
    dispatch(
        contract.freelancer,
        NotificationCategory.PAYMENT,
        "Milestone funded",
        f"“{milestone.title}” is paid and held in escrow. You can start work.",
        data={"contract_id": contract.id},
    )
    dispatch(
        charge.payer,
        NotificationCategory.PAYMENT,
        "Payment received",
        f"Rs {charge.amount:,.0f} for “{milestone.title}” is held in escrow until you approve "
        "the work.",
        data={"contract_id": contract.id},
    )


def _settle_plan(charge: Charge) -> None:
    from professional.models import Subscription

    now = timezone.now()
    Subscription.objects.filter(user=charge.payer, status__in=Subscription.LIVE_STATUSES).update(
        status=Subscription.Status.CANCELLED, cancelled_at=now, updated_at=now
    )
    span = timedelta(days=365 if charge.interval == Subscription.Interval.YEARLY else 30)
    subscription = Subscription.objects.create(
        user=charge.payer,
        plan=charge.plan,
        interval=charge.interval or Subscription.Interval.MONTHLY,
        status=Subscription.Status.ACTIVE,
        current_period_end=now + span,
    )
    SubscriptionPayment.objects.create(
        subscription=subscription,
        amount=charge.amount,
        reference_note=f"Swich {charge.swich_order_id or charge.reference}"[:200],
        paid_by=charge.payer,
        confirmed_at=charge.paid_at,
    )
    dispatch(
        charge.payer,
        NotificationCategory.PAYMENT,
        f"You are on {charge.plan.name}",
        "Payment received. Your new limits are active now.",
        data={"url": "/pricing"},
    )


def _refund_orphan(charge: Charge, reason: str) -> None:
    """Money arrived for something that no longer stands. Recorded as owed
    back; an operator refunds it from the admin console."""
    from .models import Refund

    if charge.milestone_id or charge.order_id:
        milestone = charge.milestone
        if milestone is None and charge.order is not None and charge.order.contract is not None:
            milestone = charge.order.contract.milestones.first()
        if milestone is not None and not Refund.objects.filter(milestone=milestone).exists():
            Refund.objects.create(
                milestone=milestone, client=charge.payer, amount=charge.amount, reason=reason[:200]
            )
    logger.warning("swich_payment_for_closed_item ref=%s reason=%s", charge.reference, reason)
    dispatch(
        charge.payer,
        NotificationCategory.PAYMENT,
        "Your payment will be refunded",
        f"{reason} Rs {charge.amount:,.0f} will be refunded to you.",
        data=_where(charge),
    )


def expire_unpaid(*, now=None) -> dict:
    """Close checkouts nobody finished: charges left waiting, and orders that
    were never paid for. Nothing was taken, so nothing is refunded."""
    from contracts.models import Contract, Milestone
    from gigs.models import Order

    now = now or timezone.now()
    cutoff = now - timedelta(hours=settings.UNPAID_ORDER_HOURS)
    charges = Charge.objects.filter(status=Charge.Status.CREATED, created_at__lt=cutoff).update(
        status=Charge.Status.EXPIRED, updated_at=now
    )
    orders = 0
    for order in Order.objects.filter(
        status=Order.Status.AWAITING_PAYMENT, created_at__lt=cutoff
    ).select_related("contract", "gig", "buyer"):
        with transaction.atomic():
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status", "updated_at"])
            if order.contract is not None:
                order.contract.milestones.filter(status=Milestone.Status.PENDING).update(
                    status=Milestone.Status.CANCELLED, updated_at=now
                )
                order.contract.status = Contract.Status.CANCELLED
                order.contract.ended_at = now
                order.contract.save(update_fields=["status", "ended_at", "updated_at"])
            dispatch(
                order.buyer,
                NotificationCategory.ORDER,
                "Unpaid order closed",
                f"Your order for “{order.gig.title}” was not paid within "
                f"{settings.UNPAID_ORDER_HOURS} hours, so it was closed. Nothing was charged.",
                data={"order_id": order.id},
            )
        orders += 1
    return {"charges": charges, "orders": orders}
