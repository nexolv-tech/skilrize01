"""
Tests for the professional layer.

The rules worth guarding are the ones that cost money or leak commercially
sensitive data: an entitlement that resolves the wrong way, a CRM query that
can reach another user's pipeline, two live subscriptions on one account, and a
seat count that can be grown past what was paid for.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from marketplace.models import Proposal
from marketplace.tests import make_user, sign_in
from professional.entitlements import for_user, seed_default_plans
from professional.models import (
    Agency,
    AgencyMember,
    Contact,
    Deal,
    Plan,
    RetainerPlan,
    RetainerSubscription,
    Subscription,
    Task,
)


@pytest.fixture
def tiers(db):
    return {plan.tier: plan for plan in seed_default_plans()}


def subscribe(user, plan, *, days=30) -> Subscription:
    return Subscription.objects.create(
        user=user,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        current_period_end=timezone.now() + timedelta(days=days),
    )


# --- Entitlements -----------------------------------------------------------


@pytest.mark.django_db
def test_no_subscription_resolves_to_free_not_unlimited(tiers):
    """The failure mode of a bug here must be "charged for what they'd get
    anyway", never "everyone got everything"."""
    rights = for_user(make_user("nobody@example.com"))
    assert rights.tier == Plan.Tier.FREE
    assert rights.can_create_agency is False
    assert rights.can_sell_retainers is False
    assert rights.proposal_quota == 30


@pytest.mark.django_db
def test_an_expired_subscription_falls_back_to_free(tiers):
    user = make_user("lapsed@example.com")
    Subscription.objects.create(
        user=user,
        plan=tiers[Plan.Tier.ELITE],
        status=Subscription.Status.ACTIVE,
        current_period_end=timezone.now() - timedelta(days=1),
    )
    assert for_user(user).tier == Plan.Tier.FREE


@pytest.mark.django_db
def test_an_anonymous_caller_resolves_to_free(tiers):
    """The pricing page renders for logged-out visitors; raising would mean it
    needs a session."""
    from django.contrib.auth.models import AnonymousUser

    assert for_user(AnonymousUser()).tier == Plan.Tier.FREE
    assert for_user(None).tier == Plan.Tier.FREE


@pytest.mark.django_db
def test_a_paid_plan_is_never_a_downgrade_for_a_student(tiers):
    """A student's free allowance beats Pro's number, so the higher wins."""
    from accounts.models import University, VerificationStatus

    uni = University.objects.create(name="COMSATS", short_code="CUI")
    student = make_user("student@example.com")
    student.university = uni
    student.student_verification_status = VerificationStatus.VERIFIED
    student.save()

    free_quota = for_user(student).proposal_quota
    assert free_quota == Proposal.FREE_PLAN_STUDENT_QUOTA

    subscribe(student, tiers[Plan.Tier.PRO])
    assert for_user(student).proposal_quota >= free_quota


@pytest.mark.django_db
def test_the_proposal_quota_follows_the_plan(tiers):
    seller = make_user("seller@example.com")
    assert Proposal.quota_for(seller) == 30

    subscribe(seller, tiers[Plan.Tier.PRO])
    assert Proposal.quota_for(seller) == 90

    Subscription.objects.filter(user=seller).delete()
    subscribe(seller, tiers[Plan.Tier.ELITE])
    assert Proposal.quota_for(seller) == Plan.UNLIMITED
    # Unlimited must never surface as a negative "slots remaining".
    assert Proposal.remaining_quota(seller) > 0


# --- Subscriptions ----------------------------------------------------------


@pytest.mark.django_db
def test_only_one_subscription_can_be_live(tiers):
    """Two overlapping subscriptions silently double someone's entitlements."""
    from django.db.utils import IntegrityError

    user = make_user("double@example.com")
    subscribe(user, tiers[Plan.Tier.PRO])

    with pytest.raises(IntegrityError):
        subscribe(user, tiers[Plan.Tier.ELITE])


@pytest.mark.django_db
def test_switching_tiers_replaces_rather_than_stacks(tiers):
    user = make_user("switcher@example.com")
    client = sign_in(user)

    client.post("/api/v1/subscription/subscribe/", {"tier": "pro"}, format="json")
    client.post("/api/v1/subscription/subscribe/", {"tier": "elite"}, format="json")

    live = Subscription.objects.filter(user=user, status__in=Subscription.LIVE_STATUSES)
    assert live.count() == 1
    assert live.first().plan.tier == Plan.Tier.ELITE


