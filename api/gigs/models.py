"""
Track B — gigs.

A freelancer publishes a productised service at a fixed price and a buyer
purchases it directly: no bidding, no negotiation, no approval step. Where
Track A is a hiring process, this is a transaction.

Two decisions shape everything here:

**An order is backed by a contract.** Rather than growing a second escrow, a
second message thread, and a second review system, an order creates a
``contracts.Contract`` with a single milestone and drives it. That is what makes
"one wallet, one reputation" true rather than aspirational — a five-star review
from a purchased gig and one from a won proposal are the same row in the same
table.

**The requirements form gates the clock.** Section 11.3 is emphatic: the
delivery countdown does not start until the buyer has submitted what the seller
needs. Without that, a buyer who pays and disappears runs the seller's clock
down for them.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from core.models import ScopedModel, TimestampedModel


class Gig(ScopedModel):
    """A productised service listing."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        DENIED = "denied", "Denied"

    #: Section 11.1 — the constrained title format is what keeps a catalogue
    #: scannable and comparable.
    TITLE_PREFIX = "I will "
    MAX_TAGS = 5

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gigs"
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.ForeignKey(
        "marketplace.Category",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="gigs",
    )
    skills = models.ManyToManyField("marketplace.Skill", blank=True, related_name="gigs")
    #: Capped at MAX_TAGS to prevent tag spam.
    tags = models.JSONField(default=list, blank=True)

    description = models.TextField()
    #: [{"question": "...", "answer": "..."}]
    faq = models.JSONField(default=list, blank=True)
    #: The structured questions a buyer must answer before the clock starts:
    #: [{"key": "brand_name", "label": "...", "type": "text", "required": true}]
    requirements = models.JSONField(default=list, blank=True)

    gallery = models.ManyToManyField("core.StoredFile", blank=True, related_name="+")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)

    # Discovery counters, written by the platform.
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    orders_count = models.PositiveIntegerField(default=0)
    rating_average = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    rating_count = models.PositiveIntegerField(default=0)

    published_at = models.DateTimeField(null=True, blank=True)

    #: Maintained by `gigs.indexing.reindex`, called on save and by the
    #: backfill task. Stored rather than computed per query: building the
    #: vector at query time means a sequential scan over every row, which is
    #: exactly what the GIN index below exists to avoid.
    search_vector = SearchVectorField(null=True, editable=False)
    #: Set by an active `discovery.Promotion`. Denormalised because ranking
    #: reads it on every row of every search.
    is_promoted = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"]),
            models.Index(fields=["visibility", "university", "status"]),
            GinIndex(fields=["search_vector"], name="gig_search_vector_gin"),
            # Trigram index for the misspelling fallback. Without it every
            # fuzzy search is a full scan.
            GinIndex(
                name="gig_title_trigram",
                fields=["title"],
                opclasses=["gin_trgm_ops"],
            ),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or "gig"
            self.slug = base
            # Slugs are public URLs, so collisions get a suffix rather than an
            # error the seller cannot act on.
            suffix = 1
            while Gig.objects.unscoped().filter(slug=self.slug).exclude(pk=self.pk).exists():
                suffix += 1
                self.slug = f"{base[:210]}-{suffix}"

        result = super().save(*args, **kwargs)

        # Reindex after the row exists, because the vector is built by Postgres
        # from the stored row. Skipped when the caller passed `update_fields`
        # that cannot affect the text — the hot path here is a counter bump on
        # every impression, and rebuilding a vector for that would be absurd.
        indexed_fields = {"title", "description", "tags", "category"}
        touched = kwargs.get("update_fields")
        if touched is None or indexed_fields & set(touched):
            from core.indexing import reindex_gig

            reindex_gig(self.pk)
        return result

    @property
    def is_orderable(self) -> bool:
        return self.status == self.Status.ACTIVE and self.packages.filter(is_active=True).exists()

    @property
    def starting_price(self) -> Decimal | None:
        cheapest = self.packages.filter(is_active=True).order_by("price").first()
        return cheapest.price if cheapest else None

    @property
    def conversion_rate(self) -> float:
        """Orders per click. Meaningless below a handful of clicks, so the
        caller decides whether to show it."""
        return round(self.orders_count / self.clicks, 4) if self.clicks else 0.0

    def accepts_order_from(self, user) -> tuple[bool, str]:
        if not self.is_orderable:
            return False, "This gig is not available to order right now."
        if self.seller_id == user.pk:
            return False, "You cannot order your own gig."
        if not user.can_transact:
            return False, "Complete your profile before buying."
        return True, ""

    def publish(self) -> None:
        self.status = self.Status.ACTIVE
        self.published_at = self.published_at or timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])


class Package(TimestampedModel):
    """One of the three tiers a buyer chooses between.

    Tiered pricing reliably raises average order value, but a service that does
    not genuinely tier may publish only Basic rather than invent differences
    (Section 11.2, single-package mode).
    """

    class Tier(models.TextChoices):
        BASIC = "basic", "Basic"
        STANDARD = "standard", "Standard"
        PREMIUM = "premium", "Premium"

    #: A revision entitlement this high is effectively unlimited and is
    #: displayed as such.
    UNLIMITED_REVISIONS = 99

    gig = models.ForeignKey(Gig, on_delete=models.CASCADE, related_name="packages")
    tier = models.CharField(max_length=10, choices=Tier.choices)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=300, blank=True)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("1"))]
    )
    delivery_days = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    revisions = models.PositiveSmallIntegerField(default=1)
    #: Plain feature bullets shown as a checklist.
    features = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price"]
        constraints = [
            models.UniqueConstraint(fields=["gig", "tier"], name="one_package_per_tier_per_gig")
        ]

    def __str__(self) -> str:
        return f"{self.gig_id} · {self.tier} · {self.price}"

    @property
    def has_unlimited_revisions(self) -> bool:
        return self.revisions >= self.UNLIMITED_REVISIONS


