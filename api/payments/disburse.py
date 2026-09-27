"""
Sending money out through Swich: freelancer payouts and buyer refunds (D56).

`settlement` decides what is owed (a `Payout` on release, a `Refund` on
cancellation); this module sends it. Each runs as a Celery task queued once
the row is committed, and again whenever an operator presses "Send through
Swich" in the admin console. Anything Swich refuses stays pending with
Swich's reason in `last_error`, for the operator to fix and resend or to
send by hand; nothing here ever marks money sent that Swich did not confirm.

**Never paying twice.** A payout goes out under a reference that is stored
before the request. Before any new attempt, Swich is asked where the last
reference stands: if it was paid, the payout is marked paid; if Swich is
still working on it, nothing is sent; only a failed or unknown attempt is
retried, under a new reference.

**Checking the name first.** Swich's title fetch returns the name the bank or
wallet holds for the account. If it shares no word with the name on the
payout profile, nothing is sent: a mistyped account number should cost a
message, not the freelancer's money.
"""

from __future__ import annotations

import logging
import re

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import AuditLog, NotificationCategory
from core.notify import dispatch

from . import institutions, swich
from .models import Charge, Payout, PayoutProfile, Refund

logger = logging.getLogger(__name__)

_DONE = {"success", "successful", "completed", "paid", "processed"}
_WORKING = {"pending", "queue", "queued", "processing", "in process", "in progress", "initiated"}


def queue_payout_sending(payout: Payout) -> None:
    """Send a new payout once the release that created it is committed."""
    if swich.payouts_enabled():
        from .tasks import send_payout_task

        transaction.on_commit(lambda: send_payout_task.delay(payout.pk))


def queue_refund_sending(refund: Refund) -> None:
    if swich.payouts_enabled():
        from .tasks import send_refund_task

        transaction.on_commit(lambda: send_refund_task.delay(refund.pk))


def _words(name: str) -> set[str]:
    return {word for word in re.findall(r"[a-z]+", name.lower()) if len(word) >= 3}


def names_agree(on_profile: str, at_bank: str) -> bool:
    """Loose on purpose: banks abbreviate, reorder and add "MR"/"S/O". An
    empty title from Swich is not a mismatch; the bank simply did not say."""
    if not at_bank.strip():
        return True
    return bool(_words(on_profile) & _words(at_bank))


def _fail(record, message: str) -> str:
    record.last_error = message[:1000]
    record.save(update_fields=["last_error", "updated_at"])
    logger.warning("swich_send_failed %s=%s %s", type(record).__name__, record.pk, message)
    return "failed"


def _mark_payout_paid(payout: Payout, swich_id: str) -> str:
    payout.status = Payout.Status.PAID
    payout.paid_at = timezone.now()
    payout.paid_by = None
    payout.note = f"Swich IBFT {swich_id or payout.swich_reference}"
    payout.last_error = ""
    payout.save(update_fields=["status", "paid_at", "paid_by", "note", "last_error", "updated_at"])
    AuditLog.record(
        action=AuditLog.Action.UPDATE,
        target=payout,
        justification=f"Payout sent through Swich ({payout.note}).",
    )
    dispatch(
        payout.freelancer,
        NotificationCategory.PAYMENT,
        "Payment sent",
        f"Rs {payout.net_amount:,.0f} for “{payout.milestone.contract.title}” has been sent to "
        "your bank account or wallet through Swich.",
        data={"contract_id": payout.milestone.contract_id},
    )
    return "paid"