@pytest.mark.django_db
def test_cancelling_keeps_the_period_the_user_paid_for(tiers):
    user = make_user("canceller@example.com")
    client = sign_in(user)
    client.post("/api/v1/subscription/subscribe/", {"tier": "pro"}, format="json")

    response = client.post("/api/v1/subscription/cancel/", {}, format="json")
    assert response.status_code == 200
    assert response.data["cancel_at_period_end"] is True
    # Still Pro until the period ends.
    assert for_user(user).tier == Plan.Tier.PRO


@pytest.mark.django_db
def test_the_pricing_table_is_public(client, tiers):
    response = client.get("/api/v1/plans/")
    assert response.status_code == 200
    assert {row["tier"] for row in response.data} == {"free", "pro", "elite"}


@pytest.fixture
def client(db):
    from rest_framework.test import APIClient

    return APIClient()


# --- CRM --------------------------------------------------------------------


@pytest.mark.django_db
def test_a_pipeline_is_never_reachable_by_another_user(tiers):
    """A contact list names who somebody is talking to and for how much."""
    mine = make_user("mine@example.com")
    theirs = make_user("theirs@example.com")

    contact = Contact.objects.create(owner=theirs, name="Their Client")

    listed = sign_in(mine).get("/api/v1/crm/contacts/").data
    assert listed["count"] == 0
    assert sign_in(mine).get(f"/api/v1/crm/contacts/{contact.pk}/").status_code == 404


