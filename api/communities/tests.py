"""
Tests for the community layer.

The rules worth guarding here are the ones that are quiet when they break: a
closed community whose contents are readable, a campus community that surfaces
globally, a moderator action available to somebody who is not one, and a
conversation readable by a third party.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from accounts.models import University, VerificationStatus
from communities.models import (
    ChatMessage,
    Community,
    Conversation,
    Event,
    EventRSVP,
    FeedItem,
    Membership,
    Reply,
    Report,
    Thread,
)
from core.scope import Scope, SurfaceKind, Visibility, use_scope
from marketplace.tests import make_user, sign_in

CAMPUS = "HTTP_X_SKILRIZE_SURFACE"


@pytest.fixture
def owner(db):
    return make_user("owner@example.com")


@pytest.fixture
def member(db):
    return make_user("member@example.com")


@pytest.fixture
def stranger(db):
    return make_user("stranger@example.com")


@pytest.fixture
def community(owner):
    response = sign_in(owner).post(
        "/api/v1/communities/",
        {"name": "Robotics Society", "tagline": "We build things", "kind": "open"},
        format="json",
    )
    assert response.status_code == 201, response.data
    return Community.objects.unscoped().get(pk=response.data["id"])


def join(user, community) -> None:
    assert sign_in(user).post(f"/api/v1/communities/{community.pk}/join/").status_code == 200


# --- Creation and membership ------------------------------------------------


@pytest.mark.django_db
def test_creating_a_community_makes_the_creator_its_owner(community, owner):
    membership = community.memberships.get(user=owner)
    assert membership.role == Membership.Role.OWNER
    assert community.member_count == 1


@pytest.mark.django_db
def test_joining_and_leaving_keeps_the_count_honest(community, member):
    join(member, community)
    community.refresh_from_db()
    assert community.member_count == 2

    assert sign_in(member).post(f"/api/v1/communities/{community.pk}/leave/").status_code == 204
    community.refresh_from_db()
    assert community.member_count == 1


@pytest.mark.django_db
def test_the_owner_cannot_walk_away_and_orphan_the_community(community, owner):
    response = sign_in(owner).post(f"/api/v1/communities/{community.pk}/leave/")
    assert response.status_code == 400
    assert response.data["code"] == "owner_cannot_leave"


@pytest.mark.django_db
def test_a_request_to_join_waits_for_approval(owner, member):
    created = sign_in(owner).post(
        "/api/v1/communities/", {"name": "Selective Club", "kind": "request"}, format="json"
    )
    community = Community.objects.unscoped().get(pk=created.data["id"])

    sign_in(member).post(f"/api/v1/communities/{community.pk}/join/")
    membership = community.memberships.get(user=member)
    assert membership.status == Membership.Status.PENDING

    community.refresh_from_db()
    assert community.member_count == 1, "a pending member is not a member"


@pytest.mark.django_db
def test_a_closed_community_is_discoverable_but_not_readable(owner, stranger):
    created = sign_in(owner).post(
        "/api/v1/communities/", {"name": "Invite Only", "kind": "closed"}, format="json"
    )
    community = Community.objects.unscoped().get(pk=created.data["id"])
    client = sign_in(stranger)

    # Findable, so it can be asked about…
    listing = client.get("/api/v1/communities/").data
    assert "Invite Only" in [row["name"] for row in listing["results"]]

    # …but not enterable.
    assert client.post(f"/api/v1/communities/{community.pk}/join/").status_code == 403
    assert client.get(f"/api/v1/communities/{community.pk}/members/").status_code == 403


# --- Discussion -------------------------------------------------------------


@pytest.mark.django_db
def test_only_members_can_start_a_discussion(community, member, stranger):
    join(member, community)
    body = {"community": community.pk, "title": "Meeting Friday", "body": "Same room as last week."}

    assert sign_in(member).post("/api/v1/threads/", body, format="json").status_code == 201
    refused = sign_in(stranger).post("/api/v1/threads/", body, format="json")
    assert refused.status_code == 403
    assert refused.data["code"] == "not_a_member"


@pytest.mark.django_db
def test_replies_bump_the_thread_and_count(community, owner, member):
    join(member, community)
    thread = (
        sign_in(owner)
        .post(
            "/api/v1/threads/",
            {"community": community.pk, "title": "Kit order", "body": "What do we still need?"},
            format="json",
        )
        .data
    )
    before = Thread.objects.unscoped().get(pk=thread["id"]).last_activity_at

    response = sign_in(member).post(
        f"/api/v1/threads/{thread['id']}/replies/", {"body": "Servos and a battery."}, format="json"
    )
    assert response.status_code == 201

    refreshed = Thread.objects.unscoped().get(pk=thread["id"])
    assert refreshed.reply_count == 1
    assert refreshed.last_activity_at > before


@pytest.mark.django_db
def test_nesting_stops_at_the_limit(community, owner):
    thread = (
        sign_in(owner)
        .post(
            "/api/v1/threads/",
            {"community": community.pk, "title": "Deep thread", "body": "How far does this go?"},
            format="json",
        )
        .data
    )
    client = sign_in(owner)

    # MAX_DEPTH is the deepest *depth value*, so levels 0..MAX_DEPTH are all
    # legal and the refusal comes one past that.
    parent = None
    for _ in range(Reply.MAX_DEPTH + 2):
        response = client.post(
            f"/api/v1/threads/{thread['id']}/replies/",
            {"body": "one deeper", "parent": parent},
            format="json",
        )
        if response.status_code != 201:
            break
        parent = response.data["id"]

    assert response.status_code == 400
    assert response.data["code"] == "too_deep"


@pytest.mark.django_db
def test_a_locked_thread_takes_no_replies(community, owner, member):
    join(member, community)
    thread = (
        sign_in(owner)
        .post(
            "/api/v1/threads/",
            {"community": community.pk, "title": "Settled matter", "body": "Decision is final."},
            format="json",
        )
        .data
    )

    assert sign_in(owner).post(f"/api/v1/threads/{thread['id']}/lock/").status_code == 200
    refused = sign_in(member).post(
        f"/api/v1/threads/{thread['id']}/replies/", {"body": "But actually…"}, format="json"
    )
    assert refused.status_code == 400
    assert refused.data["code"] == "locked"


@pytest.mark.django_db
def test_only_a_moderator_can_pin_or_lock(community, member):
    join(member, community)
    thread = (
        sign_in(member)
        .post(
            "/api/v1/threads/",
            {"community": community.pk, "title": "My thread", "body": "Please pin this."},
            format="json",
        )
        .data
    )

    # Its author, but not a moderator.
    assert sign_in(member).post(f"/api/v1/threads/{thread['id']}/pin/").status_code == 403


@pytest.mark.django_db
def test_a_removed_reply_keeps_its_children_and_hides_its_words(community, owner, member):
    join(member, community)
    thread = (
        sign_in(owner)
        .post(
            "/api/v1/threads/",
            {"community": community.pk, "title": "Thread", "body": "Opening post here."},
            format="json",
        )
        .data
    )

    parent = (
        sign_in(member)
        .post(f"/api/v1/threads/{thread['id']}/replies/", {"body": "something rude"}, format="json")
        .data
    )
    child = (
        sign_in(owner)
        .post(
            f"/api/v1/threads/{thread['id']}/replies/",
            {"body": "a reasonable answer", "parent": parent["id"]},
            format="json",
        )
        .data
    )

    # The owner moderates, so they may remove somebody else's reply.
    assert sign_in(owner).delete(f"/api/v1/replies/{parent['id']}/").status_code == 204

    listed = sign_in(owner).get(f"/api/v1/threads/{thread['id']}/replies/").data["results"]
    bodies = {row["id"]: row["body"] for row in listed}
    assert bodies[parent["id"]] == "[removed by a moderator]"
    assert bodies[child["id"]] == "a reasonable answer", "the answer must survive"


# --- Group chat -------------------------------------------------------------


@pytest.mark.django_db
def test_chat_is_members_only_and_reads_oldest_first(community, owner, member, stranger):
    join(member, community)
    for text in ("first", "second", "third"):
        sign_in(member).post(
            f"/api/v1/communities/{community.pk}/chat/", {"body": text}, format="json"
        )

    messages = sign_in(owner).get(f"/api/v1/communities/{community.pk}/chat/").data
    assert [m["body"] for m in messages] == ["first", "second", "third"]

    refused = sign_in(stranger).get(f"/api/v1/communities/{community.pk}/chat/")
    assert refused.status_code == 403


# --- Events -----------------------------------------------------------------


@pytest.mark.django_db
def test_an_event_needs_a_place_or_a_link(community, owner):
    response = sign_in(owner).post(
        "/api/v1/events/",
        {
            "community": community.pk,
            "title": "Nowhere meetup",
            "starts_at": (timezone.now() + timezone.timedelta(days=2)).isoformat(),
        },
        format="json",
    )
    assert response.status_code == 400
    assert "location" in response.data


@pytest.mark.django_db
def test_rsvp_respects_capacity(community, owner, member):
    join(member, community)
    event = (
        sign_in(owner)
        .post(
            "/api/v1/events/",
            {
                "community": community.pk,
                "title": "Tiny workshop",
                "starts_at": (timezone.now() + timezone.timedelta(days=2)).isoformat(),
                "location": "Lab 3",
                "capacity": 1,
            },
            format="json",
        )
        .data
    )

    assert (
        sign_in(owner)
        .post(f"/api/v1/events/{event['id']}/rsvp/", {"status": "going"}, format="json")
        .status_code
        == 200
    )
    full = sign_in(member).post(
        f"/api/v1/events/{event['id']}/rsvp/", {"status": "going"}, format="json"
    )
    assert full.status_code == 400
    assert full.data["code"] == "event_full"

    # Interested is still fine — capacity limits attendance, not curiosity.
    assert (
        sign_in(member)
        .post(f"/api/v1/events/{event['id']}/rsvp/", {"status": "interested"}, format="json")
        .status_code
        == 200
    )


@pytest.mark.django_db
def test_changing_your_own_rsvp_does_not_double_count(community, owner):
    event = (
        sign_in(owner)
        .post(
            "/api/v1/events/",
            {
                "community": community.pk,
                "title": "Workshop",
                "starts_at": (timezone.now() + timezone.timedelta(days=2)).isoformat(),
                "online_url": "https://example.com/meet",
            },
            format="json",
        )
        .data
    )
    client = sign_in(owner)
    for _ in range(3):
        client.post(f"/api/v1/events/{event['id']}/rsvp/", {"status": "going"}, format="json")

    assert Event.objects.unscoped().get(pk=event["id"]).going_count == 1
    assert EventRSVP.objects.filter(event_id=event["id"]).count() == 1


# --- Peer messaging ---------------------------------------------------------


@pytest.mark.django_db
def test_a_conversation_between_two_people_is_reused(owner, member):
    first = sign_in(owner).post(
        "/api/v1/conversations/start/", {"handle": member.handle}, format="json"
    )
    second = sign_in(member).post(
        "/api/v1/conversations/start/", {"handle": owner.handle}, format="json"
    )

    assert first.status_code == 201
    assert first.data["id"] == second.data["id"], "opening from either side is one conversation"
    assert Conversation.objects.count() == 1


@pytest.mark.django_db
def test_a_third_party_cannot_read_a_conversation(owner, member, stranger):
    conversation = (
        sign_in(owner)
        .post("/api/v1/conversations/start/", {"handle": member.handle}, format="json")
        .data
    )
    sign_in(owner).post(
        f"/api/v1/conversations/{conversation['id']}/messages/",
        {"body": "private"},
        format="json",
    )

    assert (
        sign_in(stranger).get(f"/api/v1/conversations/{conversation['id']}/messages/").status_code
        == 404
    )
    assert sign_in(stranger).get("/api/v1/conversations/").data["count"] == 0


@pytest.mark.django_db
def test_reading_a_conversation_clears_its_unread_count(owner, member):
    conversation = (
        sign_in(owner)
        .post("/api/v1/conversations/start/", {"handle": member.handle}, format="json")
        .data
    )
    sign_in(owner).post(
        f"/api/v1/conversations/{conversation['id']}/messages/", {"body": "hello"}, format="json"
    )

    inbox = sign_in(member).get("/api/v1/conversations/").data["results"]
    assert inbox[0]["unread_count"] == 1

    sign_in(member).get(f"/api/v1/conversations/{conversation['id']}/messages/")
    inbox = sign_in(member).get("/api/v1/conversations/").data["results"]
    assert inbox[0]["unread_count"] == 0


# --- Feed -------------------------------------------------------------------


@pytest.mark.django_db
def test_activity_writes_to_the_feed(community, owner, member):
    join(member, community)
    verbs = set(FeedItem.objects.unscoped().values_list("verb", flat=True))
    assert FeedItem.Verb.COMMUNITY_CREATED in verbs
    assert FeedItem.Verb.JOINED_COMMUNITY in verbs


@pytest.mark.django_db
def test_a_failed_feed_write_never_breaks_the_action(community, owner, monkeypatch):
    """The feed is a convenience and must never roll back real work."""
    from communities import models as community_models

    def explode(*args, **kwargs):
        raise RuntimeError("feed is down")

    monkeypatch.setattr(community_models.FeedItem.objects, "create", explode)

    response = sign_in(owner).post(
        "/api/v1/threads/",
        {
            "community": community.pk,
            "title": "Still works",
            "body": "Feed is broken but this is not.",
        },
        format="json",
    )
    assert response.status_code == 201


# --- Tenancy ----------------------------------------------------------------


@pytest.mark.django_db
def test_a_campus_community_never_appears_globally(db):
    cui = University.objects.create(name="COMSATS", short_code="CUI")
    student = make_user("student@example.com")
    student.university = cui
    student.student_verification_status = VerificationStatus.VERIFIED
    student.save()

    created = sign_in(student).post(
        "/api/v1/communities/",
        {"name": "CUI Robotics", "kind": "open", "visibility": "university"},
        format="json",
        **{CAMPUS: "university"},
    )
    assert created.status_code == 201

    outsider = make_user("outsider@example.com")
    listing = sign_in(outsider).get("/api/v1/communities/").data
    assert "CUI Robotics" not in [row["name"] for row in listing["results"]]


@pytest.mark.django_db
def test_content_inherits_the_surface_of_its_community(db):
    """A thread in a campus community is campus content, not global content."""
    cui = University.objects.create(name="COMSATS", short_code="CUI")
    student = make_user("student@example.com")
    student.university = cui
    student.student_verification_status = VerificationStatus.VERIFIED
    student.save()

    with use_scope(Scope(SurfaceKind.UNIVERSITY, cui.pk)):
        campus = Community.objects.create(
            name="CUI Society",
            slug="cui-society",
            created_by=student,
            visibility=Visibility.UNIVERSITY,
            university=cui,
        )
        thread = Thread.objects.create(
            community=campus, author=student, title="Campus thread", body="Only for us."
        )
        chat = ChatMessage.objects.create(community=campus, author=student, body="hi")

    # Copied from the community, not defaulted to global.
    assert thread.visibility == Visibility.UNIVERSITY
    assert thread.university_id == cui.pk
    assert chat.visibility == Visibility.UNIVERSITY

    with use_scope(Scope(SurfaceKind.GLOBAL)):
        assert Thread.objects.count() == 0
        assert ChatMessage.objects.count() == 0


# --- Moderation -------------------------------------------------------------


@pytest.mark.django_db
def test_reporting_is_once_per_person_per_item(community, owner, member):
    join(member, community)
    thread = (
        sign_in(owner)
        .post(
            "/api/v1/threads/",
            {"community": community.pk, "title": "Contested", "body": "Something questionable."},
            format="json",
        )
        .data
    )
    body = {
        "kind": "thread",
        "object_id": thread["id"],
        "community": community.pk,
        "reason": "This breaks the rules.",
    }

    assert sign_in(member).post("/api/v1/reports/", body, format="json").status_code == 201
    again = sign_in(member).post("/api/v1/reports/", body, format="json")
    assert again.status_code == 409


@pytest.mark.django_db
def test_the_queue_shows_only_communities_you_moderate(community, owner, member, stranger):
    join(member, community)
    thread = (
        sign_in(owner)
        .post(
            "/api/v1/threads/",
            {"community": community.pk, "title": "Contested", "body": "Something questionable."},
            format="json",
        )
        .data
    )
    sign_in(member).post(
        "/api/v1/reports/",
        {
            "kind": "thread",
            "object_id": thread["id"],
            "community": community.pk,
            "reason": "This breaks the rules.",
        },
        format="json",
    )

    assert len(sign_in(owner).get("/api/v1/moderation/queue/").data) == 1
    assert sign_in(stranger).get("/api/v1/moderation/queue/").data == []
    assert sign_in(member).get("/api/v1/moderation/queue/").data == []


@pytest.mark.django_db
def test_resolving_a_report_requires_moderating_that_community(community, owner, member):
    join(member, community)
    report = Report.objects.create(
        reporter=member,
        community=community,
        kind=Report.Kind.THREAD,
        object_id=1,
        reason="Testing the gate.",
    )

    refused = sign_in(member).post(f"/api/v1/moderation/reports/{report.pk}/resolve/")
    assert refused.status_code == 403

    upheld = sign_in(owner).post(
        f"/api/v1/moderation/reports/{report.pk}/resolve/",
        {"upheld": True, "note": "Removed."},
        format="json",
    )
    assert upheld.status_code == 200
    assert upheld.data["status"] == "upheld"