def send_payout(payout_id: int) -> str:
    """Pay one pending payout through Swich. Returns what happened:
    `paid`, `processing`, `failed`, `not_pending` or `disabled`."""
    if not swich.payouts_enabled():
        return "disabled"
    with transaction.atomic():
        payout = (
            Payout.objects.select_for_update(of=("self",))
            .select_related("freelancer", "milestone__contract")
            .get(pk=payout_id)
        )
        if payout.status != Payout.Status.PENDING:
            return "not_pending"

        try:
            if payout.swich_reference:
                previous = swich.inquire_payout(payout.swich_reference)
                state = (previous or {}).get("status_text", "").lower()
                if state in _DONE:
                    return _mark_payout_paid(payout, previous["id"])
                if state in _WORKING:
                    _fail(payout, "Swich is still processing the last attempt.")
                    return "processing"

            profile = PayoutProfile.objects.filter(user=payout.freelancer).first()
            if profile is None or not profile.swich_ready:
                dispatch(
                    payout.freelancer,
                    NotificationCategory.PAYMENT,
                    "Add where to send your payment",
                    f"Rs {payout.net_amount:,.0f} is ready for you. Add your bank account or "
                    "Easypaisa/JazzCash wallet under Settings → Payouts so we can send it.",
                    data={"url": "/settings/payouts"},
                )
                return _fail(
                    payout,
                    "The freelancer has not added a bank account or wallet that Swich can pay "
                    "(Settings → Payouts). They have been asked to.",
                )
            bank_name = institutions.name_of(profile.bank_code) or profile.bank_name
            title = swich.fetch_title(
                bank_code=profile.bank_code,
                bank_name=bank_name,
                account_number=profile.account_number,
                msisdn=profile.msisdn,
                amount=payout.net_amount,
            )
            if not names_agree(profile.account_title, title):
                return _fail(
                    payout,
                    f"The account belongs to “{title}”, not “{profile.account_title}” as on the "
                    "payout profile. Nothing was sent; check the account number with the "
                    "freelancer.",
                )

            payout.swich_attempts += 1
            payout.swich_reference = f"SRPO{payout.pk:07d}-{payout.swich_attempts}"
            payout.save(update_fields=["swich_attempts", "swich_reference", "updated_at"])
            swich_id = swich.send_ibft(
                reference=payout.swich_reference,
                bank_code=profile.bank_code,
                bank_name=bank_name,
                account_number=profile.account_number,
                account_title=title or profile.account_title,
                name=payout.freelancer.full_name or profile.account_title,
                cnic=profile.cnic,
                msisdn=profile.msisdn,
                amount=payout.net_amount,
            )
        except swich.SwichError as exc:
            return _fail(payout, str(exc))
        return _mark_payout_paid(payout, swich_id)


def _paid_charge_for(refund: Refund) -> Charge | None:
    milestone = refund.milestone
    return (
        Charge.objects.filter(status=Charge.Status.PAID)
        .filter(Q(milestone=milestone) | Q(order__contract=milestone.contract_id))
        .exclude(swich_order_id="")
        .order_by("-paid_at")
        .first()
    )


def send_refund(refund_id: int) -> str:
    """Refund one pending refund to the card or wallet it was paid from.
    Swich refunds only some methods; a refusal is left for an operator."""
    if not swich.payouts_enabled():
        return "disabled"
    with transaction.atomic():
        refund = (
            Refund.objects.select_for_update(of=("self",))
            .select_related("client", "milestone__contract")
            .get(pk=refund_id)
        )
        if refund.status != Refund.Status.PENDING:
            return "not_pending"
        charge = _paid_charge_for(refund)
        if charge is None:
            return _fail(
                refund,
                "This payment did not come through Swich, so it cannot be refunded "
                "automatically. Send it by hand and record the reference.",
            )
        try:
            swich.refund_payin(
                swich_order_id=charge.swich_order_id, amount=refund.amount, reason=refund.reason
            )
        except swich.SwichError as exc:
            return _fail(
                refund,
                f"Swich could not refund this payment automatically ({exc}). Send it by hand "
                "and record the reference.",
            )
        refund.status = Refund.Status.REFUNDED
        refund.refunded_at = timezone.now()
        refund.refunded_by = None
        refund.note = f"Swich refund of {charge.swich_order_id}"
        refund.last_error = ""
        refund.save(
            update_fields=[
                "status",
                "refunded_at",
                "refunded_by",
                "note",
                "last_error",
                "updated_at",
            ]
        )
        AuditLog.record(
            action=AuditLog.Action.UPDATE,
            target=refund,
            justification=f"Refunded through Swich ({charge.swich_order_id}).",
        )
        dispatch(
            refund.client,
            NotificationCategory.PAYMENT,
            "Refund sent",
            f"Rs {refund.amount:,.0f} for “{refund.milestone.contract.title}” has been returned "
            "to the card or wallet you paid with. Your bank may take a few working days to show "
            "it.",
            data={"contract_id": refund.milestone.contract_id},
        )
        return "refunded"
