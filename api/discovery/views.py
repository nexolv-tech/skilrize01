"""
Search, showcase, and promotion endpoints.

The search views are thin on purpose: matching, ranking, and faceting all live
in `core.search`, so gigs and projects get identical behaviour rather than two
implementations that slowly disagree about what "relevance" means.
"""

from __future__ import annotations

from dataclasses import asdict

from django.db.models import F, Min, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core.pagination import StandardPagination
from core.scope import SurfaceKind, get_scope
from core.search import (
    apply_ranking,
    apply_text_search,
    facets_for,
    price_buckets,
)

from .models import Promotion, SearchLog, ShowcaseItem
from .serializers import (
    PromotionSerializer,
    PromotionWriteSerializer,
    SearchGigSerializer,
    SearchProjectSerializer,
    ShowcaseItemSerializer,
)


def _current_visibility() -> str:
    scope = get_scope()
    return "university" if scope and scope.kind is SurfaceKind.UNIVERSITY else "global"


def _facet_payload(facets: dict) -> dict:
    # `asdict`, not `vars`: Facet uses `slots=True` and so has no `__dict__`.
    return {name: [asdict(option) for option in options] for name, options in facets.items()}


@api_view(["GET"])
@permission_classes([AllowAny])
def search_gigs(request):
    """
    GET /search/gigs/?q=&category=&price=&level=&rating=&delivery=&sort=

    Faceted search over the service catalogue on the active surface.
    """
    from gigs.models import Gig

    params = request.query_params
    term = params.get("q", "").strip()

    # Scope is applied by the manager before anything else touches the set.
    base = (
        Gig.objects.filter(status=Gig.Status.ACTIVE)
        .select_related("seller", "seller__seller_profile", "category")
        .prefetch_related("packages", "gallery")
    )

    matched = apply_text_search(base, term)

    # Facet counts come from the matched set *before* the user's own facet
    # selections narrow it — otherwise every unpicked option reads as zero the
    # moment somebody picks one, and the filters become unusable.
    facets = facets_for(
        matched, {"category": "category__name", "level": "seller__seller_profile__level"}
    )
    facets["price"] = price_buckets(
        matched.annotate(price_floor=F("packages__price")), "price_floor"
    )

    filtered = matched
    if category := params.get("category"):
        filtered = filtered.filter(Q(category__slug=category) | Q(category__name=category))
    if level := params.get("level"):
        filtered = filtered.filter(seller__seller_profile__level=level)
    if rating := params.get("rating"):
        filtered = filtered.filter(rating_average__gte=rating)
    if delivery := params.get("delivery"):
        filtered = filtered.filter(packages__delivery_days__lte=delivery)
    if band := params.get("price"):
        low, _, high = band.partition("-")
        if low:
            filtered = filtered.filter(packages__price__gte=low)
        if high:
            filtered = filtered.filter(packages__price__lt=high)

    filtered = filtered.distinct()

    ranked = apply_ranking(
        filtered,
        reputation_path="seller__seller_profile__job_success_score",
        published_path="published_at",
        promoted=True,
    )

    # Explicit sorts replace the ranking order entirely. Someone who asked for
    # "newest" means newest, not "newest, nudged by whoever paid".
    sort = params.get("sort")
    if sort == "newest":
        ranked = ranked.order_by("-published_at", "-id")
    elif sort == "rating":
        ranked = ranked.order_by(F("rating_average").desc(nulls_last=True), "-id")
    elif sort == "price":
        # Not `.order_by("packages__price", ...)`. A gig carries several
        # packages, so ordering by the raw related field joins `packages` a
        # second time — and because Postgres requires an ORDER BY column used
        # with SELECT DISTINCT to appear in the select list, that package
        # price rides along in the row tuple. A gig with three packages then
        # produces three distinguishable rows, all with the same id, and
        # `.distinct()` has nothing left to collapse: the API returned the
        # same gig two or three times, once per package, which is what
        # actually showed up as a duplicate React key on the results page.
        #
        # `Min()` sidesteps the join-then-order-by shape entirely: it is an
        # aggregate, so Django groups by every other selected column instead
        # of adding the related field to the row, and one row per gig comes
        # back regardless of how many packages it has.
        ranked = ranked.annotate(sort_price=Min("packages__price")).order_by("sort_price", "-id")

    paginator = StandardPagination()
    page = paginator.paginate_queryset(ranked, request)
    payload = paginator.get_paginated_response(
        SearchGigSerializer(page, many=True, context={"request": request}).data
    )
    payload.data["facets"] = _facet_payload(facets)
    payload.data["query"] = term

    SearchLog.record(term, "gigs", payload.data.get("count", 0), _current_visibility())
    _count_impressions(page)
    return payload


