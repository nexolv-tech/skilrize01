"""
Escrow payments — Phase 3, D42.

No payment gateway sits behind this. A licensed merchant account (Swich or
any other — see D41 for what was tried first) needs an NTN for production
use, and that isn't available yet. Instead: a client funding a milestone
transfers money directly to the platform's own bank account, shown to them
in the UI; the platform manually pays the freelancer out on release, minus
its commission, once someone has actually wired it. Real money moves —
just outside any API this codebase calls. What's here is the bookkeeping
around that transfer and the escrow framing the product presents to both
sides, not a payment integration standing in for one.

`EscrowFunding` and `Payout` are each `OneToOne` on `Milestone`, not
`ForeignKey` — unlike a gateway charge that can fail and retry, funding and
payout here are simple declarations of something that already happened by
hand, so there is exactly one of each per milestone, ever.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from core.crypto import EncryptedTextField
from core.models import TimestampedModel


class EscrowFunding(TimestampedModel):
    """A milestone's money, reported as transferred to the platform's bank
    account. Nothing here verifies the transfer actually happened — there
    is no gateway to ask — so this is the client's own declaration, the
    same trust basis the pre-Phase-3 `Milestone.fund()` always ran on.
    What's real is everything downstream of it: the money is genuinely
    expected to already be in the platform's account by the time a
    freelancer is told to start work.
    """

    milestone = models.OneToOneField(
        "contracts.Milestone", on_delete=models.CASCADE, related_name="funding"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="PKR")
    #: Whatever the client typed as their bank transfer reference — a
    #: courtesy for reconciliation, not a verified value.
    reference_note = models.CharField(max_length=200, blank=True)
    funded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    def __str__(self) -> str:
        return f"EscrowFunding(milestone={self.milestone_id})"


class SubscriptionPayment(TimestampedModel):
    """A subscription period's price, reported as transferred to the
    platform's bank account — the same client-declared trust basis
    `EscrowFunding` runs on, just for plan billing instead of a milestone.

    Unlike escrow there is nothing to release later: the whole amount is
    the platform's, so there is no matching `Payout` on the other end —
    one row per period is the full record.
    """

    subscription = models.ForeignKey(
        "professional.Subscription", on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="PKR")
    reference_note = models.CharField(max_length=200, blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"SubscriptionPayment(subscription={self.subscription_id})"


class PayoutProfile(TimestampedModel):
    """Where a freelancer's released milestone money actually goes, for
    whoever on the platform side sends the manual bank transfer to read.

    `account_number` and `cnic` are `EncryptedTextField` for the same
    reason the OTP secrets in `accounts.models` are — a bank account
    number and a national ID card number are exactly the pair a breach
    turns into fraud, and neither needs to be searched or filtered on,
    only read back once when a payout is being sent.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payout_profile"
    )
    bank_name = models.CharField(max_length=100, blank=True)
    account_title = models.CharField(max_length=200, blank=True)
    account_number = EncryptedTextField(blank=True)
    cnic = EncryptedTextField(blank=True)
    msisdn = models.CharField(max_length=20, blank=True)

    @property
    def is_complete(self) -> bool:
        return bool(self.bank_name and self.account_title and self.account_number and self.cnic)

    def __str__(self) -> str:
        return f"PayoutProfile({self.user_id})"


class Payout(TimestampedModel):
    """One milestone's release, split into what the freelancer receives
    and what the platform keeps — and, until someone on the platform side
    actually wires it, a queue item rather than a completed transaction.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"

    milestone = models.OneToOneField(
        "contracts.Milestone", on_delete=models.CASCADE, related_name="payout"
    )
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payouts_received"
    )
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    #: Snapshotted at release time, not read live from settings later —
    #: a rate change must never rewrite what an already-released milestone
    #: is recorded as having charged.
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="PKR")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    #: A transfer reference, a note on which admin sent it — whatever
    #: makes this payout traceable back to the real bank transfer.
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["freelancer", "status"])]

    @classmethod
    def compute(cls, *, milestone, freelancer, commission_percent: Decimal) -> Payout:
        """Builds (but does not save) a `Payout` from a milestone amount
        and a commission rate — the one place the split arithmetic lives,
        so `release_milestone` and any admin tooling agree on it exactly."""
        gross = milestone.amount
        commission = (gross * commission_percent / Decimal("100")).quantize(Decimal("0.01"))
        return cls(
            milestone=milestone,
            freelancer=freelancer,
            gross_amount=gross,
            commission_percent=commission_percent,
            commission_amount=commission,
            net_amount=gross - commission,
        )

    def __str__(self) -> str:
        return f"Payout(milestone={self.milestone_id}, {self.status})"
