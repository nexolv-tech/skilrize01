"""
Tests for search, ranking, reputation, review integrity, and promoted placement.

The rules worth guarding here are the ones a marketplace loses trust over: a
paid placement that outranks merit, a fraud check that fires on a single
innocent signal, a score that swings on one review, and a facet count that goes
to zero the moment somebody uses a filter.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from accounts.models import SellerProfile, University, VerificationStatus
from accounts.reputation import SellerLevel
from core.scope import GLOBAL_SCOPE, Scope, SurfaceKind, Visibility, use_scope
from discovery.models import SearchLog, ShowcaseItem
from gigs.models import Gig, Package
from marketplace.models import Category
from marketplace.tests import make_user, sign_in


@pytest.fixture
def category(db):
    return Category.objects.create(name="Development & IT", slug="development-it")


def make_gig(seller, title: str, *, price=10000, university=None, category=None) -> Gig:
    visibility = Visibility.UNIVERSITY if university else Visibility.GLOBAL
    scope = Scope(SurfaceKind.UNIVERSITY, university.pk) if university else GLOBAL_SCOPE
    with use_scope(scope):
        gig = Gig.objects.create(
            seller=seller,
            title=title,
            description=f"A detailed description of {title} with plenty of searchable words.",
            tags=["design", "branding"],
            status=Gig.Status.ACTIVE,
            published_at=timezone.now(),
            visibility=visibility,
            university=university,
            category=category,
        )
        Package.objects.create(
            gig=gig,
            tier=Package.Tier.BASIC,
            name="Basic",
            price=Decimal(price),
            delivery_days=3,
            revisions=1,
        )
    return gig


# --- Full-text search -------------------------------------------------------


@pytest.mark.django_db
def test_search_matches_on_title_and_body(category):
    seller = make_user("seller@example.com")
    make_gig(seller, "I will design a logo", category=category)
    make_gig(seller, "I will write Python code", category=category)

    client = sign_in(make_user("buyer@example.com"))
    results = client.get("/api/v1/search/gigs/?q=logo").data
    assert [row["title"] for row in results["results"]] == ["I will design a logo"]


@pytest.mark.django_db
def test_search_survives_a_misspelling(category):
    """A stemmer cannot fix a typo; the trigram fallback can."""
    seller = make_user("seller@example.com")
    make_gig(seller, "I will retouch your photoshop images", category=category)

    client = sign_in(make_user("buyer@example.com"))
    results = client.get("/api/v1/search/gigs/?q=photshop").data
    assert results["count"] == 1


@pytest.mark.django_db
def test_search_understands_quoted_phrases_and_exclusions(category):
    seller = make_user("seller@example.com")
    make_gig(seller, "I will build a mobile app", category=category)
    make_gig(seller, "I will build a website", category=category)

    client = sign_in(make_user("buyer@example.com"))
    results = client.get("/api/v1/search/gigs/?q=build -website").data
    titles = [row["title"] for row in results["results"]]
    assert "I will build a mobile app" in titles
    assert "I will build a website" not in titles


@pytest.mark.django_db
def test_an_empty_query_returns_the_catalogue(category):
    seller = make_user("seller@example.com")
    make_gig(seller, "I will design a logo", category=category)

    client = sign_in(make_user("buyer@example.com"))
    assert client.get("/api/v1/search/gigs/").data["count"] == 1


@pytest.mark.django_db
def test_search_never_crosses_a_surface(category):
    """The leakage gate applies to search exactly as it does to browse."""
    cui = University.objects.create(name="COMSATS", short_code="CUI")
    student = make_user("student@example.com")
    student.university = cui
    student.student_verification_status = VerificationStatus.VERIFIED
    student.save()

    make_gig(student, "I will design campus posters", university=cui, category=category)

    outsider = sign_in(make_user("outsider@example.com"))
    assert outsider.get("/api/v1/search/gigs/?q=posters").data["count"] == 0


# --- Facets -----------------------------------------------------------------


@pytest.mark.django_db
def test_facets_are_counted_before_the_user_filters(category):
    """The bug this guards: facet counts computed after filtering read zero for
    every option the user did not pick, so the filters become unusable."""
    other = Category.objects.create(name="Design & Creative", slug="design-creative")
    seller = make_user("seller@example.com")
    make_gig(seller, "I will build an API", category=category)
    make_gig(seller, "I will design a logo", category=other)

    client = sign_in(make_user("buyer@example.com"))
    filtered = client.get("/api/v1/search/gigs/?category=design-creative").data

    assert filtered["count"] == 1
    counts = {row["value"]: row["count"] for row in filtered["facets"]["category"]}
    # Both categories still carry a count, so the user can switch to the other.
    assert counts.get("Development & IT") == 1
    assert counts.get("Design & Creative") == 1


@pytest.mark.django_db
def test_price_bands_are_fixed_not_derived(category):
    seller = make_user("seller@example.com")
    make_gig(seller, "I will do cheap work", price=2000, category=category)
    make_gig(seller, "I will do expensive work", price=80000, category=category)

    client = sign_in(make_user("buyer@example.com"))
    bands = {
        row["value"]: row["count"]
        for row in client.get("/api/v1/search/gigs/").data["facets"]["price"]
    }
    assert bands["0-5000"] == 1
    assert bands["50000-"] == 1


@pytest.mark.django_db
def test_sorting_by_price_does_not_duplicate_a_gig_with_several_packages(category):
    """A gig appeared once per package rather than once, total — and worse,
    legitimate *other* gigs could go missing along with it.

    `?sort=price` used to order by the raw related field — `packages__price`
    — which joins the packages table a second time. Postgres requires an
    ORDER BY column used with SELECT DISTINCT to appear in the select list, so
    that price rode along in the row, and a gig with three packages produced
    three rows sharing one id.

    That alone would just be a visible duplicate. What made it worse: DRF's
    paginator calls `.count()` to size the page, and Django's `.count()`
    optimisation for a queryset like this reports the *true* number of
    distinct gigs — 2 here — while the actual row fetch still returns the
    undeduplicated 4-row set. The paginator then slices `[0:2]` against that
    4-row set, not the 2-row one the count implied. Put the multi-package
    gig's three prices at the *cheapest* end and the slice never reaches the
    single-package gig at all: two rows come back, both the same id, and the
    other gig vanishes from a results page that claimed to hold it.

    Prices are chosen so a test that only checked "no duplicate key" would
    have passed anyway, by accident, if the truncation happened to land after
    the duplicate rather than before it — the way an earlier version of this
    test did. Asserting the exact id set closes that gap.
    """
    seller = make_user("seller@example.com")
    layered = make_gig(seller, "I will do a three-tier gig", price=1000, category=category)
    Package.objects.create(
        gig=layered,
        tier=Package.Tier.STANDARD,
        name="Standard",
        price=Decimal("2000"),
        delivery_days=5,
        revisions=2,
    )
    Package.objects.create(
        gig=layered,
        tier=Package.Tier.PREMIUM,
        name="Premium",
        price=Decimal("3000"),
        delivery_days=7,
        revisions=3,
    )
    single = make_gig(seller, "I will do a single-tier gig", price=50000, category=category)

    client = sign_in(make_user("buyer@example.com"))
    response = client.get("/api/v1/search/gigs/?sort=price")

    assert response.data["count"] == 2
    ids = [row["id"] for row in response.data["results"]]
    assert set(ids) == {single.pk, layered.pk}, f"got {ids}"
    assert len(ids) == len(set(ids)), f"duplicate id in {ids}"
    # The cheapest package decides where a multi-tier gig sorts, not an
    # arbitrary one of its three price rows.
    assert ids == [layered.pk, single.pk]


# --- Ranking and promotion --------------------------------------------------


@pytest.mark.django_db
def test_a_promoted_listing_is_labelled(category):
    seller = make_user("seller@example.com")
    gig = make_gig(seller, "I will design a logo", category=category)
    Gig.all_objects.filter(pk=gig.pk).update(is_promoted=True)

    client = sign_in(make_user("buyer@example.com"))
    row = client.get("/api/v1/search/gigs/?q=logo").data["results"][0]
    assert row["is_promoted"] is True


@pytest.mark.django_db
def test_promotion_lifts_but_does_not_override_an_explicit_sort(category):
    """Someone who asked for "newest" means newest — not "newest, nudged by
    whoever paid". A paid slot that survives an explicit sort is an advert
    pretending to be a result."""
    seller = make_user("seller@example.com")
    old = make_gig(seller, "I will do old promoted work", category=category)
    Gig.all_objects.filter(pk=old.pk).update(
        is_promoted=True, published_at=timezone.now() - timedelta(days=30)
    )
    newest = make_gig(seller, "I will do brand new work", category=category)

    client = sign_in(make_user("buyer@example.com"))
    by_newest = client.get("/api/v1/search/gigs/?sort=newest").data["results"]
    assert by_newest[0]["id"] == newest.pk


@pytest.mark.django_db
def test_you_can_only_promote_your_own_active_gig(category):
    seller = make_user("seller@example.com")
    other = make_user("other@example.com")
    gig = make_gig(seller, "I will design a logo", category=category)

    refused = sign_in(other).post(
        "/api/v1/promotions/",
        {"gig": gig.pk, "daily_budget": "500", "total_budget": "5000"},
        format="json",
    )
    assert refused.status_code == 400

    allowed = sign_in(seller).post(
        "/api/v1/promotions/",
        {"gig": gig.pk, "daily_budget": "500", "total_budget": "5000"},
        format="json",
    )
    assert allowed.status_code == 201
    gig.refresh_from_db()
    assert gig.is_promoted is True


@pytest.mark.django_db
def test_a_budget_smaller_than_one_day_is_refused(category):
    seller = make_user("seller@example.com")
    gig = make_gig(seller, "I will design a logo", category=category)

    response = sign_in(seller).post(
        "/api/v1/promotions/",
        {"gig": gig.pk, "daily_budget": "5000", "total_budget": "1000"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_impressions_and_clicks_are_counted_separately(category):
    seller = make_user("seller@example.com")
    gig = make_gig(seller, "I will design a logo", category=category)

    client = sign_in(make_user("buyer@example.com"))
    client.get("/api/v1/search/gigs/?q=logo")
    gig.refresh_from_db()
    assert gig.impressions == 1
    assert gig.clicks == 0

    client.post(f"/api/v1/gigs/{gig.pk}/click/")
    gig.refresh_from_db()
    assert gig.clicks == 1


# --- Reputation -------------------------------------------------------------


@pytest.mark.django_db
def test_a_seller_with_too_little_history_has_no_score():
    """One contract is not evidence. A score on a single review would swing
    forty points on the next one."""
    from accounts.reputation import compute

    seller = make_user("seller@example.com")
    reputation = compute(seller)
    assert reputation.job_success_score is None
    assert reputation.level == SellerLevel.NEW


@pytest.mark.django_db
def test_the_level_ladder_needs_volume_score_and_tenure():
    ladder = SellerLevel.evaluate

    # Everything but time served.
    assert ladder(contracts=25, score=95, on_time=95, age_days=5) == SellerLevel.NEW
    # Time but no track record.
    assert ladder(contracts=1, score=None, on_time=100, age_days=900) == SellerLevel.NEW
    # The real thing.
    assert ladder(contracts=25, score=95, on_time=95, age_days=365) == SellerLevel.TOP_RATED
    assert ladder(contracts=12, score=86, on_time=90, age_days=120) == SellerLevel.LEVEL_TWO
    assert ladder(contracts=4, score=80, on_time=80, age_days=45) == SellerLevel.LEVEL_ONE


@pytest.mark.django_db
def test_reputation_is_exposed_publicly(category):
    seller = make_user("seller@example.com")
    SellerProfile.objects.update_or_create(
        user=seller,
        defaults={
            "level": SellerLevel.LEVEL_TWO,
            "job_success_score": 88,
            "contracts_completed": 11,
        },
    )

    response = sign_in(make_user("buyer@example.com")).get(
        f"/api/v1/sellers/{seller.handle}/reputation/"
    )
    assert response.status_code == 200
    assert response.data["level"] == SellerLevel.LEVEL_TWO
    assert response.data["job_success_score"] == 88


# --- Review integrity -------------------------------------------------------


@pytest.mark.django_db
def test_one_innocent_signal_never_suppresses_a_review():
    """Shared wifi is not fraud. Only a combination heavy enough to be
    implausible should touch anyone's score."""
    from contracts.integrity import FLAG_AT, SIGNAL_WEIGHTS

    assert SIGNAL_WEIGHTS["same_network"] < FLAG_AT
    assert SIGNAL_WEIGHTS["instant_perfect"] < FLAG_AT
    assert SIGNAL_WEIGHTS["trivial_value"] < FLAG_AT


