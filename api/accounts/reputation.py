"""
Job Success Score and seller levels.

Two numbers that decide who gets seen, so both are computed here and nowhere
else. They are written only by `recompute_for`, which the nightly task and the
contract-completion hook both call — nothing else on the platform may set
`job_success_score` or `level`, and the admin renders them read-only.

A note on tuning, recorded because it will otherwise be forgotten: the weights
below are *stated*, not *fitted*. Fitting them needs a body of completed,
paid contracts with known outcomes, which does not exist until the payments
phase has been running for a while. They are therefore expressed as named
constants with the reasoning attached, so that when the data does arrive the
argument to be had is about the numbers rather than about where they live.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)

#: A score is meaningless on one contract. Below this, sellers are shown as
#: "new" rather than carrying a number that a single review would swing by
#: forty points.
MIN_CONTRACTS_FOR_SCORE = 3

#: What the score is made of. Weights sum to 1.0.
#:
#: Outcome dominates because it is the only component a seller cannot
#: manufacture: it counts contracts that reached completion against those that
#: were cancelled after work began. Ratings are weighted lower than they look
#: like they should be — they are self-reported, inflated across every
#: marketplace of this kind, and the integrity checks in `contracts.integrity`
#: exist precisely because they are the easiest component to game.
WEIGHT_OUTCOME = Decimal("0.40")
WEIGHT_RATING = Decimal("0.30")
WEIGHT_ON_TIME = Decimal("0.20")
WEIGHT_REPEAT = Decimal("0.10")

#: Work older than this stops counting. A score should describe who somebody is
#: now, not who they were three years ago.
LOOKBACK_DAYS = 730


@dataclass(frozen=True, slots=True)
class Reputation:
    """The computed picture for one seller."""

    job_success_score: int | None
    contracts_completed: int
    on_time_delivery_rate: int | None
    repeat_client_rate: int | None
    average_rating: Decimal | None
    level: str

    @property
    def is_established(self) -> bool:
        return self.job_success_score is not None


class SellerLevel:
    """Ladder rungs, in ascending order.

    Deliberately not a `TextChoices` on the model alone: the thresholds are the
    interesting part and they belong next to the definition, not scattered
    across whatever code happens to check them.
    """

    NEW = "new"
    LEVEL_ONE = "level_one"
    LEVEL_TWO = "level_two"
    TOP_RATED = "top_rated"

    CHOICES = [
        (NEW, "New seller"),
        (LEVEL_ONE, "Level 1"),
        (LEVEL_TWO, "Level 2"),
        (TOP_RATED, "Top Rated"),
    ]

    #: (level, min contracts, min score, min on-time, min days since joining)
    #:
    #: Tenure is in here alongside volume because every threshold that counts
    #: only completions can be climbed in a weekend by a ring of accounts
    #: trading tiny contracts with each other. Time is the one input that
    #: cannot be bought.
    LADDER = [
        (TOP_RATED, 20, 90, 90, 180),
        (LEVEL_TWO, 10, 85, 85, 90),
        (LEVEL_ONE, 3, 75, 75, 30),
    ]

    @classmethod
    def evaluate(
        cls, *, contracts: int, score: int | None, on_time: int | None, age_days: int
    ) -> str:
        if score is None:
            return cls.NEW
        for level, min_contracts, min_score, min_on_time, min_age in cls.LADDER:
            if (
                contracts >= min_contracts
                and score >= min_score
                and (on_time or 0) >= min_on_time
                and age_days >= min_age
            ):
                return level
        return cls.NEW


def compute(user) -> Reputation:
    """Work out a seller's reputation from their contract history.

    Reads nothing but contracts and published reviews. In particular it never
    reads the stored score, so a corrupted value cannot perpetuate itself
    across recomputations.
    """
    from contracts.models import Contract, Milestone, Review

    since = timezone.now() - timedelta(days=LOOKBACK_DAYS)

    # `unscoped` on purpose: a seller's reputation follows them between the
    # global marketplace and their campus portal. Scoping it would give the
    # same person two different scores depending on where you looked at them,
    # and the higher one would always be the one they linked to.
    contracts = Contract.objects.unscoped().filter(freelancer=user, created_at__gte=since)

    completed = contracts.filter(status=Contract.Status.COMPLETED).count()
    # Only cancellations *after* work started count against anyone. A contract
    # cancelled before the freelancer began is a client changing their mind.
    abandoned = (
        contracts.filter(
            status=Contract.Status.CANCELLED,
            milestones__status__in=[
                Milestone.Status.FUNDED,
                Milestone.Status.IN_PROGRESS,
                Milestone.Status.DELIVERED,
            ],
        )
        .distinct()
        .count()
    )

    finished = completed + abandoned
    if completed < MIN_CONTRACTS_FOR_SCORE:
        return Reputation(
            job_success_score=None,
            contracts_completed=completed,
            on_time_delivery_rate=None,
            repeat_client_rate=None,
            average_rating=None,
            level=SellerLevel.NEW,
        )

    outcome = Decimal(completed) / Decimal(finished or 1)

    # Published reviews only, and only ones integrity has not flagged.
    reviews = Review.objects.filter(
        subject=user,
        role=Review.Role.CLIENT,
        published_at__isnull=False,
        created_at__gte=since,
    ).exclude(integrity_status=Review.Integrity.SUPPRESSED)

    aggregate = reviews.aggregate(mean=Avg("overall"), total=Count("id"))
    average_rating = aggregate["mean"]
    # A five-star average sits at 1.0; anything below three is worth ~nothing,
    # because on a scale where almost everyone is above four, a three is a
    # complaint.
    rating_component = (
        max(Decimal(0), (Decimal(str(average_rating)) - Decimal(3)) / Decimal(2))
        if average_rating
        else Decimal("0.5")
    )

    on_time = _on_time_rate(contracts)
    repeat = _repeat_client_rate(contracts, completed)

    raw = (
        WEIGHT_OUTCOME * outcome
        + WEIGHT_RATING * rating_component
        + WEIGHT_ON_TIME
        * (Decimal(on_time) / Decimal(100) if on_time is not None else Decimal("0.8"))
        + WEIGHT_REPEAT * (Decimal(repeat) / Decimal(100) if repeat is not None else Decimal(0))
    )
    score = int(max(Decimal(0), min(Decimal(1), raw)) * 100)

    age_days = (timezone.now() - user.created_at).days
    return Reputation(
        job_success_score=score,
        contracts_completed=completed,
        on_time_delivery_rate=on_time,
        repeat_client_rate=repeat,
        average_rating=Decimal(str(round(average_rating, 2))) if average_rating else None,
        level=SellerLevel.evaluate(
            contracts=completed, score=score, on_time=on_time, age_days=age_days
        ),
    )


def _on_time_rate(contracts) -> int | None:
    """Share of milestones delivered on or before their due date."""
    from contracts.models import Milestone

    delivered = Milestone.objects.filter(
        contract__in=contracts, delivered_at__isnull=False, due_date__isnull=False
    )
    total = delivered.count()
    if not total:
        return None
    # Compared as dates: a delivery at 23:50 on the due date is on time.
    punctual = sum(
        1 for m in delivered.only("delivered_at", "due_date") if m.delivered_at.date() <= m.due_date
    )
    return round(punctual * 100 / total)


def _repeat_client_rate(contracts, completed: int) -> int | None:
    """Share of completed contracts that came from a returning client.

    The strongest available quality signal: a client who hires the same person
    twice is voting with something more expensive than a star rating.
    """
    from contracts.models import Contract

    if not completed:
        return None
    repeats = (
        contracts.filter(status=Contract.Status.COMPLETED)
        .values("client_id")
        .annotate(times=Count("id"))
        .filter(times__gt=1)
        .aggregate(extra=Count("client_id"))
    )
    returning = repeats["extra"] or 0
    return round(returning * 100 / completed)


def recompute_for(user) -> Reputation:
    """Compute and persist. The only writer of these fields."""
    from .models import SellerProfile

    reputation = compute(user)
    profile, _ = SellerProfile.objects.get_or_create(user=user)
    profile.job_success_score = reputation.job_success_score
    profile.contracts_completed = reputation.contracts_completed
    profile.on_time_delivery_rate = reputation.on_time_delivery_rate
    profile.repeat_client_rate = reputation.repeat_client_rate
    profile.average_rating = reputation.average_rating
    profile.level = reputation.level
    profile.reputation_updated_at = timezone.now()
    profile.save(
        update_fields=[
            "job_success_score",
            "contracts_completed",
            "on_time_delivery_rate",
            "repeat_client_rate",
            "average_rating",
            "level",
            "reputation_updated_at",
            "updated_at",
        ]
    )
    return reputation


def recompute_stale(limit: int = 500) -> int:
    """Refresh the sellers whose numbers are oldest. Returns how many.

    Batched rather than recomputing everyone, because this walks contract
    history per seller and the whole platform in one transaction is exactly the
    job that starts timing out six months from now.
    """
    from .models import SellerProfile

    stale = (
        SellerProfile.objects.filter(
            Q(reputation_updated_at__isnull=True)
            | Q(reputation_updated_at__lt=timezone.now() - timedelta(hours=24))
        )
        .select_related("user")
        .order_by("reputation_updated_at")[:limit]
    )

    done = 0
    for profile in stale:
        try:
            recompute_for(profile.user)
            done += 1
        except Exception:
            # One seller's bad data must not stop the batch.
            logger.exception("reputation_failed user=%s", profile.user_id)
    return done
