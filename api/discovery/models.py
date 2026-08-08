"""
Promoted placement and the global work showcase.

Both are discovery surfaces, and both are governed by the same rule: **a paid
placement is always labelled, and it never displaces an honest result it did
not out-rank on merit.** Promotion is a bounded additive term in the ranking
formula (`core.search.PROMOTION_WEIGHT`), not a bypass of it — a bad listing
with a budget still loses to a good one without.

That is a product decision as much as an ethical one. A search where the top
result is simply whoever paid most is a search people stop trusting, and a
marketplace nobody trusts has nothing left to sell.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import ScopedModel, TimestampedModel
from core.scope import Visibility


class Promotion(TimestampedModel):
    """A seller paying to raise one gig's placement.

    Deliberately *not* an auction. A second-price auction is the standard
    answer and it is the right one at scale, but it needs enough bidders per
    query for the clearing price to mean anything; run on a thin marketplace it
    just charges the only bidder their maximum. A flat daily rate is honest
    about what it is until there is competition to clear.
    """

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        ACTIVE = "active", "Running"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Finished"
        EXHAUSTED = "exhausted", "Budget spent"

    gig = models.ForeignKey("gigs.Gig", on_delete=models.CASCADE, related_name="promotions")
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="promotions"
    )

    daily_budget = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("100"))]
    )
    total_budget = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("100"))]
    )
    spent = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.SCHEDULED, db_index=True
    )

    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "starts_at", "ends_at"])]

    def __str__(self) -> str:
        return f"Promotion of gig {self.gig_id} ({self.status})"

    def clean(self) -> None:
        super().clean()
        if self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "A promotion must end after it starts."})
        if self.total_budget < self.daily_budget:
            raise ValidationError(
                {"total_budget": "The total budget cannot be less than one day's budget."}
            )

    @property
    def is_live(self) -> bool:
        now = timezone.now()
        return (
            self.status == self.Status.ACTIVE
            and self.starts_at <= now
            and (self.ends_at is None or self.ends_at > now)
            and self.spent < self.total_budget
        )

    @property
    def click_through_rate(self) -> float:
        return round(self.clicks * 100 / self.impressions, 2) if self.impressions else 0.0

    def sync_gig_flag(self) -> None:
        """Mirror live-ness onto the gig, which is what ranking reads.

        The flag is denormalised because ranking touches it on every row of
        every search; joining to promotions there would put a date comparison
        in the hot path of the most-run query on the platform.
        """
        from gigs.models import Gig

        Gig.all_objects.filter(pk=self.gig_id).update(is_promoted=self.is_live)


class ShowcaseItem(ScopedModel):
    """A piece of completed work, published to the global showcase.

    Sourced from finished contracts rather than a free-form portfolio upload,
    which is the whole point: anyone can upload a picture and claim it, but a
    showcase entry here is backed by a contract that was delivered, accepted,
    and reviewed. That provenance is the only thing that makes a portfolio on a
    marketplace worth more than one on a personal site.

    Both parties must agree before it appears. A client who paid for work they
    would rather not advertise has a legitimate interest in it staying private,
    and a freelancer who did good work has an equally legitimate interest in
    showing it — so it takes two yeses and either side can withdraw.
    """

    contract = models.OneToOneField(
        "contracts.Contract", on_delete=models.CASCADE, related_name="showcase"
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="showcase_items"
    )

    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    cover = models.ForeignKey(
        "core.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    category = models.ForeignKey(
        "marketplace.Category", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    skills = models.JSONField(default=list, blank=True)

    seller_approved = models.BooleanField(default=False)
    client_approved = models.BooleanField(default=False)
    #: Copied at publication, not joined. A showcase entry is a record of what
    #: the work scored at the time; a later review edit must not silently
    #: rewrite history on somebody's portfolio.
    rating_at_publication = models.PositiveSmallIntegerField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(ScopedModel.Meta):
        ordering = ["-published_at", "-created_at"]
        indexes = [models.Index(fields=["visibility", "university", "-published_at"])]

    def __str__(self) -> str:
        return self.title

    @property
    def is_published(self) -> bool:
        return self.published_at is not None

    def publish_if_ready(self) -> bool:
        """Publish once both sides have agreed. Returns whether it published."""
        if self.published_at or not (self.seller_approved and self.client_approved):
            return False

        from contracts.models import Review

        review = (
            Review.objects.filter(
                contract=self.contract,
                role=Review.Role.CLIENT,
                published_at__isnull=False,
            )
            .exclude(integrity_status=Review.Integrity.SUPPRESSED)
            .first()
        )
        self.rating_at_publication = review.overall if review else None
        self.published_at = timezone.now()
        self.save(update_fields=["rating_at_publication", "published_at", "updated_at"])
        return True

    def withdraw(self, by_user) -> None:
        """Either party can pull it back at any time, permission included."""
        if by_user.pk == self.seller_id:
            self.seller_approved = False
        else:
            self.client_approved = False
        self.published_at = None
        self.save(
            update_fields=["seller_approved", "client_approved", "published_at", "updated_at"]
        )

    @classmethod
    def draft_for(cls, contract) -> ShowcaseItem | None:
        """Offer a showcase entry once a contract completes.

        Created unapproved: it exists so both parties have something to say yes
        to, and it is invisible until they do.
        """
        from contracts.models import Contract

        if contract.status != Contract.Status.COMPLETED:
            return None
        # `all_objects`: this is keyed on a unique contract and is reached from
        # background work as often as from a request, so it must not depend on
        # a scope being active. The surface is set explicitly below from the
        # contract, which is the authority on where this work happened.
        item, _ = cls.all_objects.get_or_create(
            contract=contract,
            defaults={
                "seller": contract.freelancer,
                "title": contract.title[:200],
                "category_id": getattr(contract.project, "category_id", None),
                # A showcase entry lives on the surface its contract did, so
                # campus work never becomes a global advertisement.
                "visibility": contract.visibility,
                "university_id": contract.university_id,
            },
        )
        return item


class SearchLog(TimestampedModel):
    """What people searched for, and whether it worked.

    Kept because the roadmap's own caveat about Phase 6 — that ranking needs
    real history to tune against — only stops being true if somebody starts
    recording the history. Zero-result queries in particular are the cheapest
    product feedback on a marketplace: they are a list of things buyers want
    and nobody is selling.

    Deliberately stores no user id. The term and the result count are enough to
    tune ranking; tying a search history to a person is a different dataset with
    a different risk profile, and this does not need it.
    """

    term = models.CharField(max_length=200, db_index=True)
    kind = models.CharField(
        max_length=12,
        choices=[("gigs", "Services"), ("projects", "Projects")],
        default="gigs",
    )
    result_count = models.PositiveIntegerField(default=0)
    #: Which surface it ran on, so campus and global demand can be told apart.
    visibility = models.CharField(
        max_length=16,
        choices=[(v, v.name.title()) for v in Visibility],
        default=Visibility.GLOBAL,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["result_count", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.term} ({self.result_count})"

    @classmethod
    def record(cls, term: str, kind: str, count: int, visibility: str) -> None:
        """Best-effort. Analytics must never break a search."""
        import logging

        term = (term or "").strip()[:200]
        if not term:
            return
        try:
            cls.objects.create(
                term=term.lower(), kind=kind, result_count=count, visibility=visibility
            )
        except Exception:
            logging.getLogger(__name__).exception("search_log_failed term=%s", term)


def expire_promotions() -> int:
    """Close promotions past their end date or budget. Returns how many."""
    now = timezone.now()
    changed = 0

    for promotion in Promotion.objects.filter(
        status__in=[Promotion.Status.ACTIVE, Promotion.Status.SCHEDULED]
    ).select_related("gig"):
        if promotion.status == Promotion.Status.SCHEDULED and promotion.starts_at <= now:
            promotion.status = Promotion.Status.ACTIVE
        elif promotion.spent >= promotion.total_budget:
            promotion.status = Promotion.Status.EXHAUSTED
        elif promotion.ends_at and promotion.ends_at <= now:
            promotion.status = Promotion.Status.COMPLETED
        else:
            promotion.sync_gig_flag()
            continue

        promotion.save(update_fields=["status", "updated_at"])
        promotion.sync_gig_flag()
        changed += 1

    return changed


def promotion_window() -> timedelta:
    """Shortest bookable run. Anything less cannot gather usable data."""
    return timedelta(days=1)
