"""
Payments (D55).

The Swich callback (public: Swich calls it server to server, so identity
comes entirely from the checksum, never a session), the status of a charge
for the buyer returning from Swich's page, what a buyer can pay with, and a
freelancer's own payout profile and history.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.auth import CanMoveMoney
from core.pagination import StandardPagination

from . import checkout, swich
from .models import Charge, Payout, PayoutProfile, Refund
from .serializers import PayoutProfileSerializer, PayoutSerializer, RefundSerializer

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def payment_options(request):
    """How a buyer can pay, shown at checkout before anyone signs in, and the
    commission a release deducts."""
    return Response(
        {
            "available": checkout.available(),
            "provider": "Swich",
            "methods": swich.METHODS,
            "commission_percent": settings.PLATFORM_COMMISSION_PERCENT,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payout_institutions(request):
    """The banks and wallets a payout can go to through Swich (D56)."""
    from . import institutions

    return Response(
        [
            {"code": code, "name": name, "kind": kind}
            for code, name, kind in institutions.INSTITUTIONS
        ]
    )


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def swich_callback(request):
    """Swich's Pay In result. Never trusted at face value:
    `verify_callback_checksum` is what decides this came from Swich, since
    anyone can call a public URL claiming any outcome. Acknowledged with a
    2xx once handled, including duplicates, so Swich stops retrying."""
    params = request.query_params if request.method == "GET" else request.data
    reference = str(params.get("CustomerTransactionId", ""))
    order_id = str(params.get("OrderId", ""))
    amount = str(params.get("Amount", ""))
    txn_status = str(params.get("Status", ""))
    checksum = str(params.get("checksum", "") or params.get("Checksum", ""))

    if not reference or not checksum:
        return Response({"detail": "missing required parameters"}, status=400)
    if not swich.verify_callback_checksum(
        customer_transaction_id=reference,
        order_id=order_id,
        amount=amount,
        status=txn_status,
        checksum=checksum,
    ):
        logger.warning("swich_callback_bad_checksum ref=%s", reference)
        return Response({"detail": "invalid checksum"}, status=400)

    payload = {key: str(value) for key, value in params.items() if key.lower() != "checksum"}
    outcome = checkout.record_callback(
        reference=reference,
        swich_order_id=order_id,
        amount=amount,
        status=txn_status,
        payload=payload,
    )
    logger.info("swich_callback ref=%s outcome=%s", reference, outcome)
    if outcome == "unknown":
        return Response({"detail": "unknown transaction"}, status=404)
    return Response({"status": outcome})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def charge_status(request, reference):
    """Where a payment stands, for the page a buyer returns to from Swich.
    Only the payer can ask."""
    charge = get_object_or_404(
        Charge.objects.select_related("milestone"), reference=reference, payer=request.user
    )
    return Response(
        {
            "reference": charge.reference,
            "purpose": charge.purpose,
            "status": charge.status,
            "amount": str(charge.amount),
            "order_id": charge.order_id,
            "contract_id": charge.milestone.contract_id if charge.milestone else None,
        }
    )


def checkout_response(charge, url, *, http_status=status.HTTP_201_CREATED, **extra) -> Response:
    """What every "pay" endpoint answers: where to send the buyer."""
    return Response(
        {"checkout_url": url, "payment_reference": charge.reference, **extra}, status=http_status
    )


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


class MyPayoutsView(ListAPIView):
    """A freelancer's own payout history — what was released, the
    platform's cut, what they actually received, and whether it has been
    sent yet."""

    permission_classes = [IsAuthenticated]
    serializer_class = PayoutSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return Payout.objects.filter(freelancer=self.request.user).select_related("milestone")


class MyRefundsView(ListAPIView):
    """A client's own refunds — money returned from escrow after a
    cancellation, and whether it has been sent back yet."""

    permission_classes = [IsAuthenticated]
    serializer_class = RefundSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return Refund.objects.filter(client=self.request.user).select_related("milestone")
