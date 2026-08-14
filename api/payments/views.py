"""
Payments — Phase 3, D41.

Three surfaces: the Swich Pay In callback (public — Swich calls this
server-to-server, so identity comes entirely from the checksum, never from a
session), the freelancer's own payout profile, and their payout history.
"""

from __future__ import annotations

import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.auth import CanMoveMoney
from core.models import NotificationCategory
from core.notify import dispatch
from core.pagination import StandardPagination

from .models import EscrowCharge, Payout, PayoutProfile
from .providers import swich
from .providers.base import SwichError, SwichUnavailable
from .serializers import PayoutProfileSerializer, PayoutSerializer

logger = logging.getLogger(__name__)

#: The status strings Swich's callback has been observed/documented to use.
#: Anything else is treated as a failure — refusing to guess at an unknown
#: status is safer than assuming success.
_SUCCESS_STATUSES = {"success", "paid", "successful", "completed"}


@api_view(["GET"])
@permission_classes([AllowAny])
def swich_payin_callback(request):
    """Swich's Pay In result notification — a GET, per Swich's documented
    shape, acknowledged with any 2xx response.

    Never trusts the query params at face value: `verify_callback_checksum`
    is what actually decides this request came from Swich. Anyone can send
    a GET to a public URL claiming any outcome they like; the checksum is
    the only thing that cannot be forged without `SWICH_SECRET_KEY`.
    """
    params = request.query_params
    customer_transaction_id = params.get("CustomerTransactionId", "")
    order_id = params.get("OrderId", "")
    amount = params.get("Amount", "")
    txn_status = params.get("Status", "")
    checksum = params.get("checksum", "")

    if not customer_transaction_id or not checksum:
        return Response({"detail": "missing required parameters"}, status=400)

    if not swich.verify_callback_checksum(
        customer_transaction_id=customer_transaction_id,
        order_id=order_id,
        amount=amount,
        status=txn_status,
        checksum=checksum,
    ):
        logger.warning("swich_payin_callback_bad_checksum ctid=%s", customer_transaction_id)
        return Response({"detail": "invalid checksum"}, status=400)

    charge = (
        EscrowCharge.objects.select_related("milestone", "milestone__contract")
        .filter(customer_transaction_id=customer_transaction_id)
        .first()
    )
    if charge is None:
        return Response({"detail": "unknown transaction"}, status=404)

    # A callback can arrive more than once (Swich retries undelivered
    # acknowledgements) — once this charge has already resolved, replaying
    # the same outcome is a no-op rather than a double-fund.
    if charge.status != EscrowCharge.Status.CREATED:
        return Response({"status": "already processed"})

    charge.swich_order_id = order_id
    charge.callback_payload = params.dict()
    milestone = charge.milestone

    if txn_status.lower() in _SUCCESS_STATUSES:
        charge.status = EscrowCharge.Status.PAID
        charge.paid_at = timezone.now()
        charge.save(
            update_fields=["status", "swich_order_id", "callback_payload", "paid_at", "updated_at"]
        )

        if milestone.status == milestone.Status.AWAITING_PAYMENT:
            milestone.fund()
            from contracts.models import ContractEvent

            # A gig order (`gigs.models.Order.contract`, related_name
            # `gig_order`) funds through this exact same checkout — it has
            # no separate "milestone funded" moment a client requests, so
            # this callback is also the first true confirmation that an
            # order was actually paid for, not merely started.
            order = getattr(milestone.contract, "gig_order", None)
            if order is not None:
                from django.db.models import F

                from gigs.models import Gig

                Gig.objects.filter(pk=order.gig_id).update(orders_count=F("orders_count") + 1)
                ContractEvent.log(
                    milestone.contract,
                    ContractEvent.Kind.FUNDED,
                    body="Order placed and funded. Waiting for requirements.",
                    milestone_id=milestone.id,
                    amount=str(milestone.amount),
                )
                dispatch(
                    milestone.contract.freelancer,
                    NotificationCategory.ORDER,
                    "New order received",
                    f"{milestone.contract.client.display_name} ordered “{order.gig.title}”.",
                    data={"order_id": order.id},
                )
            else:
                ContractEvent.log(
                    milestone.contract,
                    ContractEvent.Kind.FUNDED,
                    body=f"“{milestone.title}” funded.",
                    milestone_id=milestone.id,
                    amount=str(milestone.amount),
                )
                dispatch(
                    milestone.contract.freelancer,
                    NotificationCategory.PAYMENT,
                    "Milestone funded",
                    f"“{milestone.title}” is funded — you can safely start work.",
                    data={"contract_id": milestone.contract_id},
                )
    else:
        charge.status = EscrowCharge.Status.FAILED
        charge.save(update_fields=["status", "swich_order_id", "callback_payload", "updated_at"])
        if milestone.status == milestone.Status.AWAITING_PAYMENT:
            milestone.mark_payment_failed()

    return Response({"status": "ok"})


class PayoutProfileView(APIView):
    """GET/PATCH the caller's own payout destination. Money-adjacent —
    setting where released funds go is exactly the kind of account change
    `CanMoveMoney` exists to gate (2FA required, same as funding or
    releasing a milestone)."""

    permission_classes = [IsAuthenticated, CanMoveMoney]

    def get(self, request):
        profile, _ = PayoutProfile.objects.get_or_create(user=request.user)
        return Response(PayoutProfileSerializer(profile).data)

    def patch(self, request):
        profile, _ = PayoutProfile.objects.get_or_create(user=request.user)
        serializer = PayoutProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PayoutProfileSerializer(profile).data)


class VerifyPayoutTitleView(APIView):
    """Look up the account holder's name for a bank account before saving
    it as a payout destination — lets the UI show "you're about to be
    paid at: <name>" so a mistyped account number is caught by a name
    mismatch, not discovered when a payout silently goes to a stranger."""

    permission_classes = [IsAuthenticated, CanMoveMoney]

    def post(self, request):
        bank_code = request.data.get("bank_code", "")
        bank_name = request.data.get("bank_name", "")
        account_number = request.data.get("account_number", "")
        msisdn = request.data.get("msisdn", "")
        if not (bank_code and bank_name and account_number and msisdn):
            return Response(
                {"detail": "bank_code, bank_name, account_number and msisdn are all required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = swich.fetch_title(
                bank_code=bank_code,
                bank_name=bank_name,
                account_number=account_number,
                msisdn=msisdn,
                amount="10",
            )
        except SwichUnavailable:
            return Response(
                {
                    "detail": "Payments are not enabled in this environment.",
                    "code": "payments_unavailable",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except SwichError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        title = (result.get("data") or {}).get("accountTitleTo", "")
        return Response({"account_title": title})


class MyPayoutsView(ListAPIView):
    """A freelancer's own payout history — what was sent, when, and what
    failed and why."""

    permission_classes = [IsAuthenticated]
    serializer_class = PayoutSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return Payout.objects.filter(freelancer=self.request.user).select_related("milestone")
