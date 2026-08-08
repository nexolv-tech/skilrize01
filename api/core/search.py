"""
Full-text search, ranking, and facets.

PostgreSQL FTS rather than a search cluster, deliberately. A separate engine
introduces a second datastore that must be kept in sync with the database, and
every stale-index bug that follows is a listing a seller swears they published.
Postgres has none of that: the index is updated in the same transaction as the
row. It stops being the right answer somewhere north of a few million listings,
by which point the catalogue itself will be telling us.

Three things live here, and they are separate on purpose:

* **Matching** — what the query lets through. A `SearchVector` over weighted
  fields, plus a trigram fallback so a misspelled search still finds things.
* **Ranking** — the order of what got through. Relevance is only one input;
  reputation, freshness, and promotion all move a result.
* **Facets** — the counts beside each filter. Computed from the *matched* set
  before the user's own facet filters narrow it, which is the part everyone
  gets wrong.

Every query starts from a scope-enforcing manager, so tenancy is applied before
matching runs — never as a post-filter over ranked results, which would leak
existence through counts and pagination.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramWordSimilarity,
)
from django.db.models import Case, Count, DecimalField, F, FloatField, Q, QuerySet, Value, When
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone

#: Field weights. Postgres offers exactly four (A–D) and they are relative, not
#: absolute: A is roughly four times D. Title carries the most because a gig
#: title on this platform is a constrained, human-written summary of the whole
#: offer — it is the highest-signal text there is.
WEIGHT_TITLE = "A"
WEIGHT_TAGS = "B"
WEIGHT_SKILLS = "C"
WEIGHT_BODY = "D"

#: Below this, a trigram match is noise rather than a near-miss.
TRIGRAM_FLOOR = 0.25

#: How the final ordering is composed. These are stated rather than fitted —
#: tuning them needs completed, paid contracts to measure against, which the
#: payments phase has not yet produced. They are named and gathered here so the
#: eventual argument is about the numbers, not about where they live.
RELEVANCE_WEIGHT = 1.0
REPUTATION_WEIGHT = 0.35
FRESHNESS_WEIGHT = 0.15
PROMOTION_WEIGHT = 0.50

#: A listing stops counting as new after this. Freshness exists so a brand-new
#: seller is discoverable at all; it is not meant to outweigh a track record.
FRESHNESS_DAYS = 30


@dataclass(slots=True)
class Facet:
    """One filter option and how many results carry it."""

    value: str
    label: str
    count: int


@dataclass(slots=True)
class SearchResult:
    queryset: QuerySet
    total: int
    facets: dict[str, list[Facet]] = field(default_factory=dict)
    #: Set when the query was corrected or relaxed, so the UI can say so.
    note: str = ""


def build_vector(*, title: str, tags: str, skills: str, body: str) -> SearchVector:
    """The weighted vector expression, shared by indexing and by querying."""
    return (
        SearchVector(title, weight=WEIGHT_TITLE, config="english")
        + SearchVector(tags, weight=WEIGHT_TAGS, config="english")
        + SearchVector(skills, weight=WEIGHT_SKILLS, config="english")
        + SearchVector(body, weight=WEIGHT_BODY, config="english")
    )


#: Characters that mean the user is issuing an instruction, not just naming a
#: thing: `-` excludes, `"` quotes a phrase, `OR` widens.
_OPERATORS = ('"', " -", "OR")


def has_operators(term: str) -> bool:
    return any(token in f" {term}" for token in _OPERATORS)


def apply_text_search(queryset: QuerySet, term: str, *, title_field: str = "title") -> QuerySet:
    """Filter to rows matching ``term``, annotating `relevance`.

    Two matchers. `websearch` handles quoted phrases and `-exclusions` the way
    people actually type into a search box. Trigram *word* similarity catches
    the misspellings FTS cannot, because a stemmer has no idea that "photshop"
    was meant to be "photoshop".

    The fuzzy matcher is deliberately switched off when the query contains
    operators, and that is not a detail. ORing a similarity match back in
    resurrects exactly the rows the user just excluded — search for
    `build -website` and the website result returns anyway, because it is still
    textually similar. An exclusion that does not exclude is worse than no
    exclusion at all, so when someone asks precisely, only the precise matcher
    answers.

    Word similarity rather than whole-string similarity: comparing "photshop"
    against a full title scores near zero because most of the title is other
    words. `TrigramWordSimilarity` compares the term against the best-matching
    word inside the string, which is what a misspelling actually is.
    """
    if not term:
        return queryset.annotate(relevance=Value(0.0, output_field=FloatField()))

    query = SearchQuery(term, config="english", search_type="websearch")
    precise_only = has_operators(term)

    annotated = queryset.annotate(
        fts_rank=SearchRank(F("search_vector"), query),
        fuzzy=TrigramWordSimilarity(term, title_field),
    )

    if precise_only:
        return annotated.filter(search_vector=query).annotate(
            relevance=F("fts_rank"),
        )

    return annotated.filter(Q(search_vector=query) | Q(fuzzy__gt=TRIGRAM_FLOOR)).annotate(
        # Whichever matcher was more confident wins, so a strong exact match is
        # never dragged down by a weak fuzzy score or the reverse.
        relevance=Greatest("fts_rank", "fuzzy", output_field=FloatField())
    )


def apply_ranking(
    queryset: QuerySet,
    *,
    reputation_path: str,
    published_path: str,
    promoted: bool = True,
) -> QuerySet:
    """Annotate `score` and order by it.

    `reputation_path` and `published_path` are passed in because gigs and
    projects reach the same concepts by different relations — the alternative
    is two near-identical copies of this function that drift apart.
    """
    cutoff = timezone.now() - timedelta(days=FRESHNESS_DAYS)

    queryset = queryset.annotate(
        # 0–1, from the 0–100 job success score. An unscored seller sits at
        # 0.5 rather than 0: a new seller should start mid-table, not last,
        # or nobody new is ever discovered and the ladder has no bottom rung.
        reputation=Coalesce(
            F(reputation_path) / Value(100.0, output_field=FloatField()),
            Value(0.5, output_field=FloatField()),
            output_field=FloatField(),
        ),
        freshness=Case(
            When(**{f"{published_path}__gte": cutoff}, then=Value(1.0)),
            default=Value(0.0),
            output_field=FloatField(),
        ),
    )

    if promoted:
        queryset = queryset.annotate(
            promotion=Case(
                When(is_promoted=True, then=Value(1.0)),
                default=Value(0.0),
                output_field=FloatField(),
            )
        )
    else:
        queryset = queryset.annotate(promotion=Value(0.0, output_field=FloatField()))

    return queryset.annotate(
        score=(
            F("relevance") * Value(RELEVANCE_WEIGHT, output_field=FloatField())
            + F("reputation") * Value(REPUTATION_WEIGHT, output_field=FloatField())
            + F("freshness") * Value(FRESHNESS_WEIGHT, output_field=FloatField())
            + F("promotion") * Value(PROMOTION_WEIGHT, output_field=FloatField())
        )
    ).order_by("-score", "-id")


def facets_for(queryset: QuerySet, spec: dict[str, str]) -> dict[str, list[Facet]]:
    """Count each facet value across ``queryset``.

    Takes the queryset *before* the user's facet selections are applied. A
    facet list computed after filtering shows every unselected option as zero,
    which makes the filters unusable the moment somebody picks one.
    """
    result: dict[str, list[Facet]] = {}
    for name, path in spec.items():
        rows = (
            queryset.values(path)
            .annotate(count=Count("id", distinct=True))
            .filter(count__gt=0)
            .order_by("-count")[:25]
        )
        result[name] = [
            Facet(value=str(row[path]), label=str(row[path]), count=row["count"])
            for row in rows
            if row[path] is not None
        ]
    return result


def price_buckets(queryset: QuerySet, path: str) -> list[Facet]:
    """Fixed price bands rather than a computed histogram.

    Bands that move with the result set make the filter useless: the same
    listing falls in "budget" for one search and "premium" for another, and a
    user who ticks a band cannot tell what they asked for.
    """
    bands = [
        ("0-5000", "Under Rs 5,000", Q(**{f"{path}__lt": 5000})),
        ("5000-15000", "Rs 5,000 – 15,000", Q(**{f"{path}__gte": 5000, f"{path}__lt": 15000})),
        ("15000-50000", "Rs 15,000 – 50,000", Q(**{f"{path}__gte": 15000, f"{path}__lt": 50000})),
        ("50000-", "Rs 50,000+", Q(**{f"{path}__gte": 50000})),
    ]
    return [
        Facet(value=value, label=label, count=queryset.filter(condition).count())
        for value, label, condition in bands
    ]


def parse_price_band(band: str) -> Q:
    """Turn a `min-max` band back into a filter. Unknown bands match nothing."""
    if not band or "-" not in band:
        return Q()
    low, _, high = band.partition("-")
    condition = Q()
    if low:
        condition &= Q(price_floor__gte=Decimal(low))
    if high:
        condition &= Q(price_floor__lt=Decimal(high))
    return condition


def as_decimal_field() -> DecimalField:
    return DecimalField(max_digits=12, decimal_places=2)
