"""
Tests for the project and bidding track.

The rules worth guarding here are the ones that are invisible when they work
and expensive when they do not: the profile gate, the proposal quota, the
self-bidding block, and — most of all — that a campus brief never appears in
the global marketplace.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from accounts.models import University, User, VerificationStatus
from core.scope import GLOBAL_SCOPE, Scope, SurfaceKind, Visibility, use_scope
from marketplace.models import Category, Project, ProjectType, Proposal, Skill

PASSWORD = "correct-horse-battery-staple"


def make_user(email: str, *, transactable: bool = True, **extra) -> User:
    user = User.objects.create_user(email, PASSWORD, **extra)
    if transactable:
        user.email_verified = True
        user.phone_verified = True
        user.identity_status = VerificationStatus.VERIFIED
        user.save()
    return user


def sign_in(user: User) -> APIClient:
    client = APIClient()
    client.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")
    return client


@pytest.fixture
def client_user(db) -> User:
    return make_user("hirer@example.com")


@pytest.fixture
def freelancer(db) -> User:
    return make_user("seller@example.com")


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(name="Development & IT", slug="development-it")


@pytest.fixture
def project(client_user, category) -> Project:
    with use_scope(GLOBAL_SCOPE):
        project = Project.objects.create(
            client=client_user,
            title="Build an internal ops dashboard",
            description="Rebuild our ops dashboard in React with a Django API behind it.",
            category=category,
            project_type=ProjectType.FIXED,
            budget_min=40000,
            budget_max=80000,
        )
    project.publish()
    return project


# --- Posting a brief -------------------------------------------------------


BRIEF = {
    "title": "Design a brand identity",
    "description": "Logo, palette, and a one-page usage guide for a new fintech.",
    "project_type": "fixed",
    "budget_min": "15000",
    "budget_max": "30000",
    "experience_level": "intermediate",
}


@pytest.mark.django_db
def test_posting_a_project_requires_a_complete_profile(db):
    """The gate is real: browsing is free, posting is not."""
    incomplete = make_user("incomplete@example.com", transactable=False)

    response = sign_in(incomplete).post("/api/v1/projects/", BRIEF, format="json")

    assert response.status_code == 403
    assert response.data["code"] == "profile_incomplete"
    assert Project.objects.unscoped().count() == 0


@pytest.mark.django_db
def test_a_verified_client_can_post_and_publish(client_user, category):
    api = sign_in(client_user)

    created = api.post(
        "/api/v1/projects/",
        {**BRIEF, "category": category.id, "screening_questions": [{"text": "Show similar work."}]},
        format="json",
    )
    assert created.status_code == 201

    project = Project.objects.unscoped().get(pk=created.data["id"])
    # A new brief is a draft until explicitly published.
    assert project.status == Project.Status.DRAFT
    assert project.screening_questions.count() == 1

    published = api.post(f"/api/v1/projects/{project.pk}/publish/")
    assert published.status_code == 200
    assert published.data["status"] == "open"


@pytest.mark.django_db
def test_a_fixed_project_must_carry_a_budget(client_user):
    response = sign_in(client_user).post(
        "/api/v1/projects/", {**BRIEF, "budget_min": None, "budget_max": None}, format="json"
    )
    assert response.status_code == 400
    assert "budget_max" in response.data


@pytest.mark.django_db
def test_only_the_owner_can_edit_a_brief(project, freelancer):
    response = sign_in(freelancer).patch(
        f"/api/v1/projects/{project.pk}/", {"title": "Hijacked"}, format="json"
    )
    assert response.status_code == 403
    project.refresh_from_db()
    assert project.title != "Hijacked"


@pytest.mark.django_db
def test_browsing_shows_open_projects_only(project, freelancer):
    with use_scope(GLOBAL_SCOPE):
        Project.objects.create(
            client=project.client,
            title="Still a draft",
            description="Not ready.",
            project_type=ProjectType.FIXED,
            budget_max=1000,
        )

    response = sign_in(freelancer).get("/api/v1/projects/")

    assert response.status_code == 200
    titles = [row["title"] for row in response.data["results"]]
    assert project.title in titles
    assert "Still a draft" not in titles


# --- Scope isolation, applied to real marketplace content ------------------


@pytest.mark.django_db
def test_a_campus_brief_never_appears_in_the_global_marketplace(client_user, freelancer):
    """The Phase 0 tenancy layer, proved against an actual Project."""
    cui = University.objects.create(name="COMSATS", short_code="CUI")
    fast = University.objects.create(name="FAST", short_code="FAST")

    with use_scope(Scope(SurfaceKind.UNIVERSITY, university_id=cui.pk)):
        Project.objects.create(
            client=client_user,
            title="CUI only — poster design",
            description="For the CUI society.",
            project_type=ProjectType.FIXED,
            budget_max=1500,
            status=Project.Status.OPEN,
            visibility=Visibility.UNIVERSITY,
            university=cui,
        )

    # A plain browse runs on the global surface.
    titles = [row["title"] for row in sign_in(freelancer).get("/api/v1/projects/").data["results"]]
    assert "CUI only — poster design" not in titles

    # And a student at another university sees nothing of it either.
    with use_scope(Scope(SurfaceKind.UNIVERSITY, university_id=fast.pk)):
        assert not Project.objects.filter(title__startswith="CUI only").exists()


@pytest.mark.django_db
def test_a_non_student_cannot_post_to_a_campus_portal(client_user):
    response = sign_in(client_user).post(
        "/api/v1/projects/", {**BRIEF, "visibility": "university"}, format="json"
    )
    assert response.status_code == 400
    assert "visibility" in response.data


# --- Proposals -------------------------------------------------------------


PROPOSAL = {
    "cover_letter": "I have shipped three dashboards on this exact stack.",
    "bid_amount": "60000",
    "estimated_days": 21,
}


@pytest.mark.django_db
def test_a_freelancer_can_submit_a_proposal(project, freelancer):
    response = sign_in(freelancer).post(
        f"/api/v1/projects/{project.pk}/proposals/", PROPOSAL, format="json"
    )

    assert response.status_code == 201
    project.refresh_from_db()
    assert project.proposal_count == 1


@pytest.mark.django_db
def test_a_client_cannot_bid_on_their_own_project(project, client_user):
    response = sign_in(client_user).post(
        f"/api/v1/projects/{project.pk}/proposals/", PROPOSAL, format="json"
    )
    assert response.status_code == 400
    assert "your own project" in response.data["detail"]


@pytest.mark.django_db
def test_a_freelancer_cannot_bid_twice(project, freelancer):
    api = sign_in(freelancer)
    assert (
        api.post(f"/api/v1/projects/{project.pk}/proposals/", PROPOSAL, format="json").status_code
        == 201
    )

    second = api.post(f"/api/v1/projects/{project.pk}/proposals/", PROPOSAL, format="json")
    assert second.status_code == 400
    assert "already submitted" in second.data["detail"]


@pytest.mark.django_db
def test_required_screening_questions_must_be_answered(project, freelancer):
    from marketplace.models import ScreeningQuestion

    ScreeningQuestion.objects.create(project=project, text="Link a similar dashboard.")

    response = sign_in(freelancer).post(
        f"/api/v1/projects/{project.pk}/proposals/", PROPOSAL, format="json"
    )

    assert response.status_code == 400
    assert "answers" in response.data


@pytest.mark.django_db
def test_the_proposal_quota_is_enforced(project, freelancer, client_user, category):
    """Mass low-quality bidding is what the quota exists to stop."""
    with use_scope(GLOBAL_SCOPE):
        for index in range(Proposal.FREE_PLAN_QUOTA):
            other = Project.objects.create(
                client=client_user,
                title=f"Filler {index}",
                description="x",
                project_type=ProjectType.FIXED,
                budget_max=1000,
                status=Project.Status.OPEN,
            )
            Proposal.objects.create(
                project=other, freelancer=freelancer, cover_letter="x", bid_amount=500
            )

    assert Proposal.remaining_quota(freelancer) == 0

    response = sign_in(freelancer).post(
        f"/api/v1/projects/{project.pk}/proposals/", PROPOSAL, format="json"
    )
    assert response.status_code == 402
    assert response.data["code"] == "quota_exhausted"


@pytest.mark.django_db
def test_withdrawing_a_proposal_frees_its_slot(project, freelancer):
    api = sign_in(freelancer)
    proposal_id = api.post(
        f"/api/v1/projects/{project.pk}/proposals/", PROPOSAL, format="json"
    ).data["id"]

    before = Proposal.remaining_quota(freelancer)
    assert api.post(f"/api/v1/proposals/{proposal_id}/withdraw/").status_code == 200
    assert Proposal.remaining_quota(freelancer) == before + 1


@pytest.mark.django_db
def test_a_freelancer_cannot_read_rival_proposals(project, freelancer, db):
    rival = make_user("rival@example.com")
    Proposal.objects.create(
        project=project, freelancer=rival, cover_letter="Mine", bid_amount=50000
    )
    Proposal.objects.create(
        project=project, freelancer=freelancer, cover_letter="Also mine", bid_amount=55000
    )

    # The bidder sees only their own bid…
    seen = sign_in(freelancer).get(f"/api/v1/projects/{project.pk}/proposals/").data
    assert [row["cover_letter"] for row in seen] == ["Also mine"]

    # …while the client sees the whole field.
    assert len(sign_in(project.client).get(f"/api/v1/projects/{project.pk}/proposals/").data) == 2


@pytest.mark.django_db
def test_a_closed_project_stops_accepting_proposals(project, freelancer):
    project.close()

    response = sign_in(freelancer).post(
        f"/api/v1/projects/{project.pk}/proposals/", PROPOSAL, format="json"
    )
    assert response.status_code == 400
    assert response.data["code"] == "proposal_not_allowed"


@pytest.mark.django_db
def test_students_only_projects_exclude_everyone_else(project, freelancer):
    project.verified_students_only = True
    project.save(update_fields=["verified_students_only"])

    response = sign_in(freelancer).post(
        f"/api/v1/projects/{project.pk}/proposals/", PROPOSAL, format="json"
    )
    assert response.status_code == 400
    assert "verified students" in response.data["detail"]


@pytest.mark.django_db
def test_quota_endpoint_reports_remaining_slots(freelancer):
    response = sign_in(freelancer).get("/api/v1/proposals/quota/")

    assert response.status_code == 200
    assert response.data["limit"] == Proposal.FREE_PLAN_QUOTA
    assert response.data["remaining"] == Proposal.FREE_PLAN_QUOTA


@pytest.mark.django_db
def test_students_get_a_larger_quota(db):
    university = University.objects.create(name="COMSATS", short_code="CUI")
    student = make_user("student@cui.edu.pk")
    student.university = university
    student.student_verification_status = VerificationStatus.VERIFIED
    student.save()

    assert Proposal.quota_for(student) == Proposal.FREE_PLAN_STUDENT_QUOTA


# --- Taxonomy --------------------------------------------------------------


@pytest.mark.django_db
def test_categories_expose_their_children(category):
    Category.objects.create(name="Web Development", slug="web-development", parent=category)

    response = APIClient().get("/api/v1/categories/")

    assert response.status_code == 200
    assert response.data[0]["children"][0]["name"] == "Web Development"


@pytest.mark.django_db
def test_skill_search_is_limited_to_approved_terms():
    Skill.objects.create(name="React")
    Skill.objects.create(name="Reactive Voodoo", is_approved=False)

    names = [row["name"] for row in APIClient().get("/api/v1/skills/?q=react").data]

    assert names == ["React"]
