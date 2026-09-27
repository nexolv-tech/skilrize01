"""
Contracts, milestones, the work diary, and reviews.

This is where an accepted proposal becomes an obligation. Two things here are
load-bearing and worth stating plainly:

**Terms are frozen at acceptance.** A contract stores its own snapshot of what
was agreed. Editing the originating project afterwards must not silently change
what someone signed up to, so nothing downstream reads the project for terms.

**Money moves through states, never by assignment.** No phase-1 code sets a
balance. Milestones advance through funding, delivery, and release, and each
transition is recorded. Phase 3 replaces the manual admin funding step with a
real gateway and a double-entry ledger; the state machine it plugs into is the
one written here.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import ScopedModel, TimestampedModel

#: Every rating on this platform is 1–5 stars, so the constraint is declared
#: once rather than repeated across seven fields.
STARS = {"validators": [MinValueValidator(1), MaxValueValidator(5)]}


class ContractType(models.TextChoices):
    FIXED = "fixed", "Fixed price"
    MILESTONE = "milestone", "Fixed price, milestones"
    HOURLY = "hourly", "Hourly"


class Contract(ScopedModel):
    """The agreement between one client and one freelancer."""

    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting acceptance"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        DELIVERED = "delivered", "Delivered, awaiting review"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        DISPUTED = "disputed", "Disputed"

    #: Section 18.2 — if a client can hold a delivery in limbo indefinitely by
    #: not responding, escrow protects only one side. The review window expires
    #: into automatic release.
    REVIEW_WINDOW_DAYS = 7

    project = models.ForeignKey(
        "marketplace.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contracts",
    )
    proposal = models.OneToOneField(
        "marketplace.Proposal",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contract",
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="contracts_as_client"
    )
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="contracts_as_freelancer"
    )

    title = models.CharField(max_length=200)
    contract_type = models.CharField(max_length=12, choices=ContractType.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)

    #: Fixed and milestone contracts.
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("1"))],
    )
    #: Hourly contracts. The weekly cap is what stops a client being surprised
    #: by an unbounded invoice (Section 10.5).
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    weekly_hour_limit = models.PositiveSmallIntegerField(null=True, blank=True)

    #: An immutable record of what was agreed, captured at acceptance.
    terms = models.JSONField(default=dict, blank=True)

    accepted_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    #: When an unanswered delivery auto-completes.
    review_deadline = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client", "status"]),
            models.Index(fields=["freelancer", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.get_status_display()})"

    def involves(self, user) -> bool:
        return user.pk in (self.client_id, self.freelancer_id)

    def counterparty(self, user):
        return self.freelancer if user.pk == self.client_id else self.client

    @property
    def is_live(self) -> bool:
        return self.status in (self.Status.ACTIVE, self.Status.DELIVERED, self.Status.PAUSED)

    @property
    def funded_amount(self) -> Decimal:
        """What is currently secured in escrow across all milestones."""
        held = [
            Milestone.Status.FUNDED,
            Milestone.Status.IN_PROGRESS,
            Milestone.Status.DELIVERED,
        ]
        return self.milestones.filter(status__in=held).aggregate(total=models.Sum("amount"))[
            "total"
        ] or Decimal("0")

    @property
    def released_amount(self) -> Decimal:
        return self.milestones.filter(status=Milestone.Status.RELEASED).aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0")

    @property
    def logged_amount(self) -> Decimal:
        """Value of approved time on an hourly contract."""
        if self.contract_type != ContractType.HOURLY or not self.hourly_rate:
            return Decimal("0")
        minutes = (
            self.time_entries.filter(is_disputed=False).aggregate(total=models.Sum("minutes"))[
                "total"
            ]
            or 0
        )
        return (Decimal(minutes) / Decimal(60) * self.hourly_rate).quantize(Decimal("0.01"))

    def snapshot_terms(self) -> dict:
        """Freeze what was agreed, so later edits upstream cannot rewrite it."""
        return {
            "title": self.title,
            "contract_type": self.contract_type,
            "total_amount": str(self.total_amount) if self.total_amount else None,
            "hourly_rate": str(self.hourly_rate) if self.hourly_rate else None,
            "weekly_hour_limit": self.weekly_hour_limit,
            "project_id": self.project_id,
            "project_description": self.project.description if self.project else "",
            "milestones": [
                {"title": m.title, "amount": str(m.amount), "due_date": str(m.due_date or "")}
                for m in self.milestones.all()
            ],
            "frozen_at": timezone.now().isoformat(),
        }

    @classmethod
    def create_from_proposal(
        cls,
        proposal,
        *,
        client,
        milestone_specs: list[dict] | None = None,
        weekly_hour_limit: int | None = None,
        contract_type: str | None = None,
    ) -> Contract:
        """Open a contract from a proposal — the machinery `award` and a
        trial's `convert` both need, factored out because they need the
        exact same one, not two versions that can quietly drift apart.

        Validates milestone amounts *before* creating anything. The original
        single-caller version created the `Contract` row first and validated
        after — which meant a mismatched milestone total left a real,
        permanent `Contract` behind despite the request being rejected as a
        400, because `proposal.contract` is a `OneToOneField`: that zombie
        row occupied the slot forever and made the proposal un-awardable on
        every subsequent attempt, correct amounts or not. Does not touch the
        proposal or project status — an award and a trial conversion do that
        at different points, so it stays the caller's decision.
        """
        from django.core.exceptions import ValidationError

        from marketplace.models import ProjectType

        project = proposal.project
        hourly = project.project_type == ProjectType.HOURLY
        resolved_type = contract_type or (ContractType.HOURLY if hourly else ContractType.FIXED)

        specs = None
        if not hourly:
            specs = milestone_specs or [
                {"title": "Full delivery", "amount": proposal.bid_amount, "order": 0}
            ]
            if milestone_specs:
                resolved_type = ContractType.MILESTONE
            total = sum(Decimal(str(spec["amount"])) for spec in specs)
            if proposal.bid_amount and abs(total - proposal.bid_amount) > Decimal("0.01"):
                raise ValidationError("Milestone amounts must add up to the agreed price.")

        contract = cls.objects.create(
            project=project,
            proposal=proposal,
            client=client,
            freelancer=proposal.freelancer,
            title=project.title,
            contract_type=resolved_type,
            total_amount=None if hourly else proposal.bid_amount,
            hourly_rate=proposal.hourly_rate if hourly else None,
            weekly_hour_limit=weekly_hour_limit or project.weekly_hours,
            # The contract lives on the same surface as the brief it came
            # from, so a campus contract never becomes globally visible.
            visibility=project.visibility,
            university=project.university,
        )
        if specs:
            Milestone.objects.bulk_create(
                [
                    Milestone(
                        contract=contract,
                        order=spec.get("order", index),
                        title=spec["title"],
                        description=spec.get("description", ""),
                        amount=Decimal(str(spec["amount"])),
                        due_date=spec.get("due_date"),
                    )
                    for index, spec in enumerate(specs)
                ]
            )
        return contract

    def accept(self) -> None:
        self.status = self.Status.ACTIVE
        self.accepted_at = timezone.now()
        self.started_at = self.accepted_at
        self.terms = self.snapshot_terms()
        self.save(update_fields=["status", "accepted_at", "started_at", "terms", "updated_at"])

    def mark_delivered(self) -> None:
        from datetime import timedelta

        self.status = self.Status.DELIVERED
        self.delivered_at = timezone.now()
        self.review_deadline = self.delivered_at + timedelta(days=self.REVIEW_WINDOW_DAYS)
        self.save(update_fields=["status", "delivered_at", "review_deadline", "updated_at"])

    def complete(self) -> None:
        self.status = self.Status.COMPLETED
        self.ended_at = timezone.now()
        self.save(update_fields=["status", "ended_at", "updated_at"])

        # A completed contract is the single event that moves a reputation, so
        # it recomputes immediately rather than waiting for the nightly sweep —
        # a seller who just finished their third job should see the level they
        # earned, not tomorrow's version of it.
        #
        # Wrapped because reputation is derived data: failing to recompute it
        # must never undo the completion that triggered it.
        try:
            from accounts.reputation import recompute_for

            recompute_for(self.freelancer)
        except Exception:
            import logging

            logging.getLogger(__name__).exception("reputation_refresh_failed contract=%s", self.pk)


class Milestone(TimestampedModel):
    """One funded, delivered, and released stage of a contract.

    A single-payment fixed contract is modelled as one milestone rather than as
    a special case, so funding and release have exactly one implementation.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting funding"
        FUNDED = "funded", "Funded"
        IN_PROGRESS = "in_progress", "In progress"
        DELIVERED = "delivered", "Delivered"
        APPROVED = "approved", "Approved"
        RELEASED = "released", "Released"
        CANCELLED = "cancelled", "Cancelled"

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="milestones")
    order = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("1"))]
    )
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)

    deliverables = models.ManyToManyField("core.StoredFile", blank=True, related_name="+")
    delivery_note = models.TextField(blank=True)

    funded_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"{self.title} — {self.get_status_display()}"

    @property
    def is_funded(self) -> bool:
        return self.status not in (self.Status.PENDING, self.Status.CANCELLED)

    def fund(self) -> None:
        """Money is secured in escrow: called when Swich confirms the
        payment (`payments.checkout`, D55), or by an admin who recorded a
        payment received another way."""
        self.status = self.Status.FUNDED
        self.funded_at = timezone.now()
        self.save(update_fields=["status", "funded_at", "updated_at"])

    def deliver(self, note: str = "") -> None:
        self.status = self.Status.DELIVERED
        self.delivery_note = note or self.delivery_note
        self.delivered_at = timezone.now()
        self.save(update_fields=["status", "delivery_note", "delivered_at", "updated_at"])

    def release(self) -> None:
        self.status = self.Status.RELEASED
        self.released_at = timezone.now()
        self.save(update_fields=["status", "released_at", "updated_at"])


