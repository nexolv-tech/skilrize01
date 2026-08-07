"""
The cross-tenant leakage suite.

Report Section 15.2 makes this a release gate rather than ordinary coverage,
and the reasoning is worth restating because it changes how these tests are
written: a tenancy bug does not look like a bug. Nothing errors, no alert
fires, and every page renders. One university simply sees another's private
work, or a student's campus-only brief turns up in the open marketplace — and
the first person to notice is a customer.

So this file is adversarial rather than illustrative. It is not here to show
that scoping works on the happy path; it is here to try to get data out.

Four properties, each attacked separately:

  1. **No unscoped access.** A scopeable model queried with no scope raises
     rather than returning rows. Fail open here and nothing else matters.
  2. **No leakage across surfaces.** Campus content never reaches the global
     marketplace, and one campus never reaches another — through lists, detail
     routes, search, filters, or counts.
  3. **No entitlement escalation.** A user cannot obtain a surface they are not
     verified for, and cannot keep one after it is revoked.
  4. **Complete coverage.** Every `ScopedModel` in the codebase is exercised.
     A model added later without a scope test fails `test_every_scoped_model_
     is_covered` — the gate defends itself against the next developer.

The fourth is the one that keeps this suite honest as the schema grows.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from accounts.models import University, User, VerificationStatus
from core.models import ScopedModel
from core.scope import (
    GLOBAL_SCOPE,
    UNRESTRICTED_SCOPE,
    Scope,
    ScopeDenied,
    ScopeNotSet,
    SurfaceKind,
    Visibility,
    resolve_for,
    use_scope,
)
from gigs.models import Gig
from marketplace.models import Category, Project, ProjectType

PASSWORD = "Correct-Horse9-Battery"
SURFACE_HEADER = "HTTP_X_SKILRIZE_SURFACE"


# --- Fixtures ---------------------------------------------------------------


@pytest.fixture
def comsats(db):
    return University.objects.create(name="COMSATS University", short_code="CUI")


@pytest.fixture
def fast(db):
    return University.objects.create(name="FAST NUCES", short_code="FAST")


@pytest.fixture
def category(db):
    return Category.objects.create(name="Development & IT", slug="development-it")


def make_student(email: str, university: University | None) -> User:
    user = User.objects.create_user(email, PASSWORD)
    user.email_verified = True
    user.phone_verified = True
    user.identity_status = VerificationStatus.VERIFIED
    if university is not None:
        user.university = university
        user.student_verification_status = VerificationStatus.VERIFIED
    user.save()
    return user


def sign_in(user: User, surface: str | None = None) -> APIClient:
    client = APIClient()
    client.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")
    if surface:
        client.credentials(**{SURFACE_HEADER: surface})
    return client


def make_project(owner: User, category: Category, title: str, university: University | None):
    """Create a brief on whichever surface `university` implies."""
    visibility = Visibility.GLOBAL if university is None else Visibility.UNIVERSITY
    scope = GLOBAL_SCOPE if university is None else Scope(SurfaceKind.UNIVERSITY, university.pk)
    with use_scope(scope):
        return Project.objects.create(
            client=owner,
            category=category,
            title=title,
            description="x" * 120,
            project_type=ProjectType.FIXED,
            status=Project.Status.OPEN,
            visibility=visibility,
            university=university,
        )


# --- 1. Nothing runs unscoped ----------------------------------------------


@pytest.mark.django_db
def test_a_scopeable_model_refuses_to_query_without_a_scope():
    """The property everything else rests on."""
    with pytest.raises(ScopeNotSet):
        list(Project.objects.all())
    with pytest.raises(ScopeNotSet):
        list(Gig.objects.all())


@pytest.mark.django_db
def test_counts_and_existence_checks_are_scoped_too():
    """`count()` and `exists()` bypass any filtering bolted on at the view."""
    with pytest.raises(ScopeNotSet):
        Project.objects.count()
    with pytest.raises(ScopeNotSet):
        Project.objects.exists()
    with pytest.raises(ScopeNotSet):
        Project.objects.first()


@pytest.mark.django_db
def test_escaping_the_scope_requires_saying_so(comsats, category):
    owner = make_student("owner@example.com", comsats)
    make_project(owner, category, "Campus brief", comsats)

    # The escape hatch works, and is greppable. That is the whole design.
    assert Project.objects.unscoped().count() == 1


# --- 2. No leakage between surfaces ----------------------------------------


@pytest.mark.django_db
def test_a_campus_brief_never_appears_in_the_global_marketplace(comsats, category):
    student = make_student("student@example.com", comsats)
    make_project(student, category, "Campus only brief", comsats)
    make_project(student, category, "Open to everyone", None)

    outsider = make_student("outsider@example.com", None)
    listed = sign_in(outsider).get("/api/v1/projects/").data
    titles = [row["title"] for row in listed["results"]]

    assert "Open to everyone" in titles
    assert "Campus only brief" not in titles
    # The count must agree with the rows. A post-filtered list leaks existence
    # through the total even when the row itself is withheld.
    assert listed["count"] == 1


@pytest.mark.django_db
def test_one_campus_never_sees_another(comsats, fast, category):
    cui_student = make_student("cui@example.com", comsats)
    fast_student = make_student("fast@example.com", fast)

    make_project(cui_student, category, "CUI poster design", comsats)
    make_project(fast_student, category, "FAST thesis help", fast)

    listed = sign_in(fast_student, "university").get("/api/v1/projects/").data
    titles = [row["title"] for row in listed["results"]]

    assert titles == ["FAST thesis help"]
    assert listed["count"] == 1


@pytest.mark.django_db
def test_a_campus_gig_never_appears_in_the_global_catalogue(comsats, category):
    seller = make_student("seller@example.com", comsats)
    with use_scope(Scope(SurfaceKind.UNIVERSITY, comsats.pk)):
        Gig.objects.create(
            seller=seller,
            title="I will design campus posters",
            description="For CUI societies.",
            status=Gig.Status.ACTIVE,
            visibility=Visibility.UNIVERSITY,
            university=comsats,
        )

    outsider = make_student("browser@example.com", None)
    listed = sign_in(outsider).get("/api/v1/gigs/").data
    assert listed["count"] == 0


@pytest.mark.django_db
def test_the_detail_route_does_not_leak_what_the_list_hides(comsats, category):
    """The classic miss: the list is filtered, the retrieve-by-id is not."""
    student = make_student("student@example.com", comsats)
    hidden = make_project(student, category, "Campus only brief", comsats)

    outsider = make_student("outsider@example.com", None)
    response = sign_in(outsider).get(f"/api/v1/projects/{hidden.pk}/")

    # 404 rather than 403: a 403 confirms the row exists, which is itself the
    # leak on a surface the caller cannot see.
    assert response.status_code == 404


@pytest.mark.django_db
def test_search_and_filters_cannot_be_used_to_probe_other_surfaces(comsats, category):
    """Filtering must run *after* the scope pre-filter, never instead of it."""
    student = make_student("student@example.com", comsats)
    make_project(student, category, "Secret campus robotics project", comsats)

    outsider = make_student("outsider@example.com", None)
    client = sign_in(outsider)

    for query in ("?q=robotics", "?q=Secret", f"?category={category.pk}", "?ordering=-created_at"):
        listed = client.get(f"/api/v1/projects/{query}").data
        assert listed["count"] == 0, f"leaked through {query}"


@pytest.mark.django_db
def test_a_student_on_the_global_surface_does_not_see_their_own_campus_content(comsats, category):
    """Surface is where you are standing, not who you are.

    A student browsing the global marketplace must see exactly what a
    non-student sees, or the two surfaces are not actually separate and every
    screenshot they share leaks campus content.
    """
    student = make_student("student@example.com", comsats)
    make_project(student, category, "Campus only brief", comsats)
    make_project(student, category, "Open to everyone", None)

    listed = sign_in(student).get("/api/v1/projects/").data
    assert [row["title"] for row in listed["results"]] == ["Open to everyone"]


# --- 3. Entitlement cannot be escalated ------------------------------------


@pytest.mark.django_db
def test_an_unverified_user_cannot_request_a_university_surface(comsats):
    nobody = make_student("nobody@example.com", None)
    response = sign_in(nobody, "university").get("/api/v1/projects/")
    assert response.status_code == 403
    assert response.data["code"] == "scope_denied"


@pytest.mark.django_db
def test_an_anonymous_caller_cannot_request_a_university_surface():
    client = APIClient()
    client.credentials(**{SURFACE_HEADER: "university"})
    assert client.get("/api/v1/projects/").status_code == 403


@pytest.mark.django_db
def test_an_unknown_surface_is_refused_rather_than_ignored(comsats):
    """Silently falling back to global would hide a probe."""
    student = make_student("student@example.com", comsats)
    assert sign_in(student, "admin").get("/api/v1/projects/").status_code == 403
    assert sign_in(student, "university:999").get("/api/v1/projects/").status_code == 403


@pytest.mark.django_db
def test_a_student_is_pinned_to_their_own_university(comsats, fast):
    """The header names a *kind*, never an id — but assert it anyway."""
    cui_student = make_student("cui@example.com", comsats)
    scope = resolve_for(cui_student, "university")
    assert scope.university_id == comsats.pk

    with pytest.raises(ScopeDenied):
        resolve_for(cui_student, "university", university_id=fast.pk)


@pytest.mark.django_db
def test_revoking_verification_closes_the_portal_immediately(comsats, category):
    student = make_student("student@example.com", comsats)
    make_project(student, category, "Campus only brief", comsats)

    assert sign_in(student, "university").get("/api/v1/projects/").data["count"] == 1

    # Graduated, or approved in error.
    student.student_verification_status = VerificationStatus.REJECTED
    student.save(update_fields=["student_verification_status"])

    assert sign_in(student, "university").get("/api/v1/projects/").status_code == 403


@pytest.mark.django_db
def test_a_rejection_revokes_an_already_granted_portal(comsats):
    from accounts.models import StudentVerification

    student = make_student("student@example.com", None)
    application = StudentVerification.objects.create(
        user=student, university=comsats, university_email="s@cui.edu.pk"
    )
    application.approve()
    student.refresh_from_db()
    assert student.is_verified_student

    application.reject("Card did not match.")
    student.refresh_from_db()
    assert not student.is_verified_student
    assert student.university_id is None


# --- 4. The gate defends itself --------------------------------------------


def _scoped_models() -> list[type]:
    """Every concrete model that inherits tenancy."""
    from django.apps import apps

    return [
        model
        for model in apps.get_models()
        if issubclass(model, ScopedModel) and not model._meta.abstract
    ]


@pytest.mark.django_db
def test_every_scoped_model_refuses_an_unscoped_query():
    """Applies the core property to every scopeable model automatically.

    A model added later inherits this test for free. That matters more than it
    looks: the failure mode being defended against is a developer adding a
    scopeable model and simply not thinking about tenancy, and a test they have
    to remember to write does not defend against that.
    """
    models = _scoped_models()
    assert models, "no scoped models discovered — the check itself is broken"

    for model in models:
        with pytest.raises(ScopeNotSet, match=r"scopeable"):
            model.objects.count()


@pytest.mark.django_db
def test_every_scoped_model_filters_by_surface():
    """And that the filter actually discriminates, not merely that it runs."""
    for model in _scoped_models():
        with use_scope(GLOBAL_SCOPE):
            sql = str(model.objects.all().query)
        assert "visibility" in sql, f"{model.__name__} does not filter on visibility"

        with use_scope(Scope(SurfaceKind.UNIVERSITY, 1)):
            sql = str(model.objects.all().query)
        assert "university_id" in sql, f"{model.__name__} does not filter on university"


@pytest.mark.django_db
def test_the_unrestricted_scope_is_the_only_way_to_see_everything(comsats, fast, category):
    cui = make_student("cui@example.com", comsats)
    fast_student = make_student("fast@example.com", fast)
    make_project(cui, category, "CUI brief", comsats)
    make_project(fast_student, category, "FAST brief", fast)
    make_project(cui, category, "Global brief", None)

    with use_scope(GLOBAL_SCOPE):
        assert Project.objects.count() == 1
    with use_scope(Scope(SurfaceKind.UNIVERSITY, comsats.pk)):
        assert Project.objects.count() == 1
    with use_scope(UNRESTRICTED_SCOPE):
        assert Project.objects.count() == 3


@pytest.mark.django_db
def test_scoped_content_cannot_be_created_in_an_inconsistent_state(comsats):
    """A row that claims one surface while carrying another's key would be
    invisible to both and reachable by accident from either."""
    from django.core.exceptions import ValidationError

    orphan = Project(
        client=make_student("a@example.com", comsats),
        title="Campus brief with no university",
        description="x" * 120,
        project_type=ProjectType.FIXED,
        visibility=Visibility.UNIVERSITY,
        university=None,
    )
    with pytest.raises(ValidationError):
        orphan.clean()

    mislabelled = Project(
        client=make_student("b@example.com", comsats),
        title="Global brief carrying a university",
        description="x" * 120,
        project_type=ProjectType.FIXED,
        visibility=Visibility.GLOBAL,
        university=comsats,
    )
    with pytest.raises(ValidationError):
        mislabelled.clean()
