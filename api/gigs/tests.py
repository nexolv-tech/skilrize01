"""
Tests for the gig track.

The rules that matter most here are the ones that protect whichever side is
exposed at each step: the seller from a buyer who pays and vanishes (the
requirements gate), and the buyer from a seller who under-delivers (the
revision entitlement and the acceptance window).
"""

from __future__ import annotations

import pytest

from contracts.models import Contract, Milestone
from core.scope import GLOBAL_SCOPE, Scope, SurfaceKind, Visibility, use_scope
from gigs.models import Gig, Order, Package
from marketplace.tests import make_user, sign_in

GIG_BODY = {
    "title": "design a complete brand identity",
    "description": "Logo, palette, typography, and a one-page usage guide.",
    "tags": ["logo", "branding"],
    "requirements": [
        {"key": "brand_name", "label": "What is the brand called?", "required": True},
        {"key": "notes", "label": "Anything else?", "required": False},
    ],
    "packages": [
        {
            "tier": "basic",
            "name": "Logo only",
            "price": "8000",
            "delivery_days": 3,
            "revisions": 1,
            "features": ["1 concept"],
        },
        {
            "tier": "standard",
            "name": "Logo + palette",
            "price": "15000",
            "delivery_days": 5,
            "revisions": 2,
            "features": ["3 concepts", "Colour system"],
        },
        {
            "tier": "premium",
            "name": "Full identity",
            "price": "30000",
            "delivery_days": 8,
            "revisions": 4,
            "features": ["5 concepts", "Usage guide"],
        },
    ],
    "extras": [{"title": "Source files", "price": "3000", "extra_days": 1}],
}


@pytest.fixture
def seller(db):
    return make_user("seller@example.com")


@pytest.fixture
def buyer(db):
    return make_user("buyer@example.com")


