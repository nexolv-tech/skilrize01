"""Background sending of payouts and refunds through Swich (D56)."""

from __future__ import annotations

from celery import shared_task


@shared_task
def send_payout_task(payout_id: int) -> str:
    from .disburse import send_payout

    return send_payout(payout_id)


@shared_task
def send_refund_task(refund_id: int) -> str:
    from .disburse import send_refund

    return send_refund(refund_id)
