"""Background payout processing — Phase 3, D41.

`release_milestone` (`contracts/views.py`) creates a `Payout` row and hands
off to `process_payout` rather than calling Swich inline: an IBFT call is a
network round-trip to a third party, and the client releasing a milestone
should not sit on an HTTP request waiting for it. The retry shape mirrors
`core.tasks.deliver_notification` — bounded retries, and a `Payout` that
ends `FAILED` rather than looping forever once they're exhausted.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from core.models import NotificationCategory
from core.notify import dispatch

from .providers import swich
from .providers.base import SwichError, SwichUnavailable

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_payout(self, payout_id: int) -> str:
    from .models import Payout, PayoutProfile

    payout = Payout.objects.select_related("milestone", "freelancer").filter(pk=payout_id).first()
    if payout is None:
        return "missing"
    if payout.status == Payout.Status.PAID:
        return "already_paid"

    profile = PayoutProfile.objects.filter(user=payout.freelancer).first()
    if profile is None or not profile.is_complete:
        payout.status = Payout.Status.FAILED
        payout.failure_reason = "Freelancer payout profile is incomplete."
        payout.save(update_fields=["status", "failure_reason", "updated_at"])
        return "no_profile"

    payout.status = Payout.Status.PROCESSING
    payout.save(update_fields=["status", "updated_at"])

    try:
        result = swich.create_payout(
            customer_transaction_id=payout.customer_transaction_id,
            account_number=profile.account_number,
            account_title=profile.verified_account_title or payout.freelancer.display_name,
            amount=str(payout.amount),
            bank_code=profile.bank_code,
            bank_name=profile.bank_name,
            cnic=profile.cnic,
            msisdn=profile.msisdn,
            name=payout.freelancer.display_name,
            currency=payout.currency,
        )
    except SwichUnavailable:
        payout.status = Payout.Status.FAILED
        payout.failure_reason = "Payments provider is not enabled in this environment."
        payout.save(update_fields=["status", "failure_reason", "updated_at"])
        return "provider_unavailable"
    except SwichError as exc:
        if self.request.retries >= self.max_retries:
            payout.status = Payout.Status.FAILED
            payout.failure_reason = str(exc)[:2000]
            payout.save(update_fields=["status", "failure_reason", "updated_at"])
            logger.error("payout_failed_final payout=%s error=%s", payout_id, exc)
            dispatch(
                payout.freelancer,
                NotificationCategory.PAYMENT,
                "Payout could not be completed",
                (
                    f"We could not send Rs {payout.amount} for “{payout.milestone.title}” to your "
                    "bank account. Please check your payout details and contact support."
                ),
                data={"contract_id": payout.milestone.contract_id},
            )
            return "failed"
        raise self.retry(exc=exc) from exc

    payout.status = Payout.Status.PAID
    payout.swich_response = result
    payout.paid_at = timezone.now()
    payout.save(update_fields=["status", "swich_response", "paid_at", "updated_at"])

    dispatch(
        payout.freelancer,
        NotificationCategory.PAYMENT,
        "Payout sent",
        f"Rs {payout.amount} was sent to your bank account for “{payout.milestone.title}”.",
        data={"contract_id": payout.milestone.contract_id},
    )
    return "paid"