def picture(name: str = "work.png"):
    """A real (tiny) PNG, since uploads are sniffed and re-encoded."""
    import io as _io

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buffer = _io.BytesIO()
    Image.new("RGB", (32, 20), (242, 161, 15)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def publish_gig(api, gig_id: int):
    """Publish the way a seller must: with a picture of the work first."""
    added = api.post(f"/api/v1/gigs/{gig_id}/gallery/", {"files": [picture()]}, format="multipart")
    assert added.status_code == 201, added.data
    return api.post(f"/api/v1/gigs/{gig_id}/publish/")


@pytest.fixture
def gig(seller):
    api = sign_in(seller)
    created = api.post("/api/v1/gigs/", GIG_BODY, format="json")
    assert created.status_code == 201, created.data
    published = publish_gig(api, created.data["id"])
    assert published.status_code == 200, published.data
    return Gig.objects.unscoped().get(pk=created.data["id"])


# --- Publishing ------------------------------------------------------------


@pytest.mark.django_db
def test_creating_a_gig_builds_its_tiers(gig):
    assert gig.status == Gig.Status.ACTIVE
    assert gig.packages.count() == 3
    assert gig.extras.count() == 1
    assert gig.starting_price == 8000


@pytest.mark.django_db
def test_the_title_is_normalised_to_the_house_format(gig):
    """Titles stay scannable and comparable across the catalogue."""
    assert gig.title.startswith("I will ")
    assert gig.title == "I will design a complete brand identity"


@pytest.mark.django_db
def test_tiers_must_increase_in_price(seller):
    body = {
        **GIG_BODY,
        "packages": [
            {"tier": "basic", "name": "A", "price": "9000", "delivery_days": 3, "revisions": 1},
            {"tier": "standard", "name": "B", "price": "5000", "delivery_days": 5, "revisions": 2},
        ],
    }
    response = sign_in(seller).post("/api/v1/gigs/", body, format="json")
    assert response.status_code == 400
    assert "packages" in response.data


@pytest.mark.django_db
def test_a_gig_needs_a_basic_tier(seller):
    body = {
        **GIG_BODY,
        "packages": [
            {"tier": "premium", "name": "Only", "price": "9000", "delivery_days": 3, "revisions": 1}
        ],
    }
    response = sign_in(seller).post("/api/v1/gigs/", body, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_tags_are_capped(seller):
    body = {**GIG_BODY, "tags": ["a", "b", "c", "d", "e", "f", "g"]}
    response = sign_in(seller).post("/api/v1/gigs/", body, format="json")
    assert response.status_code == 400
    assert "tags" in response.data


@pytest.mark.django_db
def test_publishing_requires_a_complete_profile(db):
    incomplete = make_user("nope@example.com", transactable=False)
    response = sign_in(incomplete).post("/api/v1/gigs/", GIG_BODY, format="json")
    assert response.status_code == 403
    assert response.data["code"] == "profile_incomplete"


@pytest.mark.django_db
def test_vacation_mode_toggles_without_deleting(gig, seller):
    api = sign_in(seller)
    assert api.post(f"/api/v1/gigs/{gig.pk}/pause/").data["status"] == "paused"

    # A paused gig leaves the catalogue but the link still resolves.
    assert sign_in(make_user("browser@example.com")).get("/api/v1/gigs/").data["count"] == 0
    assert api.post(f"/api/v1/gigs/{gig.pk}/pause/").data["status"] == "active"


@pytest.mark.django_db
def test_a_campus_gig_never_appears_in_the_global_catalogue(seller, buyer):
    from accounts.models import University

    cui = University.objects.create(name="COMSATS", short_code="CUI")
    with use_scope(Scope(SurfaceKind.UNIVERSITY, university_id=cui.pk)):
        Gig.objects.create(
            seller=seller,
            title="I will design campus posters",
            description="For CUI societies.",
            status=Gig.Status.ACTIVE,
            visibility=Visibility.UNIVERSITY,
            university=cui,
        )

    titles = [row["title"] for row in sign_in(buyer).get("/api/v1/gigs/").data["results"]]
    assert "I will design campus posters" not in titles


# --- Ordering --------------------------------------------------------------


def _place(gig, buyer, *, extras=None):
    """Place an order without paying: it waits for Swich (D55)."""
    package = gig.packages.get(tier=Package.Tier.STANDARD)
    body = {"package": package.pk}
    if extras:
        body["extras"] = extras
    return sign_in(buyer).post(f"/api/v1/gigs/{gig.pk}/order/", body, format="json")


def _order(gig, buyer, *, extras=None):
    """Buy a package: place the order, then pay for it the way Swich
    confirms a payment, through the checksum-verified callback. Returns the
    placing response with `data` swapped for the paid order, so callers read
    `data["id"]` and the order's state after payment."""
    from payments.testing import swich_pays

    response = _place(gig, buyer, extras=extras)
    if response.status_code != 201:
        return response
    assert swich_pays(response).data["status"] == "paid"
    response.data = sign_in(buyer).get(f"/api/v1/orders/{response.data['order']['id']}/").data
    return response


@pytest.mark.django_db
def test_buying_requires_an_enrolled_second_factor(gig):
    """Money movement asks for 2FA; browsing and bidding do not.

    A fully verified buyer who never enrolled can still look at the gig — they
    just cannot pay for it until they do.
    """
    unenrolled = make_user("no-authenticator@example.com", two_factor=False)
    package = gig.packages.get(tier=Package.Tier.STANDARD)
    client = sign_in(unenrolled)

    # Reading the catalogue is untouched.
    assert client.get(f"/api/v1/gigs/{gig.pk}/").status_code == 200

    response = client.post(f"/api/v1/gigs/{gig.pk}/order/", {"package": package.pk}, format="json")
    assert response.status_code == 403
    assert response.data["code"] == "two_factor_required"
    assert not Order.objects.filter(buyer=unenrolled).exists()


@pytest.mark.django_db
def test_ordering_creates_a_funded_contract(gig, buyer):
    response = _order(gig, buyer)

    assert response.status_code == 201
    order = Order.objects.get(pk=response.data["id"])
    assert order.status == Order.Status.PENDING_REQUIREMENTS
    assert order.price == 15000

    # A gig purchase is paid up front, so escrow holds the money immediately.
    contract = order.contract
    assert contract.status == Contract.Status.ACTIVE
    assert contract.milestones.first().status == Milestone.Status.FUNDED
    assert contract.funded_amount == 15000


@pytest.mark.django_db
def test_extras_are_priced_by_the_server(gig, buyer):
    extra = gig.extras.first()
    response = _order(gig, buyer, extras=[extra.pk])

    order = Order.objects.get(pk=response.data["id"])
    assert order.price == 18000  # 15000 + 3000
    # The extra also pushes the deadline out.
    assert order.delivery_days == 6


@pytest.mark.django_db
def test_a_seller_cannot_order_their_own_gig(gig, seller):
    response = _order(gig, seller)
    assert response.status_code == 400
    assert "your own gig" in response.data["detail"]


@pytest.mark.django_db
def test_a_price_sent_by_the_buyer_is_ignored(gig, buyer):
    """The server prices from what it finds, never from the request body."""
    package = gig.packages.get(tier=Package.Tier.BASIC)
    response = sign_in(buyer).post(
        f"/api/v1/gigs/{gig.pk}/order/", {"package": package.pk, "price": "1"}, format="json"
    )
    assert Order.objects.get(pk=response.data["order"]["id"]).price == 8000


@pytest.mark.django_db
def test_editing_the_gig_does_not_change_an_existing_order(gig, buyer, seller):
    order_id = _order(gig, buyer).data["id"]

    updated = dict(GIG_BODY)
    updated["packages"] = [
        {"tier": "basic", "name": "A", "price": "99000", "delivery_days": 1, "revisions": 1},
    ]
    sign_in(seller).patch(f"/api/v1/gigs/{gig.pk}/", updated, format="json")

    order = Order.objects.get(pk=order_id)
    assert order.price == 15000
    assert order.package_snapshot["price"] == "15000.00"


# --- The requirements gate -------------------------------------------------


@pytest.mark.django_db
def test_the_clock_does_not_start_until_requirements_are_submitted(gig, buyer):
    order = Order.objects.get(pk=_order(gig, buyer).data["id"])

    assert order.status == Order.Status.PENDING_REQUIREMENTS
    assert order.due_at is None
    assert "What is the brand called?" in order.missing_requirements


@pytest.mark.django_db
def test_partial_requirements_are_refused(gig, buyer):
    order_id = _order(gig, buyer).data["id"]

    response = sign_in(buyer).post(
        f"/api/v1/orders/{order_id}/requirements/",
        {"answers": {"notes": "just the optional one"}},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "missing_requirements"


@pytest.mark.django_db
def test_submitting_requirements_starts_the_clock(gig, buyer):
    order_id = _order(gig, buyer).data["id"]

    response = sign_in(buyer).post(
        f"/api/v1/orders/{order_id}/requirements/",
        {"answers": {"brand_name": "Northline", "notes": "Prefer serif."}},
        format="json",
    )

    assert response.status_code == 200
    order = Order.objects.get(pk=order_id)
    assert order.status == Order.Status.ACTIVE
    assert order.due_at is not None


@pytest.mark.django_db
def test_a_seller_cannot_submit_requirements_for_the_buyer(gig, buyer, seller):
    order_id = _order(gig, buyer).data["id"]
    response = sign_in(seller).post(
        f"/api/v1/orders/{order_id}/requirements/", {"answers": {"brand_name": "X"}}, format="json"
    )
    assert response.status_code == 403


# --- Delivery, revisions, acceptance ---------------------------------------


def _active_order(gig, buyer):
    order_id = _order(gig, buyer).data["id"]
    sign_in(buyer).post(
        f"/api/v1/orders/{order_id}/requirements/",
        {"answers": {"brand_name": "Northline"}},
        format="json",
    )
    return Order.objects.get(pk=order_id)


@pytest.mark.django_db
def test_the_full_delivery_and_acceptance_loop(gig, buyer, seller):
    order = _active_order(gig, buyer)

    delivered = sign_in(seller).post(
        f"/api/v1/orders/{order.pk}/deliver/", {"note": "Three concepts attached."}, format="json"
    )
    assert delivered.status_code == 200
    assert delivered.data["status"] == "delivered"
    assert delivered.data["accept_by"] is not None

    accepted = sign_in(buyer).post(f"/api/v1/orders/{order.pk}/accept/")
    assert accepted.status_code == 200

    order.refresh_from_db()
    assert order.status == Order.Status.COMPLETED
    assert order.contract.status == Contract.Status.COMPLETED
    assert order.contract.released_amount == 15000

    # Accepting a gig order releases through its own path, separate from
    # `contracts.release_milestone` — it must still create the seller's
    # `Payout` with the commission split (Phase 3, D42).
    from payments.models import Payout

    payout = Payout.objects.get(milestone=order.contract.milestones.first())
    assert payout.freelancer_id == seller.pk
    assert payout.status == Payout.Status.PENDING
    assert payout.net_amount == payout.gross_amount - payout.commission_amount


@pytest.mark.django_db
def test_a_buyer_cannot_deliver_and_a_seller_cannot_accept(gig, buyer, seller):
    order = _active_order(gig, buyer)

    assert sign_in(buyer).post(f"/api/v1/orders/{order.pk}/deliver/").status_code == 403

    sign_in(seller).post(f"/api/v1/orders/{order.pk}/deliver/", {"note": "done"}, format="json")
    assert sign_in(seller).post(f"/api/v1/orders/{order.pk}/accept/").status_code == 403


@pytest.mark.django_db
def test_revisions_are_limited_to_the_package_entitlement(gig, buyer, seller):
    """Standard includes two revisions; the third must be refused."""
    order = _active_order(gig, buyer)
    buyer_api, seller_api = sign_in(buyer), sign_in(seller)

    for attempt in range(2):
        seller_api.post(f"/api/v1/orders/{order.pk}/deliver/", {"note": "v"}, format="json")
        response = buyer_api.post(
            f"/api/v1/orders/{order.pk}/request-revision/",
            {"note": f"Please adjust the spacing ({attempt})."},
            format="json",
        )
        assert response.status_code == 200

    seller_api.post(f"/api/v1/orders/{order.pk}/deliver/", {"note": "v3"}, format="json")
    refused = buyer_api.post(
        f"/api/v1/orders/{order.pk}/request-revision/", {"note": "One more."}, format="json"
    )
    assert refused.status_code == 400
    assert refused.data["code"] == "no_revisions_left"


@pytest.mark.django_db
def test_a_revision_needs_a_reason(gig, buyer, seller):
    order = _active_order(gig, buyer)
    sign_in(seller).post(f"/api/v1/orders/{order.pk}/deliver/", {"note": "v1"}, format="json")

    response = sign_in(buyer).post(
        f"/api/v1/orders/{order.pk}/request-revision/", {"note": "   "}, format="json"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_a_delivered_order_cannot_be_unilaterally_cancelled(gig, buyer, seller):
    order = _active_order(gig, buyer)
    sign_in(seller).post(f"/api/v1/orders/{order.pk}/deliver/", {"note": "v1"}, format="json")

    response = sign_in(buyer).post(f"/api/v1/orders/{order.pk}/cancel/")
    assert response.status_code == 400
    assert response.data["code"] == "already_delivered"


@pytest.mark.django_db
def test_a_stranger_cannot_see_someone_elses_order(gig, buyer):
    order_id = _order(gig, buyer).data["id"]
    stranger = make_user("nosy@example.com")

    api = sign_in(stranger)
    assert api.get(f"/api/v1/orders/{order_id}/").status_code == 404
    assert api.get("/api/v1/orders/").data["count"] == 0


# --- Reviews reach across both tracks --------------------------------------


@pytest.mark.django_db
def test_a_gig_order_is_reviewed_through_the_same_contract(gig, buyer, seller):
    """One reputation across both tracks means one review system, not two."""
    order = _active_order(gig, buyer)
    sign_in(seller).post(f"/api/v1/orders/{order.pk}/deliver/", {"note": "done"}, format="json")
    sign_in(buyer).post(f"/api/v1/orders/{order.pk}/accept/")
    order.refresh_from_db()

    first = sign_in(buyer).post(
        f"/api/v1/contracts/{order.contract_id}/review/",
        {
            "overall": 5,
            "communication": 5,
            "quality": 5,
            "deadline": 5,
            "value": 5,
            "comment": "Exactly the brief.",
        },
        format="json",
    )
    assert first.status_code == 201
    assert first.data["published"] is False

    second = sign_in(seller).post(
        f"/api/v1/contracts/{order.contract_id}/review/",
        {
            "overall": 5,
            "communication": 5,
            "clarity": 4,
            "payment_promptness": 5,
            "comment": "Clear requirements.",
        },
        format="json",
    )
    assert second.data["published"] is True


# --- Buyer requests --------------------------------------------------------


@pytest.mark.django_db
def test_a_buyer_request_gives_new_sellers_a_route_in(buyer, seller):
    with use_scope(GLOBAL_SCOPE):
        created = sign_in(buyer).post(
            "/api/v1/buyer-requests/",
            {
                "description": "Need a logo for a coffee cart, quickly.",
                "budget": "5000",
                "delivery_days": 3,
            },
            format="json",
        )
    assert created.status_code == 201

    listed = sign_in(seller).get("/api/v1/buyer-requests/")
    assert listed.data["count"] == 1

    offer = sign_in(seller).post(
        "/api/v1/custom-offers/",
        {
            "buyer": buyer.pk,
            "description": "I can do this in two days.",
            "price": "4500",
            "delivery_days": 2,
            "revisions": 1,
        },
        format="json",
    )
    assert offer.status_code == 201
    assert offer.data["status"] == "sent"


@pytest.mark.django_db
def test_only_the_recipient_can_answer_a_custom_offer(buyer, seller):
    offer_id = (
        sign_in(seller)
        .post(
            "/api/v1/custom-offers/",
            {"buyer": buyer.pk, "description": "Offer", "price": "1000", "delivery_days": 2},
            format="json",
        )
        .data["id"]
    )

    assert (
        sign_in(seller)
        .post(f"/api/v1/custom-offers/{offer_id}/respond/", {"accept": True}, format="json")
        .status_code
        == 403
    )
    assert (
        sign_in(buyer)
        .post(f"/api/v1/custom-offers/{offer_id}/respond/", {"accept": True}, format="json")
        .status_code
        == 200
    )


# --- Pictures and video --------------------------------------------------------


def _draft(seller):
    api = sign_in(seller)
    created = api.post("/api/v1/gigs/", GIG_BODY, format="json")
    return api, created.data["id"]


@pytest.mark.django_db
def test_a_service_cannot_go_live_without_a_picture(seller):
    api, gig_id = _draft(seller)

    refused = api.post(f"/api/v1/gigs/{gig_id}/publish/")
    assert refused.status_code == 400
    assert refused.data["code"] == "publish_blocked"
    assert "picture" in refused.data["detail"]

    assert publish_gig(api, gig_id).status_code == 200
    assert Gig.objects.unscoped().get(pk=gig_id).status == Gig.Status.ACTIVE


@pytest.mark.django_db
def test_the_first_picture_is_the_cover_and_three_is_the_limit(seller):
    api, gig_id = _draft(seller)
    added = api.post(
        f"/api/v1/gigs/{gig_id}/gallery/",
        {"files": [picture("a.png"), picture("b.png")]},
        format="multipart",
    )
    assert added.status_code == 201
    first = added.data["images"][0]["id"]
    assert [image["status"] for image in added.data["images"]] == ["clean", "clean"]

    too_many = api.post(
        f"/api/v1/gigs/{gig_id}/gallery/",
        {"files": [picture("c.png"), picture("d.png")]},
        format="multipart",
    )
    assert too_many.status_code == 400
    assert too_many.data["code"] == "too_many_images"

    listed = api.get("/api/v1/gigs/?mine=true").data["results"][0]
    assert listed["cover_url"] and listed["status"] == "draft"
    detail = api.get(f"/api/v1/gigs/{gig_id}/").data
    assert detail["images"][0]["id"] == first


@pytest.mark.django_db
def test_a_live_service_keeps_at_least_one_picture(gig, seller):
    api = sign_in(seller)
    only = api.get(f"/api/v1/gigs/{gig.pk}/").data["images"][0]["id"]

    refused = api.delete(f"/api/v1/gigs/{gig.pk}/gallery/{only}/")
    assert refused.status_code == 400
    assert refused.data["code"] == "last_image"

    api.post(f"/api/v1/gigs/{gig.pk}/gallery/", {"files": [picture()]}, format="multipart")
    removed = api.delete(f"/api/v1/gigs/{gig.pk}/gallery/{only}/")
    assert removed.status_code == 200
    assert only not in [image["id"] for image in removed.data["images"]]


@pytest.mark.django_db
def test_pictures_must_be_images_and_only_the_owner_adds_them(gig, buyer, seller):
    from django.core.files.uploadedfile import SimpleUploadedFile

    pdf = SimpleUploadedFile("brief.pdf", b"%PDF-1.7 ...", content_type="application/pdf")
    rejected = sign_in(seller).post(
        f"/api/v1/gigs/{gig.pk}/gallery/", {"files": [pdf]}, format="multipart"
    )
    assert rejected.status_code == 400
    assert rejected.data["code"] == "invalid_file"

    stranger = sign_in(buyer).post(
        f"/api/v1/gigs/{gig.pk}/gallery/", {"files": [picture()]}, format="multipart"
    )
    assert stranger.status_code == 403


@pytest.mark.django_db
def test_a_service_takes_one_optional_mp4_video(gig, seller):
    from django.core.files.uploadedfile import SimpleUploadedFile

    api = sign_in(seller)
    mp4 = SimpleUploadedFile(
        "promo.mp4", b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64, content_type="video/mp4"
    )
    added = api.post(f"/api/v1/gigs/{gig.pk}/video/", {"file": mp4}, format="multipart")
    assert added.status_code == 201, added.data
    assert added.data["video_url"]

    not_video = api.post(f"/api/v1/gigs/{gig.pk}/video/", {"file": picture()}, format="multipart")
    assert not_video.status_code == 400

    removed = api.delete(f"/api/v1/gigs/{gig.pk}/video/")
    assert removed.status_code == 200
    assert removed.data["video_url"] is None


@pytest.mark.django_db
def test_video_is_served_in_byte_ranges(gig, seller):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient

    payload = b"\x00\x00\x00\x18ftypmp42" + bytes(range(200))
    api = sign_in(seller)
    added = api.post(
        f"/api/v1/gigs/{gig.pk}/video/",
        {"file": SimpleUploadedFile("promo.mp4", payload, content_type="video/mp4")},
        format="multipart",
    )
    url = added.data["video_url"]

    partial = APIClient().get(url, HTTP_RANGE="bytes=0-9")
    assert partial.status_code == 206
    assert partial["Content-Range"] == f"bytes 0-9/{len(payload)}"
    assert partial.content == payload[:10]

    whole = APIClient().get(url)
    assert whole.status_code == 200
    assert whole["Accept-Ranges"] == "bytes"