@pytest.mark.django_db
def test_a_deal_cannot_be_attached_to_someone_elses_contact(tiers):
    mine = make_user("mine@example.com")
    theirs = make_user("theirs@example.com")
    contact = Contact.objects.create(owner=theirs, name="Their Client")

    response = sign_in(mine).post(
        "/api/v1/crm/deals/",
        {"contact": contact.pk, "title": "Sneaky deal", "value": "1000"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_the_free_contact_limit_is_enforced_and_names_the_fix(tiers):
    user = make_user("limited@example.com")
    limit = tiers[Plan.Tier.FREE].crm_contact_limit
    Contact.objects.bulk_create(
        [Contact(owner=user, name=f"Client {index}") for index in range(limit)]
    )

    response = sign_in(user).post("/api/v1/crm/contacts/", {"name": "One too many"}, format="json")
    assert response.status_code == 402
    assert response.data["code"] == "upgrade_required"


@pytest.mark.django_db
def test_pro_lifts_the_contact_limit(tiers):
    user = make_user("pro@example.com")
    subscribe(user, tiers[Plan.Tier.PRO])
    Contact.objects.bulk_create(
        [Contact(owner=user, name=f"Client {index}") for index in range(60)]
    )

    response = sign_in(user).post("/api/v1/crm/contacts/", {"name": "Sixty-one"}, format="json")
    assert response.status_code == 201


@pytest.mark.django_db
def test_moving_a_deal_to_won_closes_it(tiers):
    user = make_user("closer@example.com")
    contact = Contact.objects.create(owner=user, name="Client")
    deal = Deal.objects.create(owner=user, contact=contact, title="Big one", value=Decimal("50000"))

    response = sign_in(user).post(
        f"/api/v1/crm/deals/{deal.pk}/stage/", {"stage": "won"}, format="json"
    )
    assert response.status_code == 200
    deal.refresh_from_db()
    assert deal.closed_at is not None
    assert deal.is_open is False


@pytest.mark.django_db
def test_win_rate_is_null_before_anything_is_decided(tiers):
    """A win rate over zero closed deals is a divide-by-zero dressed as 0%."""
    user = make_user("fresh@example.com")
    contact = Contact.objects.create(owner=user, name="Client")
    Deal.objects.create(owner=user, contact=contact, title="Open", value=Decimal("1000"))

    summary = sign_in(user).get("/api/v1/crm/pipeline/").data
    assert summary["win_rate"] is None

    deal = Deal.objects.create(owner=user, contact=contact, title="Closed", value=Decimal("1000"))
    deal.move_to(Deal.Stage.WON)
    assert sign_in(user).get("/api/v1/crm/pipeline/").data["win_rate"] == 100


@pytest.mark.django_db
def test_overdue_tasks_are_counted(tiers):
    user = make_user("busy@example.com")
    Task.objects.create(
        owner=user, title="Chase invoice", due_at=timezone.now() - timedelta(days=2)
    )
    assert sign_in(user).get("/api/v1/crm/pipeline/").data["overdue_tasks"] == 1


# --- Agencies ---------------------------------------------------------------


@pytest.mark.django_db
def test_creating_an_agency_needs_elite(tiers):
    user = make_user("hopeful@example.com")
    body = {"name": "Northline Studio"}

    refused = sign_in(user).post("/api/v1/agencies/", body, format="json")
    assert refused.status_code == 402

    subscribe(user, tiers[Plan.Tier.ELITE])
    allowed = sign_in(user).post("/api/v1/agencies/", body, format="json")
    assert allowed.status_code == 201
    assert allowed.data["my_role"] == "owner"


@pytest.mark.django_db
def test_seats_are_checked_against_the_owners_plan(tiers):
    """An admin on a free plan must not be able to grow an agency past what the
    owner paid for."""
    owner = make_user("owner@example.com")
    subscribe(owner, tiers[Plan.Tier.ELITE])
    agency = Agency.objects.create(name="Studio", owner=owner)
    AgencyMember.objects.create(
        agency=agency,
        user=owner,
        role=AgencyMember.Role.OWNER,
        status=AgencyMember.Status.ACTIVE,
        joined_at=timezone.now(),
    )

    seats = tiers[Plan.Tier.ELITE].team_seats
    for index in range(seats - 1):
        AgencyMember.objects.create(
            agency=agency,
            user=make_user(f"member{index}@example.com"),
            status=AgencyMember.Status.ACTIVE,
            joined_at=timezone.now(),
        )

    extra = make_user("extra@example.com")
    response = sign_in(owner).post(
        f"/api/v1/agencies/{agency.pk}/members/", {"handle": extra.handle}, format="json"
    )
    assert response.status_code == 402
    assert response.data["code"] == "upgrade_required"


@pytest.mark.django_db
def test_only_an_admin_can_invite(tiers):
    owner = make_user("owner@example.com")
    subscribe(owner, tiers[Plan.Tier.ELITE])
    agency = Agency.objects.create(name="Studio", owner=owner)
    AgencyMember.objects.create(
        agency=agency,
        user=owner,
        role=AgencyMember.Role.OWNER,
        status=AgencyMember.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    member = make_user("member@example.com")
    AgencyMember.objects.create(
        agency=agency, user=member, status=AgencyMember.Status.ACTIVE, joined_at=timezone.now()
    )

    response = sign_in(member).post(
        f"/api/v1/agencies/{agency.pk}/members/",
        {"handle": make_user("someone@example.com").handle},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_the_owner_cannot_be_removed(tiers):
    owner = make_user("owner@example.com")
    subscribe(owner, tiers[Plan.Tier.ELITE])
    agency = Agency.objects.create(name="Studio", owner=owner)
    membership = AgencyMember.objects.create(
        agency=agency,
        user=owner,
        role=AgencyMember.Role.OWNER,
        status=AgencyMember.Status.ACTIVE,
        joined_at=timezone.now(),
    )

    response = sign_in(owner).post(f"/api/v1/agencies/{agency.pk}/members/{membership.pk}/remove/")
    assert response.status_code == 400
    assert response.data["code"] == "owner_protected"


def _agency_with_owner(tiers) -> tuple:
    owner = make_user("owner@example.com")
    subscribe(owner, tiers[Plan.Tier.ELITE])
    agency = Agency.objects.create(name="Studio", owner=owner)
    AgencyMember.objects.create(
        agency=agency,
        user=owner,
        role=AgencyMember.Role.OWNER,
        status=AgencyMember.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    return owner, agency


@pytest.mark.django_db
def test_an_invitee_can_find_the_agency_that_invited_them(tiers):
    """An invite nobody can find is an invite nobody accepts.

    `my_role` stays null until the membership is active, which is correct — an
    invitee is not yet a member. But that left the invitation itself invisible
    in the only list the recipient would think to check.
    """
    _owner, agency = _agency_with_owner(tiers)
    invitee = make_user("invitee@example.com")
    AgencyMember.objects.create(agency=agency, user=invitee)  # defaults to INVITED

    response = sign_in(invitee).get("/api/v1/agencies/?mine=true")
    assert response.status_code == 200

    rows = response.data["results"]
    assert [row["id"] for row in rows] == [agency.pk]
    assert rows[0]["my_status"] == "invited"
    # Still not a member until they accept.
    assert rows[0]["my_role"] is None


@pytest.mark.django_db
def test_a_member_can_remove_themselves(tiers):
    """Leaving, and declining an invitation, are the same operation.

    Without this only an admin could clear a membership — so an invite you did
    not want would sit in your list permanently, which is the opposite of what
    declining means.
    """
    _owner, agency = _agency_with_owner(tiers)
    invitee = make_user("invitee@example.com")
    membership = AgencyMember.objects.create(agency=agency, user=invitee)

    response = sign_in(invitee).post(
        f"/api/v1/agencies/{agency.pk}/members/{membership.pk}/remove/"
    )
    assert response.status_code == 204

    membership.refresh_from_db()
    assert membership.status == AgencyMember.Status.REMOVED
    # And it stops showing up as a pending invitation.
    listing = sign_in(invitee).get("/api/v1/agencies/?mine=true")
    assert listing.data["results"] == []


@pytest.mark.django_db
def test_a_member_still_cannot_remove_someone_else(tiers):
    """Self-removal must not become a way to eject other people."""
    _owner, agency = _agency_with_owner(tiers)

    one = make_user("one@example.com")
    AgencyMember.objects.create(
        agency=agency, user=one, status=AgencyMember.Status.ACTIVE, joined_at=timezone.now()
    )
    two = make_user("two@example.com")
    other = AgencyMember.objects.create(
        agency=agency, user=two, status=AgencyMember.Status.ACTIVE, joined_at=timezone.now()
    )

    response = sign_in(one).post(f"/api/v1/agencies/{agency.pk}/members/{other.pk}/remove/")
    assert response.status_code == 403

    other.refresh_from_db()
    assert other.status == AgencyMember.Status.ACTIVE


# --- Workspaces -------------------------------------------------------------


@pytest.mark.django_db
def test_a_workspace_is_visible_to_members_not_just_its_creator(tiers):
    creator = make_user("creator@example.com")
    guest = make_user("guest@example.com")
    stranger = make_user("stranger@example.com")

    created = sign_in(creator).post(
        "/api/v1/workspaces/", {"name": "Northline redesign"}, format="json"
    )
    assert created.status_code == 201
    workspace_id = created.data["id"]

    sign_in(creator).post(
        f"/api/v1/workspaces/{workspace_id}/invite/",
        {"handle": guest.handle, "is_client": True},
        format="json",
    )

    assert sign_in(guest).get("/api/v1/workspaces/").data["count"] == 1
    assert sign_in(stranger).get("/api/v1/workspaces/").data["count"] == 0


# --- Retainers --------------------------------------------------------------


@pytest.mark.django_db
def test_selling_a_retainer_needs_a_paid_plan(tiers):
    seller = make_user("seller@example.com")
    body = {
        "title": "Monthly design retainer",
        "description": "Ongoing brand work, billed monthly.",
        "monthly_price": "25000",
        "deliverables": ["4 social sets", "1 landing page"],
    }

    refused = sign_in(seller).post("/api/v1/retainers/", body, format="json")
    assert refused.status_code == 402

    subscribe(seller, tiers[Plan.Tier.PRO])
    allowed = sign_in(seller).post("/api/v1/retainers/", body, format="json")
    assert allowed.status_code == 201


@pytest.mark.django_db
def test_a_retainer_must_say_what_the_buyer_gets(tiers):
    seller = make_user("seller@example.com")
    subscribe(seller, tiers[Plan.Tier.PRO])

    response = sign_in(seller).post(
        "/api/v1/retainers/",
        {
            "title": "Vague retainer",
            "description": "Some work each month.",
            "monthly_price": "25000",
            "deliverables": [],
        },
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_subscribing_to_a_retainer_is_idempotent(tiers):
    seller = make_user("seller@example.com")
    subscribe(seller, tiers[Plan.Tier.PRO])
    buyer = make_user("buyer@example.com")

    plan = (
        sign_in(seller)
        .post(
            "/api/v1/retainers/",
            {
                "title": "Monthly design retainer",
                "description": "Ongoing brand work.",
                "monthly_price": "25000",
                "deliverables": ["4 social sets"],
            },
            format="json",
        )
        .data
    )

    first = sign_in(buyer).post(f"/api/v1/retainers/{plan['id']}/subscribe/")
    second = sign_in(buyer).post(f"/api/v1/retainers/{plan['id']}/subscribe/")

    assert first.status_code == 201
    assert first.data["id"] == second.data["id"]
    assert RetainerSubscription.objects.filter(buyer=buyer).count() == 1


@pytest.mark.django_db
def test_a_seller_cannot_subscribe_to_their_own_retainer(tiers):
    seller = make_user("seller@example.com")
    subscribe(seller, tiers[Plan.Tier.PRO])
    plan = (
        sign_in(seller)
        .post(
            "/api/v1/retainers/",
            {
                "title": "Monthly retainer",
                "description": "Work.",
                "monthly_price": "25000",
                "deliverables": ["Something"],
            },
            format="json",
        )
        .data
    )

    response = sign_in(seller).post(f"/api/v1/retainers/{plan['id']}/subscribe/")
    assert response.status_code == 400


@pytest.mark.django_db
def test_a_minimum_term_delays_cancellation_but_never_refuses_it(tiers):
    """Enforcing a commitment by refusing to accept a cancellation is not
    enforcement, it is a trap."""
    seller = make_user("seller@example.com")
    subscribe(seller, tiers[Plan.Tier.PRO])
    buyer = make_user("buyer@example.com")

    from core.scope import GLOBAL_SCOPE, use_scope

    with use_scope(GLOBAL_SCOPE):
        plan = RetainerPlan.objects.create(
            seller=seller,
            title="Three month retainer",
            description="Committed work.",
            monthly_price=Decimal("25000"),
            deliverables=["Monthly report"],
            minimum_months=3,
        )
    subscription = RetainerSubscription.objects.create(
        plan=plan,
        buyer=buyer,
        current_period_end=timezone.now() + timedelta(days=30),
        months_billed=1,
    )

    response = sign_in(buyer).post(f"/api/v1/retainers/subscriptions/{subscription.pk}/cancel/")
    assert response.status_code == 200
    subscription.refresh_from_db()
    # Accepted, but takes effect at the end of the committed period.
    assert subscription.cancel_at_period_end is True
    assert subscription.status == RetainerSubscription.Status.ACTIVE

    subscription.months_billed = 3
    subscription.save(update_fields=["months_billed"])
    sign_in(buyer).post(f"/api/v1/retainers/subscriptions/{subscription.pk}/cancel/")
    subscription.refresh_from_db()
    assert subscription.status == RetainerSubscription.Status.CANCELLED


@pytest.mark.django_db
def test_a_campus_retainer_never_reaches_the_global_catalogue(tiers):
    """RetainerPlan is a ScopedModel, so the leakage gate covers it — this
    pins the behaviour at the endpoint too."""
    from accounts.models import University, VerificationStatus
    from core.scope import Scope, SurfaceKind, Visibility, use_scope

    uni = University.objects.create(name="COMSATS", short_code="CUI")
    student = make_user("student@example.com")
    student.university = uni
    student.student_verification_status = VerificationStatus.VERIFIED
    student.save()
    subscribe(student, tiers[Plan.Tier.PRO])

    with use_scope(Scope(SurfaceKind.UNIVERSITY, uni.pk)):
        RetainerPlan.objects.create(
            seller=student,
            title="Campus tutoring retainer",
            description="Weekly sessions.",
            monthly_price=Decimal("5000"),
            deliverables=["Weekly session"],
            visibility=Visibility.UNIVERSITY,
            university=uni,
        )

    outsider = make_user("outsider@example.com")
    assert sign_in(outsider).get("/api/v1/retainers/").data["count"] == 0
