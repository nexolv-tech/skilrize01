"""
Escrow payments — Phase 3, D42.

No payment gateway sits behind this. A licensed merchant account (Swich or
any other — see D41 for what was tried first) needs an NTN for production
use, which the operator did not have when this was built; that merchant
account is being applied for again (D48). Instead: a client funding a milestone
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
    """A milestone's money, held in escrow. Created when Swich's
    checksum-verified callback confirms the payment (`payments.checkout`,
    D55), already confirmed; or recorded by an admin for money received
    another way, in which case it waits in the console until someone
    matches it against the statement (D54). Records made before D55 were
    buyers' own bank-transfer declarations (D42)."""

    milestone = models.OneToOneField(
        "contracts.Milestone", on_delete=models.CASCADE, related_name="funding"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="PKR")
    #: Swich's transaction id ("Swich …"), or whatever reference was
    #: recorded with a payment taken another way.
    reference_note = models.CharField(max_length=200, blank=True)
    funded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    #: Set when an operator finds the transfer on the bank statement (admin
    #: console, Payments). Until then the funding is the client's word only.
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    def __str__(self) -> str:
        return f"EscrowFunding(milestone={self.milestone_id})"


class SubscriptionPayment(TimestampedModel):
    """A subscription period's price, paid through Swich (D55) and
    confirmed by its callback, the way `EscrowFunding` is for escrow.

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
    #: As on `EscrowFunding`: set once the transfer is seen in the bank.
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
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
    #: The bank or wallet as Swich knows it (`payments.institutions`), which
    #: is what lets a payout go out automatically (D56). Blank for a bank
    #: typed in by hand, which an operator pays instead.
    bank_code = models.CharField(max_length=12, blank=True)

    @property
    def is_complete(self) -> bool:
        return bool(self.bank_name and self.account_title and self.account_number and self.cnic)

    @property
    def swich_ready(self) -> bool:
        """Everything Swich's IBFT needs: a listed bank or wallet, and the
        mobile number it asks for with every payout."""
        return bool(self.is_complete and self.bank_code and self.msisdn)

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
    #: The customerTransactionId of the latest attempt through Swich (D56),
    #: asked about before any new attempt so nobody is paid twice.
    swich_reference = models.CharField(max_length=40, blank=True)
    swich_attempts = models.PositiveSmallIntegerField(default=0)
    #: Why the last attempt did not go through, in Swich's words.
    last_error = models.TextField(blank=True)

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


class Refund(TimestampedModel):
    """A funded milestone that will never be delivered, owed back to the
    client — the mirror image of `Payout`.

    Created whenever escrowed money has to go back rather than forward: a
    seller cancelling an order, a buyer cancelling before work starts or
    after a missed deadline, a freelancer walking away from a funded
    contract. Until this model existed a cancellation simply closed the
    order, and the money the buyer had already transferred vanished from
    the books — nothing recorded that it was owed back to anyone.

    Sent by hand like a payout: an admin transfers `amount` back to the
    client and marks the row refunded.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        REFUNDED = "refunded", "Refunded"

    milestone = models.OneToOneField(
        "contracts.Milestone", on_delete=models.CASCADE, related_name="refund"
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="refunds_received"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="PKR")
    reason = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    refunded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    refunded_at = models.DateTimeField(null=True, blank=True)
    #: The bank transfer reference for the money sent back.
    note = models.TextField(blank=True)
    #: Why Swich could not refund it automatically (D56), when it could not.
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["client", "status"])]

    def __str__(self) -> str:
        return f"Refund(milestone={self.milestone_id}, {self.status})"


class Charge(TimestampedModel):
    """One attempt to take a payment through Swich's hosted checkout (D55).

    A buyer can abandon Swich's page or have a card declined and try again,
    so an order or milestone can have several charges; at most one ends
    `paid`. The `reference` is what Swich calls the customerTransactionId:
    it is how the callback finds this row, and it never repeats.
    """

    class Purpose(models.TextChoices):
        ORDER = "order", "Service order"
        MILESTONE = "milestone", "Milestone"
        PLAN = "plan", "Plan"

    class Status(models.TextChoices):
        CREATED = "created", "Waiting for payment"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    reference = models.CharField(max_length=40, unique=True)
    purpose = models.CharField(max_length=10, choices=Purpose.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CREATED)
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="charges"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="PKR")
    milestone = models.ForeignKey(
        "contracts.Milestone",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="charges",
    )
    order = models.ForeignKey(
        "gigs.Order", null=True, blank=True, on_delete=models.CASCADE, related_name="charges"
    )
    plan = models.ForeignKey(
        "professional.Plan", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    interval = models.CharField(max_length=10, blank=True)
    #: Swich's own id for the payment, from the callback.
    swich_order_id = models.CharField(max_length=80, blank=True)
    callback_payload = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self) -> str:
        return f"Charge({self.reference}, {self.purpose}, {self.status})"
