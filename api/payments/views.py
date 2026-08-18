"""
Payments — Phase 3, D42.

Two surfaces: the freelancer's own payout profile (where a manual bank
transfer should go), and their payout history. There is no callback view
here — nothing calls back, because there is no gateway; funding and
release both happen inside `contracts.views` and `gigs.views`, gated the
same way every other money-adjacent endpoint in this codebase is.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.auth import CanMoveMoney
from core.pagination import StandardPagination

from .models import Payout, PayoutProfile
from .serializers import PayoutProfileSerializer, PayoutSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bank_transfer_instructions(request):
    """Where to actually send money to fund a milestone or order — the
    one piece of real payment infrastructure this phase has: the
    platform's own bank account (Phase 3, D42)."""
    return Response(
        {
            "bank_name": settings.PLATFORM_BANK_NAME,
            "account_title": settings.PLATFORM_BANK_ACCOUNT_TITLE,
            "account_number": settings.PLATFORM_BANK_ACCOUNT_NUMBER,
            "commission_percent": settings.PLATFORM_COMMISSION_PERCENT,
        }
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