@pytest.mark.django_db
def test_signals_accumulate_into_a_verdict():
    from contracts.integrity import FLAG_AT, SIGNAL_WEIGHTS, SUPPRESS_AT

    reciprocal = SIGNAL_WEIGHTS["reciprocal_pair"]
    throwaway = SIGNAL_WEIGHTS["throwaway_account"]
    # The classic ring: two accounts reviewing each other, both new.
    assert reciprocal + throwaway >= SUPPRESS_AT
    # A weaker pair only warrants a human look.
    assert FLAG_AT <= SIGNAL_WEIGHTS["same_network"] + SIGNAL_WEIGHTS["trivial_value"] < SUPPRESS_AT


@pytest.mark.django_db
def test_an_unchecked_review_is_distinguishable_from_a_clean_one():
    """A backlog in the checker must not read as a clean bill of health."""
    from contracts.models import Review

    assert Review.Integrity.UNCHECKED != Review.Integrity.CLEAN


# --- Work showcase ----------------------------------------------------------


@pytest.mark.django_db
def test_a_showcase_entry_needs_both_parties(category):
    from contracts.models import Contract

    seller = make_user("seller@example.com")
    client_user = make_user("client@example.com")

    with use_scope(GLOBAL_SCOPE):
        contract = Contract.objects.create(
            client=client_user,
            freelancer=seller,
            title="A finished piece of work",
            contract_type="fixed",
            total_amount=Decimal("25000"),
            status=Contract.Status.COMPLETED,
            visibility=Visibility.GLOBAL,
        )

    item = ShowcaseItem.draft_for(contract)
    assert item is not None
    assert item.published_at is None

    item.seller_approved = True
    item.save(update_fields=["seller_approved"])
    assert item.publish_if_ready() is False, "one side is not enough"

    item.client_approved = True
    item.save(update_fields=["client_approved"])
    assert item.publish_if_ready() is True

    listed = sign_in(make_user("browser@example.com")).get("/api/v1/showcase/").data
    assert listed["count"] == 1


