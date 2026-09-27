"""
The professional layer: subscriptions, CRM, agencies, shared workspaces, and
services sold as recurring retainers.

Everything here is for people already earning on the platform. The roadmap is
explicit that this phase is only worth having once there is a base of
freelancers with real income, and that shapes what is built: nothing here is on
the path of a new user, and no free-tier behaviour changes because these models
exist.

**Billing is deferred, and the seam is deliberate.** Phase 3 has not landed, so
no subscription here charges anything — `activate()` records that a plan is in
force and `entitlements.for_user` reads it. That is the same substitution
decision D12 took for milestone funding: the state machine is the real one, and
the gateway replaces one method rather than a design. What is *not* faked is
entitlement enforcement — a Pro quota is genuinely a Pro quota the moment a
subscription is active, because otherwise the whole layer is untested scaffolding
on the day money starts flowing.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from core.models import ScopedModel, TimestampedModel

# --- Plans and subscriptions ------------------------------------------------


class Plan(TimestampedModel):
    """A subscription tier.

    A row rather than a constant so pricing and limits can move without a
    deploy — the numbers in a pricing table are a commercial decision that will
    be revised more often than the code around them, and every revision behind
    a release is a revision that does not happen.

    Entitlements are explicit columns rather than a JSON blob. A blob reads
    nicely until something has to *query* on it, and "which plans include team
    seats" is a question the billing page asks on every render.
    """

    class Tier(models.TextChoices):
        FREE = "free", "Free"
        PRO = "pro", "Pro"
        ELITE = "elite", "Elite"

    #: Sentinel for "no ceiling". `None` would work but forces every caller to
    #: branch on null before comparing, and one caller will forget.
    UNLIMITED = -1

    tier = models.CharField(max_length=10, choices=Tier.choices, unique=True)
    name = models.CharField(max_length=60)
    tagline = models.CharField(max_length=180, blank=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    #: Charged as one payment covering twelve months. Stored rather than
    #: derived so a discount can be changed without a migration.
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    is_public = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    # --- Entitlements ---
    proposal_quota = models.IntegerField(default=30)
    team_seats = models.IntegerField(default=0)
    crm_contact_limit = models.IntegerField(default=0)
    #: A modest, disclosed ranking lift. Deliberately not a search bypass — see
    #: the promotion reasoning in `discovery.models`.
    search_boost = models.BooleanField(default=False)
    advanced_analytics = models.BooleanField(default=False)
    can_sell_retainers = models.BooleanField(default=False)
    can_create_agency = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    #: Marketing copy. The bullets on the pricing card, in order.
    features = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["order", "monthly_price"]

    def __str__(self) -> str:
        return self.name

    @property
    def is_paid(self) -> bool:
        return self.monthly_price > 0

    @classmethod
    def free(cls) -> Plan:
        """The tier everyone has without doing anything.

        Created on demand so a fresh database, a test, and a restored backup
        all behave the same — a missing free plan would otherwise mean every
        entitlement lookup on a new install raises.
        """
        plan, _ = cls.objects.get_or_create(
            tier=cls.Tier.FREE,
            defaults={
                "name": "Free",
                "tagline": "Everything you need to hire or get hired.",
                "proposal_quota": 30,
                "crm_contact_limit": 25,
                "order": 0,
            },
        )
        return plan


class Subscription(TimestampedModel):
    """One user's membership of a paid tier.

    Only one may be live per user at a time, enforced by a partial constraint
    rather than by application code — two overlapping subscriptions is the kind
    of state that silently doubles someone's entitlements and is discovered
    months later in a billing reconciliation.
    """

    class Status(models.TextChoices):
        TRIALING = "trialing", "In trial"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Payment overdue"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    class Interval(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    LIVE_STATUSES = ("trialing", "active", "past_due")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    interval = models.CharField(max_length=10, choices=Interval.choices, default=Interval.MONTHLY)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )

    started_at = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField()
    #: Cancelling does not revoke immediately — the user paid through the end
    #: of the period and keeps what they paid for.
    cancel_at_period_end = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status__in=["trialing", "active", "past_due"]),
                name="one_live_subscription_per_user",
            )
        ]
        indexes = [models.Index(fields=["status", "current_period_end"])]

    def __str__(self) -> str:
        return f"{self.user_id} on {self.plan_id} ({self.status})"

    @property
    def is_live(self) -> bool:
        return self.status in self.LIVE_STATUSES and self.current_period_end > timezone.now()

    def cancel(self, *, immediately: bool = False) -> None:
        self.cancelled_at = timezone.now()
        if immediately:
            self.status = self.Status.CANCELLED
            self.current_period_end = timezone.now()
        else:
            self.cancel_at_period_end = True
        self.save(
            update_fields=[
                "status",
                "cancel_at_period_end",
                "cancelled_at",
                "current_period_end",
                "updated_at",
            ]
        )

    def renew(self) -> None:
        """Extend by one interval.

        Unused today — nothing calls this. A renewal needs the member to
        pay again through Swich, as `professional.views.subscribe` does for
        a new plan (D55), driven by whatever reminds a user their period is
        ending; that flow does not exist yet. The period arithmetic and
        the state transition are already the real ones, ready for it.
        """
        span = timedelta(days=365 if self.interval == self.Interval.YEARLY else 30)
        base = max(self.current_period_end, timezone.now())
        self.current_period_end = base + span
        self.status = self.Status.ACTIVE
        self.save(update_fields=["current_period_end", "status", "updated_at"])


# --- CRM --------------------------------------------------------------------


class Contact(TimestampedModel):
    """Somebody a freelancer is doing business with.

    Not necessarily a platform user. That is the point of building a CRM in
    here rather than pointing people at a spreadsheet: a working freelancer's
    pipeline spans clients they met on the platform and clients they did not,
    and a tool that only knows about half of it does not get used.
    """

    class Source(models.TextChoices):
        PLATFORM = "platform", "SkilRize"
        REFERRAL = "referral", "Referral"
        DIRECT = "direct", "Direct outreach"
        REPEAT = "repeat", "Repeat client"
        OTHER = "other", "Other"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="crm_contacts"
    )
    #: Set when the contact is also an account here, which lets a deal be
    #: linked to a real contract later.
    linked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="crm_appearances",
    )

    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    company = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.PLATFORM)
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False)

    #: Denormalised for the pipeline board, which sorts by it on every render.
    last_interaction_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-last_interaction_at", "name"]
        indexes = [models.Index(fields=["owner", "is_archived"])]

    def __str__(self) -> str:
        return self.name

    def touch(self) -> None:
        self.last_interaction_at = timezone.now()
        self.save(update_fields=["last_interaction_at", "updated_at"])


class Deal(TimestampedModel):
    """A piece of work being pursued, at some stage of the pipeline."""

    class Stage(models.TextChoices):
        LEAD = "lead", "Lead"
        QUALIFIED = "qualified", "Qualified"
        PROPOSED = "proposed", "Proposal sent"
        NEGOTIATING = "negotiating", "Negotiating"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    OPEN_STAGES = ("lead", "qualified", "proposed", "negotiating")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deals"
    )
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="deals")
    title = models.CharField(max_length=200)
    value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    stage = models.CharField(
        max_length=12, choices=Stage.choices, default=Stage.LEAD, db_index=True
    )
    expected_close = models.DateField(null=True, blank=True)
    #: Set when a deal becomes real work on the platform. This is what makes the
    #: CRM worth having inside the marketplace rather than beside it — the
    #: pipeline closes into an actual contract instead of being marked "won" by
    #: hand and then forgotten.
    contract = models.ForeignKey(
        "contracts.Contract", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    lost_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "stage"])]

    def __str__(self) -> str:
        return self.title

    @property
    def is_open(self) -> bool:
        return self.stage in self.OPEN_STAGES

    def move_to(self, stage: str, *, reason: str = "") -> None:
        self.stage = stage
        if stage in (self.Stage.WON, self.Stage.LOST):
            self.closed_at = timezone.now()
            self.lost_reason = reason if stage == self.Stage.LOST else ""
        else:
            self.closed_at = None
        self.save(update_fields=["stage", "closed_at", "lost_reason", "updated_at"])
        self.contact.touch()


class Interaction(TimestampedModel):
    """A logged touchpoint — a call, an email, a meeting, a note."""

    class Kind(models.TextChoices):
        NOTE = "note", "Note"
        CALL = "call", "Call"
        EMAIL = "email", "Email"
        MEETING = "meeting", "Meeting"
        PROPOSAL = "proposal", "Proposal sent"

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="interactions")
    deal = models.ForeignKey(
        Deal, null=True, blank=True, on_delete=models.SET_NULL, related_name="interactions"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="crm_interactions"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.NOTE)
    body = models.TextField()
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-occurred_at"]

    def __str__(self) -> str:
        return f"{self.kind} with {self.contact_id}"


class Task(TimestampedModel):
    """A follow-up somebody has to actually do."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="crm_tasks"
    )
    contact = models.ForeignKey(
        Contact, null=True, blank=True, on_delete=models.CASCADE, related_name="tasks"
    )
    deal = models.ForeignKey(
        Deal, null=True, blank=True, on_delete=models.CASCADE, related_name="tasks"
    )
    title = models.CharField(max_length=200)
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["completed_at", "due_at"]
        indexes = [models.Index(fields=["owner", "completed_at", "due_at"])]

    def __str__(self) -> str:
        return self.title

    @property
    def is_overdue(self) -> bool:
        return bool(self.due_at and not self.completed_at and self.due_at < timezone.now())