class Trial(TimestampedModel):
    """A small, paid task offered before a client commits to the full
    project — Phase 12. "Can I trust this freelancer?" is the question
    reviews only partly answer; a trial answers it directly.

    Deliberately not new infrastructure. Once accepted, a trial opens its own
    tiny `Contract` — one milestone, the trial fee — and from there it is
    funded, delivered, and released through the exact same endpoints every
    other contract on this platform already uses. The only genuinely new
    surface is proposing the trial and converting it afterwards.
    """

    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CONVERTED = "converted", "Converted to full contract"

    proposal = models.OneToOneField(
        "marketplace.Proposal", on_delete=models.CASCADE, related_name="trial"
    )
    #: The trial's own small contract — set once the freelancer accepts.
    #: Deliberately does NOT carry `proposal`: `Contract.proposal` is a
    #: OneToOneField, and the *real* contract (once this trial converts)
    #: is the one meant to occupy that slot. A trial contract that claimed
    #: it first would make its own proposal permanently un-awardable.
    contract = models.OneToOneField(
        Contract, null=True, blank=True, on_delete=models.SET_NULL, related_name="trial_source"
    )
    #: The real contract this trial converted into, once the client
    #: continues with this freelancer. Set once, by `convert()`.
    converted_contract = models.OneToOneField(
        Contract,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="converted_from_trial",
    )

    brief = models.TextField()
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("1"))]
    )
    duration_days = models.PositiveSmallIntegerField(default=3)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PROPOSED)
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Trial on proposal {self.proposal_id} ({self.status})"

    @property
    def project(self):
        return self.proposal.project

    @property
    def freelancer(self):
        return self.proposal.freelancer

    def accept(self) -> Contract:
        """The freelancer agrees. Opens the trial's own contract — funding,
        delivery, and approval all happen through `ContractViewSet` from
        here on; nothing about a trial contract's lifecycle is special."""
        from datetime import timedelta

        from django.core.exceptions import ValidationError

        if self.status != self.Status.PROPOSED:
            raise ValidationError("This trial is no longer awaiting a response.")

        project = self.project
        contract = Contract.objects.create(
            project=project,
            client=project.client,
            freelancer=self.freelancer,
            title=f"Trial: {project.title}",
            contract_type=ContractType.FIXED,
            total_amount=self.amount,
            visibility=project.visibility,
            university=project.university,
        )
        Milestone.objects.create(
            contract=contract,
            title="Trial task",
            description=self.brief,
            amount=self.amount,
            due_date=timezone.now().date() + timedelta(days=self.duration_days),
        )
        contract.accept()

        self.contract = contract
        self.status = self.Status.ACCEPTED
        self.responded_at = timezone.now()
        self.save(update_fields=["contract", "status", "responded_at", "updated_at"])
        return contract

    def decline(self) -> None:
        from django.core.exceptions import ValidationError

        if self.status != self.Status.PROPOSED:
            raise ValidationError("This trial is no longer awaiting a response.")
        self.status = self.Status.DECLINED
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at", "updated_at"])

    def convert(self, *, client) -> Contract:
        """'Continue with this freelancer' — open the real contract this
        trial was a preview of.

        **What this does not do: credit the trial fee toward the new
        contract.** That is a ledger operation — crediting one payment
        against another — and there is no ledger until Phase 3 ships (D31).
        The amount stays on this row so the client sees it plainly on the
        new contract's funding screen instead of the platform silently
        forgetting a $50 payment it already collected.
        """
        from django.core.exceptions import ValidationError

        from marketplace.models import Project, Proposal

        if self.status != self.Status.ACCEPTED:
            raise ValidationError("Only an accepted trial can convert.")
        if self.contract is None or self.contract.status != Contract.Status.COMPLETED:
            raise ValidationError("The trial task must be delivered and approved first.")
        if hasattr(self.proposal, "contract") and self.proposal.contract is not None:
            raise ValidationError("This proposal has already been awarded.")

        new_contract = Contract.create_from_proposal(self.proposal, client=client)

        self.proposal.status = Proposal.Status.ACCEPTED
        self.proposal.save(update_fields=["status", "updated_at"])
        self.proposal.project.status = Project.Status.AWARDED
        self.proposal.project.save(update_fields=["status", "updated_at"])

        self.converted_contract = new_contract
        self.status = self.Status.CONVERTED
        self.save(update_fields=["converted_contract", "status", "updated_at"])
        return new_contract