class GigExtra(TimestampedModel):
    """An optional paid add-on: extra revisions, source files, faster delivery."""

    gig = models.ForeignKey(Gig, on_delete=models.CASCADE, related_name="extras")
    title = models.CharField(max_length=120)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("1"))]
    )
    #: Days this add-on adds to the delivery time. Fast delivery is modelled as
    #: a negative value.
    extra_days = models.SmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price"]

    def __str__(self) -> str:
        return self.title


class Order(TimestampedModel):
    """A purchase of one package, plus any extras."""

    class Status(models.TextChoices):
        PENDING_REQUIREMENTS = "pending_requirements", "Waiting for requirements"
        ACTIVE = "active", "In progress"
        DELIVERED = "delivered", "Delivered"
        REVISION = "revision", "Revision requested"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    #: Section 11.3 — inaction auto-completes the order rather than leaving the
    #: seller's money in limbo indefinitely.
    ACCEPTANCE_WINDOW_DAYS = 3

    gig = models.ForeignKey(Gig, on_delete=models.PROTECT, related_name="orders")
    package = models.ForeignKey(Package, on_delete=models.PROTECT, related_name="orders")
    extras = models.ManyToManyField(GigExtra, blank=True, related_name="orders")
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gig_orders"
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gig_sales"
    )

    #: Escrow, messaging, and reviews all live on the contract. An order is the
    #: gig-shaped face of it.
    contract = models.OneToOneField(
        "contracts.Contract",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="gig_order",
    )

    # Snapshots taken at purchase — the seller editing the gig afterwards must
    # not change what this buyer paid for.
    price = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_days = models.PositiveSmallIntegerField()
    revisions_allowed = models.PositiveSmallIntegerField()
    package_snapshot = models.JSONField(default=dict, blank=True)

    #: {"brand_name": "...", ...} keyed by the gig's requirement keys.
    requirements_answers = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.PENDING_REQUIREMENTS
    )
    revisions_used = models.PositiveSmallIntegerField(default=0)

    #: Set when requirements land, not when payment lands.
    started_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    accept_by = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["buyer", "status"]),
            models.Index(fields=["seller", "status"]),
        ]

    def __str__(self) -> str:
        return f"Order #{self.pk} — {self.gig.title}"

    def involves(self, user) -> bool:
        return user.pk in (self.buyer_id, self.seller_id)

    @property
    def revisions_left(self) -> int:
        return max(0, self.revisions_allowed - self.revisions_used)

    @property
    def is_late(self) -> bool:
        if self.due_at is None or self.status in (self.Status.COMPLETED, self.Status.CANCELLED):
            return False
        return timezone.now() > self.due_at

    @property
    def missing_requirements(self) -> list[str]:
        """Required questions the buyer has not answered yet."""
        answers = self.requirements_answers or {}
        return [
            field.get("label", field.get("key", ""))
            for field in (self.gig.requirements or [])
            if field.get("required", True) and not str(answers.get(field.get("key"), "")).strip()
        ]

    def start(self) -> None:
        """Requirements are in: the delivery clock starts now, not at payment."""
        now = timezone.now()
        self.status = self.Status.ACTIVE
        self.started_at = now
        self.due_at = now + timedelta(days=self.delivery_days)
        self.save(update_fields=["status", "started_at", "due_at", "updated_at"])

    def mark_delivered(self) -> None:
        now = timezone.now()
        self.status = self.Status.DELIVERED
        self.delivered_at = now
        self.accept_by = now + timedelta(days=self.ACCEPTANCE_WINDOW_DAYS)
        self.save(update_fields=["status", "delivered_at", "accept_by", "updated_at"])

    def request_revision(self) -> None:
        self.status = self.Status.REVISION
        self.revisions_used += 1
        self.accept_by = None
        self.save(update_fields=["status", "revisions_used", "accept_by", "updated_at"])

    def complete(self) -> None:
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])


class BuyerRequest(ScopedModel):
    """A buyer describing a need so sellers can respond with custom offers.

    Section 11.2 keeps this because it is the one route to a first sale that
    does not depend on search ranking — which a new seller does not have.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        EXPIRED = "expired", "Expired"

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="buyer_requests"
    )
    description = models.TextField()
    category = models.ForeignKey(
        "marketplace.Category",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="buyer_requests",
    )
    budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    delivery_days = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.description[:60]

    @property
    def is_live(self) -> bool:
        return self.status == self.Status.OPEN and self.expires_at > timezone.now()


class CustomOffer(TimestampedModel):
    """A bespoke, privately priced offer from a seller to one buyer.

    A large share of gig revenue arrives this way, for buyers whose needs fall
    outside the published packages (Section 11.2).
    """

    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        EXPIRED = "expired", "Expired"

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="custom_offers_sent"
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="custom_offers_received"
    )
    gig = models.ForeignKey(
        Gig, null=True, blank=True, on_delete=models.SET_NULL, related_name="custom_offers"
    )
    buyer_request = models.ForeignKey(
        BuyerRequest, null=True, blank=True, on_delete=models.SET_NULL, related_name="offers"
    )
    description = models.TextField()
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("1"))]
    )
    delivery_days = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    revisions = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.SENT)
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Offer to {self.buyer_id} — {self.price}"

    @property
    def is_live(self) -> bool:
        return self.status == self.Status.SENT and self.expires_at > timezone.now()