# --- Agencies and shared workspaces -----------------------------------------


class Agency(TimestampedModel):
    """A team selling together under one name.

    An agency does not replace its members' accounts. Everyone keeps their own
    profile, reputation, and earnings history — an agency is a way to sell
    jointly, not a way to pool identity. A freelancer who leaves takes their
    reviews with them, because the work was theirs.
    """

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    tagline = models.CharField(max_length=180, blank=True)
    description = models.TextField(blank=True)
    logo = models.ForeignKey(
        "core.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agencies_owned"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "agencies"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:120] or "agency"
            candidate, suffix = base, 2
            while Agency.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{suffix}"
                suffix += 1
            self.slug = candidate
        return super().save(*args, **kwargs)

    @property
    def seats_used(self) -> int:
        return self.members.filter(status=AgencyMember.Status.ACTIVE).count()

    def role_of(self, user) -> str | None:
        if not user or not user.is_authenticated:
            return None
        member = self.members.filter(user=user, status=AgencyMember.Status.ACTIVE).first()
        return member.role if member else None

    def can_manage(self, user) -> bool:
        return self.role_of(user) in (AgencyMember.Role.OWNER, AgencyMember.Role.ADMIN)


class AgencyMember(TimestampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        REMOVED = "removed", "Removed"

    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agency_memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.INVITED)
    #: What this member takes of work routed through the agency, as a
    #: percentage. Stored per member because agencies split differently per
    #: person and a single agency-wide rate would be a fiction.
    revenue_share = models.PositiveSmallIntegerField(default=0)
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["agency", "user"], name="one_agency_membership_per_user"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.agency_id} ({self.role})"

    def accept(self) -> None:
        self.status = self.Status.ACTIVE
        self.joined_at = timezone.now()
        self.save(update_fields=["status", "joined_at", "updated_at"])