@pytest.mark.django_db
def test_either_party_can_withdraw_a_showcase_entry(category):
    from contracts.models import Contract

    seller = make_user("seller@example.com")
    client_user = make_user("client@example.com")
    with use_scope(GLOBAL_SCOPE):
        contract = Contract.objects.create(
            client=client_user,
            freelancer=seller,
            title="Work to withdraw",
            contract_type="fixed",
            total_amount=Decimal("25000"),
            status=Contract.Status.COMPLETED,
            visibility=Visibility.GLOBAL,
        )

    item = ShowcaseItem.draft_for(contract)
    item.seller_approved = item.client_approved = True
    item.save()
    item.publish_if_ready()
    assert item.is_published

    item.withdraw(client_user)
    assert item.published_at is None
    assert item.client_approved is False


# --- Search analytics -------------------------------------------------------


@pytest.mark.django_db
def test_searches_are_logged_without_a_user(category):
    """Zero-result queries are the cheapest product feedback there is — and
    tying a search history to a person is a different dataset entirely."""
    seller = make_user("seller@example.com")
    make_gig(seller, "I will design a logo", category=category)

    sign_in(make_user("buyer@example.com")).get("/api/v1/search/gigs/?q=underwater+basket+weaving")

    entry = SearchLog.objects.filter(term="underwater basket weaving").first()
    assert entry is not None
    assert entry.result_count == 0
    assert not hasattr(entry, "user_id") or getattr(entry, "user_id", None) is None
