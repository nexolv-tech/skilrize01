"""
Review integrity checks.

Ratings are the cheapest thing on a marketplace to manufacture and the most
expensive to be wrong about, so every published review is assessed against a
set of signals before it counts toward anyone's score.

The design rule throughout: **a signal never deletes anything and never
silently decides.** Each check adds a named reason, the reasons accumulate, and
only a combination heavy enough to be implausible suppresses a review from
scoring. The row, the comment, and the reasons all survive, because the first
question a support agent asks about a suppressed review is "why", and the
second is "show me".

What this deliberately does *not* do is act on any single signal alone. Two
freelancers who genuinely hire each other, a shared university network, and a
fast reviewer are each perfectly innocent on their own; it is their
co-occurrence that is not.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger("skilrize.security")

#: Weight per signal. A review is suppressed at or above SUPPRESS_AT, and
#: merely flagged for a human above FLAG_AT. Both thresholds require more than
#: one signal to fire, which is the entire point.
SIGNAL_WEIGHTS = {
    # The two parties reviewed each other on contracts running in both
    # directions — the classic mutual-inflation ring.
    "reciprocal_pair": 3,
    # Both accounts have used the same address. Weak on its own (shared campus
    # wifi, one household, an office), which is why it is worth little alone.
    "same_network": 2,
    # A perfect score given within minutes of the contract completing, before
    # anyone could have reviewed the work.
    "instant_perfect": 2,
    # The contract was worth less than a cup of tea. Cheap contracts are how
    # review volume is bought.
    "trivial_value": 2,
    # Reviewer account created days before, with this as its only activity.
    "throwaway_account": 3,
    # This pair has traded an implausible number of contracts between them.
    "repeat_pair_volume": 2,
}

FLAG_AT = 4
SUPPRESS_AT = 6

#: Below this, a contract is too small to be evidence of anything.
TRIVIAL_CONTRACT_VALUE = 500
#: A review this fast cannot describe delivered work.
INSTANT_SECONDS = 300
#: An account younger than this reviewing once and never returning.
THROWAWAY_AGE_DAYS = 7
#: More contracts than this between one pair inside the lookback is not a
#: working relationship, it is a loop.
PAIR_VOLUME_LIMIT = 8


def assess(review) -> tuple[list[str], str]:
    """Return ``(signals, verdict)`` for one review. Pure — writes nothing."""
    signals: list[str] = []
    contract = review.contract
    author, subject = review.author, review.subject

    if _is_reciprocal(author, subject):
        signals.append("reciprocal_pair")
    if _shares_network(author, subject):
        signals.append("same_network")
    if _is_instant_perfect(review, contract):
        signals.append("instant_perfect")
    if _is_trivial_value(contract):
        signals.append("trivial_value")
    if _is_throwaway(author):
        signals.append("throwaway_account")
    if _pair_volume(author, subject) > PAIR_VOLUME_LIMIT:
        signals.append("repeat_pair_volume")

    score = sum(SIGNAL_WEIGHTS.get(signal, 0) for signal in signals)

    from .models import Review

    if score >= SUPPRESS_AT:
        return signals, Review.Integrity.SUPPRESSED
    if score >= FLAG_AT:
        return signals, Review.Integrity.FLAGGED
    return signals, Review.Integrity.CLEAN


def check(review) -> str:
    """Assess and persist. Returns the verdict."""
    signals, verdict = assess(review)

    review.integrity_signals = signals
    review.integrity_status = verdict
    review.integrity_checked_at = timezone.now()
    review.save(
        update_fields=[
            "integrity_signals",
            "integrity_status",
            "integrity_checked_at",
            "updated_at",
        ]
    )

    from .models import Review

    if verdict != Review.Integrity.CLEAN:
        logger.warning(
            "review_integrity review=%s verdict=%s signals=%s author=%s subject=%s",
            review.pk,
            verdict,
            signals,
            review.author_id,
            review.subject_id,
        )
    return verdict


def check_unassessed(limit: int = 500) -> int:
    """Work through the backlog. Returns how many were assessed."""
    from .models import Review

    pending = Review.objects.filter(
        integrity_status=Review.Integrity.UNCHECKED, published_at__isnull=False
    ).select_related("contract", "author", "subject")[:limit]

    done = 0
    for review in pending:
        try:
            check(review)
            done += 1
        except Exception:
            logger.exception("review_integrity_failed review=%s", review.pk)
    return done


# --- Individual signals -----------------------------------------------------


def _is_reciprocal(author, subject) -> bool:
    """Have these two hired each other in both directions?

    Legitimate — some people genuinely trade work — but it is also exactly how
    two accounts manufacture a rating for each other, so it carries the most
    weight of any single signal without being decisive alone.
    """
    from .models import Contract

    forward = Contract.objects.unscoped().filter(client=subject, freelancer=author).exists()
    backward = Contract.objects.unscoped().filter(client=author, freelancer=subject).exists()
    return forward and backward


def _shares_network(author, subject) -> bool:
    from accounts.models import RefreshSession

    def addresses(user) -> set[str]:
        return set(
            RefreshSession.objects.filter(user=user, ip_address__isnull=False)
            .values_list("ip_address", flat=True)
            .distinct()[:50]
        )

    mine = addresses(author)
    return bool(mine and mine & addresses(subject))


def _is_instant_perfect(review, contract) -> bool:
    if review.overall < 5:
        return False
    finished = contract.completed_at or contract.updated_at
    if not finished:
        return False
    return (review.created_at - finished).total_seconds() < INSTANT_SECONDS


def _is_trivial_value(contract) -> bool:
    return bool(contract.total_amount) and contract.total_amount < TRIVIAL_CONTRACT_VALUE


def _is_throwaway(author) -> bool:
    """A days-old account whose only act was to leave this review."""
    from .models import Contract

    if (timezone.now() - author.created_at).days > THROWAWAY_AGE_DAYS:
        return False
    activity = Contract.objects.unscoped().filter(Q(client=author) | Q(freelancer=author)).count()
    return activity <= 1


def _pair_volume(author, subject) -> int:
    from .models import Contract

    since = timezone.now() - timedelta(days=365)
    return (
        Contract.objects.unscoped()
        .filter(
            Q(client=author, freelancer=subject) | Q(client=subject, freelancer=author),
            created_at__gte=since,
        )
        .aggregate(total=Count("id"))["total"]
        or 0
    )