class TimeEntry(TimestampedModel):
    """A block of time logged against an hourly contract.

    Section 10.5 draws a hard line here: time captured by the tracker carries
    activity data and is protected in a dispute; manually added time is not.
    That asymmetry is what makes hourly protection credible, so ``source`` is
    never inferred — it is set by whichever endpoint created the entry.
    """

    class Source(models.TextChoices):
        TRACKER = "tracker", "Tracked"
        MANUAL = "manual", "Added manually"

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="time_entries")
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="time_entries"
    )
    worked_on = models.DateField()
    minutes = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    memo = models.CharField(max_length=280)
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.MANUAL)
    #: 0–100. Only meaningful for tracked time.
    activity_level = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(100)]
    )

    is_disputed = models.BooleanField(default=False)
    dispute_note = models.CharField(max_length=280, blank=True)

    class Meta:
        ordering = ["-worked_on", "-created_at"]
        indexes = [models.Index(fields=["contract", "worked_on"])]
        verbose_name_plural = "time entries"

    def __str__(self) -> str:
        return f"{self.minutes} min on {self.worked_on}"

    @property
    def hours(self) -> float:
        return round(self.minutes / 60, 2)

    @property
    def is_protected(self) -> bool:
        """Whether this time would survive a dispute."""
        return self.source == self.Source.TRACKER