class Workspace(TimestampedModel):
    """A shared space for one client engagement.

    Deliberately *not* scoped by tenancy. A workspace is private to its members
    by membership, which is a stronger guarantee than a surface filter and does
    not need one — there is no listing here to leak into a marketplace.
    """

    agency = models.ForeignKey(
        Agency, null=True, blank=True, on_delete=models.CASCADE, related_name="workspaces"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workspaces_created"
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    client_contact = models.ForeignKey(
        Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="workspaces"
    )
    contracts = models.ManyToManyField("contracts.Contract", blank=True, related_name="workspaces")
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    def has_member(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if self.created_by_id == user.pk:
            return True
        return self.members.filter(user=user).exists()


class WorkspaceMember(TimestampedModel):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workspace_memberships"
    )
    #: A client invited into the workspace sees the shared board but not the
    #: agency's internal notes. Two audiences, one space, different views.
    is_client = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "user"], name="one_workspace_membership_per_user"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in workspace {self.workspace_id}"


# --- Sellable subscription services ------------------------------------------


class RetainerPlan(ScopedModel):
    """A service sold monthly rather than per delivery.

    Scoped like any other listing, because that is what it is: a campus
    retainer must not appear in the global catalogue. It inherits `ScopedModel`
    so `core.test_tenancy` covers it automatically.
    """

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="retainer_plans"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    monthly_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("1"))]
    )
    #: What the buyer gets each month. A retainer with no stated deliverables is
    #: an argument waiting to happen.
    deliverables = models.JSONField(default=list, blank=True)
    #: 0 means no cap.
    max_subscribers = models.PositiveIntegerField(default=0)
    minimum_months = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta(ScopedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        if not self.deliverables:
            raise ValidationError({"deliverables": "State what the buyer receives each month."})

    @property
    def active_subscriber_count(self) -> int:
        return self.subscriptions.filter(status__in=RetainerSubscription.LIVE_STATUSES).count()

    @property
    def is_full(self) -> bool:
        return bool(self.max_subscribers) and self.active_subscriber_count >= self.max_subscribers


class RetainerSubscription(TimestampedModel):
    """One buyer's ongoing engagement of a retainer."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Payment overdue"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Finished"

    LIVE_STATUSES = ("active", "past_due")

    plan = models.ForeignKey(RetainerPlan, on_delete=models.CASCADE, related_name="subscriptions")
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="retainer_subscriptions"
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    started_at = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField()
    cancel_at_period_end = models.BooleanField(default=False)
    months_billed = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "buyer"],
                condition=models.Q(status__in=["active", "past_due"]),
                name="one_live_retainer_per_buyer_per_plan",
            )
        ]

    def __str__(self) -> str:
        return f"{self.buyer_id} on retainer {self.plan_id}"

    @property
    def is_live(self) -> bool:
        return self.status in self.LIVE_STATUSES

    @property
    def can_cancel_now(self) -> bool:
        """Whether the minimum commitment has been served.

        A minimum term the buyer agreed to is enforceable; enforcing it by
        refusing to *accept* a cancellation is not. Cancelling always works —
        this only decides whether it takes effect now or at the end of the
        committed period.
        """
        return self.months_billed >= self.plan.minimum_months

    def cancel(self) -> None:
        if self.can_cancel_now:
            self.status = self.Status.CANCELLED
        else:
            self.cancel_at_period_end = True
        self.save(update_fields=["status", "cancel_at_period_end", "updated_at"])