def _count_impressions(page) -> None:
    """Record that these listings were seen.

    Impressions are what make a promotion's click-through rate meaningful, and
    a seller paying for placement is owed an honest denominator.
    """
    from gigs.models import Gig

    ids = [gig.pk for gig in page or []]
    if not ids:
        return
    Gig.all_objects.filter(pk__in=ids).update(impressions=F("impressions") + 1)
    Promotion.objects.filter(gig_id__in=ids, status=Promotion.Status.ACTIVE).update(
        impressions=F("impressions") + 1
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def search_projects(request):
    """Faceted search over open briefs."""
    from marketplace.models import Project

    params = request.query_params
    term = params.get("q", "").strip()

    base = (
        Project.objects.filter(status=Project.Status.OPEN, listing=Project.Listing.PUBLIC)
        .select_related("client", "category")
        .prefetch_related("skills")
    )

    matched = apply_text_search(base, term)
    facets = facets_for(
        matched,
        {
            "category": "category__name",
            "type": "project_type",
            "experience": "experience_level",
        },
    )
    facets["budget"] = price_buckets(matched.annotate(price_floor=F("budget_max")), "price_floor")

    filtered = matched
    if category := params.get("category"):
        filtered = filtered.filter(Q(category__slug=category) | Q(category__name=category))
    if project_type := params.get("type"):
        filtered = filtered.filter(project_type=project_type)
    if experience := params.get("experience"):
        filtered = filtered.filter(experience_level=experience)
    if band := params.get("budget"):
        low, _, high = band.partition("-")
        if low:
            filtered = filtered.filter(budget_max__gte=low)
        if high:
            filtered = filtered.filter(budget_max__lt=high)

    # Briefs carry no promotion: a client paying to have their own job listed
    # above other clients' jobs would sell the freelancer's attention to the
    # highest bidder, which is the wrong side of this marketplace to auction.
    ranked = apply_ranking(
        filtered.distinct(),
        reputation_path="client__buyer_profile__hire_rate",
        published_path="published_at",
        promoted=False,
    )
    if params.get("sort") == "newest":
        ranked = ranked.order_by("-published_at", "-id")

    paginator = StandardPagination()
    page = paginator.paginate_queryset(ranked, request)
    payload = paginator.get_paginated_response(
        SearchProjectSerializer(page, many=True, context={"request": request}).data
    )
    payload.data["facets"] = _facet_payload(facets)
    payload.data["query"] = term

    SearchLog.record(term, "projects", payload.data.get("count", 0), _current_visibility())
    return payload


# --- Work showcase ----------------------------------------------------------


@api_view(["GET"])
@permission_classes([AllowAny])
def showcase(request):
    """The global work-showcase feed."""
    queryset = ShowcaseItem.objects.filter(published_at__isnull=False).select_related(
        "seller", "seller__seller_profile", "category"
    )
    if category := request.query_params.get("category"):
        queryset = queryset.filter(Q(category__slug=category) | Q(category__name=category))
    if handle := request.query_params.get("seller"):
        queryset = queryset.filter(seller__handle=handle)

    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        ShowcaseItemSerializer(page, many=True, context={"request": request}).data
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def showcase_consent(request, contract_id):
    """Read or give your side's consent to publish a completed contract."""
    from contracts.models import Contract

    contract = get_object_or_404(
        Contract.objects.unscoped().select_related("client", "freelancer"), pk=contract_id
    )
    if request.user.pk not in (contract.client_id, contract.freelancer_id):
        return Response(
            {"detail": "Not your contract.", "code": "not_a_party"},
            status=status.HTTP_403_FORBIDDEN,
        )
    if contract.status != Contract.Status.COMPLETED:
        return Response(
            {"detail": "Only completed work can be showcased.", "code": "not_completed"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    item = ShowcaseItem.draft_for(contract)
    if item is None:
        return Response(
            {"detail": "Nothing to showcase.", "code": "unavailable"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if request.method == "POST":
        consent = bool(request.data.get("approved", True))
        is_seller = request.user.pk == contract.freelancer_id

        if is_seller:
            item.seller_approved = consent
            if "title" in request.data:
                item.title = str(request.data["title"])[:200]
            if "summary" in request.data:
                item.summary = str(request.data["summary"])[:2000]
        else:
            item.client_approved = consent

        item.save(
            update_fields=[
                "seller_approved",
                "client_approved",
                "title",
                "summary",
                "updated_at",
            ]
        )
        if consent:
            item.publish_if_ready()
        else:
            item.withdraw(request.user)

    return Response(ShowcaseItemSerializer(item, context={"request": request}).data)


# --- Promotions -------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def promotions(request):
    """List your promotions, or start one."""
    if request.method == "GET":
        rows = Promotion.objects.filter(seller=request.user).select_related("gig")
        return Response(PromotionSerializer(rows, many=True).data)

    serializer = PromotionWriteSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)

    promotion = serializer.save(
        seller=request.user,
        # Live immediately when it starts now, rather than waiting for the
        # sweeper — a seller who just paid should see it running.
        status=Promotion.Status.ACTIVE
        if serializer.validated_data.get("starts_at", timezone.now()) <= timezone.now()
        else Promotion.Status.SCHEDULED,
    )
    promotion.sync_gig_flag()
    return Response(PromotionSerializer(promotion).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pause_promotion(request, pk):
    promotion = get_object_or_404(Promotion, pk=pk, seller=request.user)
    promotion.status = (
        Promotion.Status.ACTIVE
        if promotion.status == Promotion.Status.PAUSED
        else Promotion.Status.PAUSED
    )
    promotion.save(update_fields=["status", "updated_at"])
    promotion.sync_gig_flag()
    return Response(PromotionSerializer(promotion).data)


@api_view(["POST"])
@permission_classes([AllowAny])
def record_click(request, gig_id):
    """A listing was opened from a result page.

    Separate from the impression counter so click-through rate means something.
    Unauthenticated on purpose — most clicks on a catalogue come from people
    who have not signed in, and only counting members would understate every
    promotion a seller paid for.
    """
    from gigs.models import Gig

    Gig.all_objects.filter(pk=gig_id).update(clicks=F("clicks") + 1)
    Promotion.objects.filter(gig_id=gig_id, status=Promotion.Status.ACTIVE).update(
        clicks=F("clicks") + 1
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


# --- Reputation -------------------------------------------------------------


@api_view(["GET"])
@permission_classes([AllowAny])
def seller_reputation(request, handle):
    """The public reputation panel for one seller."""
    from accounts.models import User

    user = get_object_or_404(
        User.objects.select_related("seller_profile"), handle=handle, is_active=True
    )
    profile = getattr(user, "seller_profile", None)
    if profile is None:
        return Response({"detail": "Not a seller.", "code": "not_found"}, status=404)

    from contracts.models import Review

    published = (
        Review.objects.filter(subject=user, role=Review.Role.CLIENT, published_at__isnull=False)
        .exclude(integrity_status=Review.Integrity.SUPPRESSED)
        .count()
    )

    return Response(
        {
            "handle": user.handle,
            "display_name": user.display_name,
            "level": profile.level,
            "job_success_score": profile.job_success_score,
            "contracts_completed": profile.contracts_completed,
            "on_time_delivery_rate": profile.on_time_delivery_rate,
            "repeat_client_rate": profile.repeat_client_rate,
            "average_rating": profile.average_rating,
            "review_count": published,
            "updated_at": profile.reputation_updated_at,
        }
    )