class ContractEvent(TimestampedModel):
    """The unified activity timeline for a contract.

    Messages, deliveries, funding, and (from Phase 9) integration activity all
    land here in one chronological stream, which is what a dispute officer
    needs to read a working relationship end to end.
    """

    class Kind(models.TextChoices):
        MESSAGE = "message", "Message"
        STATUS = "status", "Status change"
        FUNDED = "funded", "Milestone funded"
        DELIVERED = "delivered", "Work delivered"
        RELEASED = "released", "Payment released"
        TIME = "time", "Time logged"
        REVIEW = "review", "Review left"

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contract_events",
    )
    kind = models.CharField(max_length=12, choices=Kind.choices, db_index=True)
    body = models.TextField(blank=True)
    attachments = models.ManyToManyField("core.StoredFile", blank=True, related_name="+")
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.kind} on contract {self.contract_id}"

    @classmethod
    def log(cls, contract, kind: str, actor=None, body: str = "", **payload) -> ContractEvent:
        return cls.objects.create(
            contract=contract, kind=kind, actor=actor, body=body, payload=payload
        )


class Review(TimestampedModel):
    """A two-way, double-blind review of a completed contract.

    Neither side's review is published until both have been submitted or the
    window closes (Section 14.1). That single rule removes both retaliation and
    mutual inflation, which is why publication is a method here rather than a
    flag anyone can set.
    """

    class Role(models.TextChoices):
        CLIENT = "client", "Client reviewing freelancer"
        FREELANCER = "freelancer", "Freelancer reviewing client"

    class Integrity(models.TextChoices):
        """What the fraud checks concluded about this review.

        Three states rather than a boolean, because "we have not looked yet"
        and "we looked and it is fine" must not be the same value — otherwise
        a backlog in the checker silently reads as a clean bill of health.
        """

        UNCHECKED = "unchecked", "Not yet assessed"
        CLEAN = "clean", "Assessed, no concerns"
        FLAGGED = "flagged", "Flagged for review"
        #: Excluded from public averages and from the Job Success Score, but
        #: never deleted — a removed review destroys the evidence the decision
        #: was based on.
        SUPPRESSED = "suppressed", "Excluded from scores"

    WINDOW_DAYS = 14

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="reviews")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_written"
    )
    subject = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_received"
    )
    role = models.CharField(max_length=10, choices=Role.choices)

    overall = models.PositiveSmallIntegerField(**STARS)
    communication = models.PositiveSmallIntegerField(**STARS)
    #: Client-only sub-ratings.
    quality = models.PositiveSmallIntegerField(null=True, blank=True, **STARS)
    deadline = models.PositiveSmallIntegerField(null=True, blank=True, **STARS)
    value = models.PositiveSmallIntegerField(null=True, blank=True, **STARS)
    #: Freelancer-only sub-ratings.
    clarity = models.PositiveSmallIntegerField(null=True, blank=True, **STARS)
    payment_promptness = models.PositiveSmallIntegerField(null=True, blank=True, **STARS)

    comment = models.TextField(blank=True)
    #: Never published. Feeds internal quality signals and moderation only.
    private_feedback = models.TextField(blank=True)

    published_at = models.DateTimeField(null=True, blank=True)
    #: The reviewed party may post exactly one public response.
    response = models.TextField(blank=True)

    integrity_status = models.CharField(
        max_length=12,
        choices=Integrity.choices,
        default=Integrity.UNCHECKED,
        db_index=True,
    )
    #: Which checks fired, e.g. ["reciprocal_pair", "same_network"]. Kept as a
    #: list rather than a single reason because reviews are rarely suspicious
    #: for exactly one reason, and the combination is what a moderator judges.
    integrity_signals = models.JSONField(default=list, blank=True)
    integrity_checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "author"], name="one_review_per_author_per_contract"
            )
        ]

    def __str__(self) -> str:
        return f"{self.overall}★ for {self.subject_id}"

    @property
    def is_published(self) -> bool:
        return self.published_at is not None

    @classmethod
    def publish_pair_if_ready(cls, contract) -> int:
        """Publish both reviews once both exist. Returns how many were published.

        Called after each submission. Reviews left unpublished here are picked
        up when the window expires, so a party who never reviews cannot keep
        the other's review hidden forever.
        """
        reviews = list(cls.objects.filter(contract=contract, published_at__isnull=True))
        if len(reviews) < 2:
            return 0
        now = timezone.now()
        return cls.objects.filter(pk__in=[r.pk for r in reviews]).update(published_at=now)
