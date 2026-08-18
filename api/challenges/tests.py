"""
Tests for proof-of-work challenges.

The rules worth guarding: a deadline that can be submitted past, an SSRF
guard that lets a submission reach internal infrastructure, and percentile
math that awards the wrong badge — each of those is either a security hole or
a false "VERIFIED SKILL" claim on somebody's profile.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from marketplace.tests import make_user, sign_in

from .models import Badge, Challenge, Participation, finalize_challenge
from .url_safety import UnsafeURLError, assert_safe_url


def make_challenge(
    *, automated_weight=50, duration_hours=24, closes_in_hours=168, **extra
) -> Challenge:
    author = extra.pop("created_by", None) or make_user(
        f"author{Challenge.objects.count()}@example.com", is_staff=True
    )
    return Challenge.objects.create(
        title=extra.pop("title", "Build a responsive dashboard"),
        brief=extra.pop("brief", "Recreate the attached Figma file, mobile-first."),
        duration_hours=duration_hours,
        automated_weight=automated_weight,
        status=extra.pop("status", Challenge.Status.PUBLISHED),
        opens_at=timezone.now() - timedelta(hours=1),
        closes_at=timezone.now() + timedelta(hours=closes_in_hours),
        created_by=author,
        **extra,
    )


# --- URL safety --------------------------------------------------------------


def test_unsafe_url_rejects_non_http_scheme():
    with pytest.raises(UnsafeURLError):
        assert_safe_url("ftp://8.8.8.8/")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://0.0.0.0/",
    ],
)
def test_unsafe_url_rejects_private_and_loopback_addresses(url):
    with pytest.raises(UnsafeURLError):
        assert_safe_url(url)


def test_unsafe_url_accepts_a_public_address():
    # An IP literal, not a hostname — resolved with no real DNS lookup, so
    # this test has no network dependency. Success is simply not raising.
    assert_safe_url("http://8.8.8.8/")


def test_unsafe_url_rejects_credentials_in_the_url():
    with pytest.raises(UnsafeURLError):
        assert_safe_url("http://user:pass@8.8.8.8/")


# --- Join / submit lifecycle --------------------------------------------------


@pytest.mark.django_db
def test_joining_creates_a_deadline_capped_at_challenge_close():
    """A 24-hour challenge joined nine days into a ten-day open window should
    not hand out a deadline past when the challenge itself closes."""
    challenge = make_challenge(duration_hours=24, closes_in_hours=1)
    user = make_user("joiner@example.com")
    client = sign_in(user)

    response = client.post(f"/api/v1/challenges/{challenge.slug}/join/")
    assert response.status_code == 201
    participation = Participation.objects.get(challenge=challenge, user=user)
    assert participation.deadline <= challenge.closes_at


@pytest.mark.django_db
def test_cannot_join_twice():
    challenge = make_challenge()
    user = make_user("repeat@example.com")
    client = sign_in(user)

    client.post(f"/api/v1/challenges/{challenge.slug}/join/")
    response = client.post(f"/api/v1/challenges/{challenge.slug}/join/")
    assert response.status_code == 400
    assert response.data["code"] == "already_joined"


@pytest.mark.django_db
def test_cannot_join_a_closed_challenge():
    challenge = make_challenge(closes_in_hours=-1)
    user = make_user("late@example.com")
    client = sign_in(user)

    response = client.post(f"/api/v1/challenges/{challenge.slug}/join/")
    assert response.status_code == 400
    assert response.data["code"] == "challenge_closed"


@pytest.mark.django_db
def test_submitting_after_the_deadline_is_rejected():
    challenge = make_challenge()
    user = make_user("overdue@example.com")
    participation = Participation.objects.create(
        challenge=challenge, user=user, deadline=timezone.now() - timedelta(minutes=1)
    )
    client = sign_in(user)

    response = client.post(
        f"/api/v1/challenges/{challenge.slug}/submit/",
        {"submission_url": "https://example-deploy.vercel.app/"},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "submission_rejected"
    participation.refresh_from_db()
    assert participation.status == Participation.Status.IN_PROGRESS


@pytest.mark.django_db
def test_submitting_an_unsafe_url_is_rejected_at_the_api():
    """The same guard that protects `grade_url` also runs synchronously at
    submission time, so a participant gets an immediate, honest error instead
    of a submission that silently never gets graded."""
    challenge = make_challenge()
    user = make_user("ssrf-try@example.com")
    Participation.objects.create(
        challenge=challenge, user=user, deadline=timezone.now() + timedelta(hours=1)
    )
    client = sign_in(user)

    response = client.post(
        f"/api/v1/challenges/{challenge.slug}/submit/",
        {"submission_url": "http://169.254.169.254/latest/meta-data/iam/security-credentials/"},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "unsafe_url"


# --- Scoring -------------------------------------------------------------


@pytest.mark.django_db
def test_human_only_challenge_finalizes_on_review_alone():
    challenge = make_challenge(automated_weight=0)
    user = make_user("human-graded@example.com")
    reviewer = make_user("reviewer@example.com", is_staff=True)
    participation = Participation.objects.create(
        challenge=challenge, user=user, deadline=timezone.now() + timedelta(hours=1)
    )
    participation.submit(submission_url="https://example-deploy.vercel.app/")
    assert participation.automated_status == Participation.AutomatedStatus.UNAVAILABLE

    participation.apply_human_review(
        score=88, notes="Clean, accessible, on brief.", reviewer=reviewer
    )
    participation.refresh_from_db()
    assert participation.status == Participation.Status.GRADED
    assert participation.final_score == 88


@pytest.mark.django_db
def test_automated_grading_records_unavailable_when_lighthouse_is_off(settings):
    """LIGHTHOUSE_ENABLED is off by default (D33) — this is the expected,
    everyday path, not a failure."""
    settings.LIGHTHOUSE_ENABLED = False
    challenge = make_challenge(automated_weight=100)
    user = make_user("auto-only@example.com")
    participation = Participation.objects.create(
        challenge=challenge, user=user, deadline=timezone.now() + timedelta(hours=1)
    )
    participation.submit(submission_url="https://example-deploy.vercel.app/")

    from core.tasks import grade_challenge_submission

    grade_challenge_submission(participation.id)

    participation.refresh_from_db()
    assert participation.automated_status == Participation.AutomatedStatus.UNAVAILABLE
    # Nothing to average against a human score that will never come on a
    # fully-automated challenge with no scorer configured — this attempt
    # simply never finalizes, which is honest: it was never actually graded.
    assert participation.status == Participation.Status.SUBMITTED
    assert participation.final_score is None


@pytest.mark.django_db
def test_weighted_score_combines_both_sides():
    challenge = make_challenge(automated_weight=50)
    user = make_user("both-graded@example.com")
    reviewer = make_user("reviewer2@example.com", is_staff=True)
    participation = Participation.objects.create(
        challenge=challenge, user=user, deadline=timezone.now() + timedelta(hours=1)
    )
    participation.submit(submission_url="https://example-deploy.vercel.app/")
    participation.apply_automated_result(
        status=Participation.AutomatedStatus.COMPLETE, score=80, report={"performance": 80}
    )
    participation.apply_human_review(score=60, notes="Works, rough edges.", reviewer=reviewer)

    participation.refresh_from_db()
    assert participation.status == Participation.Status.GRADED
    assert participation.final_score == 70  # (80 * 0.5) + (60 * 0.5)


# --- Finalize, ranking, badges ------------------------------------------------


@pytest.mark.django_db
def test_finalize_ranks_participants_and_awards_badges():
    challenge = make_challenge(automated_weight=0)
    reviewer = make_user("ranker@example.com", is_staff=True)
    scores = [95, 80, 60, 40, 20, 10, 5, 3, 2, 1]  # 10 participants
    participations = []
    for i, score in enumerate(scores):
        user = make_user(f"contestant{i}@example.com")
        participation = Participation.objects.create(
            challenge=challenge, user=user, deadline=timezone.now() + timedelta(hours=1)
        )
        participation.submit(submission_url="https://example-deploy.vercel.app/")
        participation.apply_human_review(score=score, notes="", reviewer=reviewer)
        participations.append(participation)

    awarded = finalize_challenge(challenge)
    assert awarded == 10

    challenge.refresh_from_db()
    assert challenge.status == Challenge.Status.COMPLETED

    winner_badge = Badge.objects.get(participation=participations[0])
    assert winner_badge.top_percent == 10  # rank 1 of 10
    assert winner_badge.label == "Top 10%"

    last_badge = Badge.objects.get(participation=participations[-1])
    assert last_badge.top_percent == 100  # rank 10 of 10


@pytest.mark.django_db
def test_finalize_is_idempotent():
    challenge = make_challenge(automated_weight=0)
    reviewer = make_user("idempotent-reviewer@example.com", is_staff=True)
    user = make_user("solo@example.com")
    participation = Participation.objects.create(
        challenge=challenge, user=user, deadline=timezone.now() + timedelta(hours=1)
    )
    participation.submit(submission_url="https://example-deploy.vercel.app/")
    participation.apply_human_review(score=70, notes="", reviewer=reviewer)

    finalize_challenge(challenge)
    finalize_challenge(challenge)  # must not raise or duplicate

    assert Badge.objects.filter(participation=participation).count() == 1


@pytest.mark.django_db
def test_a_challenge_with_no_graded_submissions_still_completes():
    challenge = make_challenge()
    assert finalize_challenge(challenge) == 0
    challenge.refresh_from_db()
    assert challenge.status == Challenge.Status.COMPLETED


# --- Permissions ---------------------------------------------------------


@pytest.mark.django_db
def test_only_staff_can_create_a_challenge():
    user = make_user("not-staff@example.com")
    client = sign_in(user)

    response = client.post(
        "/api/v1/challenges/",
        {
            "title": "Sneaky challenge",
            "brief": "...",
            "duration_hours": 24,
            "automated_weight": 50,
            "status": "published",
            "opens_at": timezone.now().isoformat(),
            "closes_at": (timezone.now() + timedelta(days=7)).isoformat(),
        },
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_staff_can_create_a_challenge():
    staff = make_user("staff-creator@example.com", is_staff=True)
    client = sign_in(staff)

    response = client.post(
        "/api/v1/challenges/",
        {
            "title": "React Dashboard Challenge",
            "brief": "Build a responsive dashboard from the attached Figma file.",
            "duration_hours": 24,
            "automated_weight": 50,
            "status": "published",
            "opens_at": timezone.now().isoformat(),
            "closes_at": (timezone.now() + timedelta(days=7)).isoformat(),
        },
        format="json",
    )
    assert response.status_code == 201
    assert Challenge.objects.get(pk=response.data["id"]).created_by == staff


@pytest.mark.django_db
def test_only_staff_can_review_submissions():
    challenge = make_challenge()
    user = make_user("reviewer-imposter@example.com")
    other = make_user("attempt-owner@example.com")
    participation = Participation.objects.create(
        challenge=challenge, user=other, deadline=timezone.now() + timedelta(hours=1)
    )
    client = sign_in(user)

    response = client.post(
        f"/api/v1/challenges/{challenge.slug}/submissions/{participation.id}/review/",
        {"score": 100},
        format="json",
    )
    assert response.status_code == 403


# --- Profile display -------------------------------------------------------


@pytest.mark.django_db
def test_badge_appears_on_public_profile():
    challenge = make_challenge(automated_weight=0)
    reviewer = make_user("profile-reviewer@example.com", is_staff=True)
    user = make_user("badge-holder@example.com")
    participation = Participation.objects.create(
        challenge=challenge, user=user, deadline=timezone.now() + timedelta(hours=1)
    )
    participation.submit(submission_url="https://example-deploy.vercel.app/")
    participation.apply_human_review(score=90, notes="", reviewer=reviewer)
    finalize_challenge(challenge)

    client = sign_in(make_user("visitor@example.com"))
    response = client.get(f"/api/v1/auth/users/{user.handle}/")
    assert response.status_code == 200
    badges = response.data["badges"]
    assert len(badges) == 1
    assert badges[0]["challenge_title"] == challenge.title
    assert badges[0]["label"] == "Top 100%"  # sole participant
