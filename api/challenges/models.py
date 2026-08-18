"""
Proof-of-work challenges: timed skill briefs, graded, and badged onto a
profile — Phase 13.

**What this deliberately does not do:** grade freelancer-submitted *source
code*. Running arbitrary submitted code server-side needs real sandboxing
(gVisor, Firecracker, Docker-in-Docker) and is its own infrastructure project,
comparable in risk to Phase 3's payment rails — not something to bolt onto a
Celery task. What is buildable without that risk, and what this app does
instead: a freelancer submits a **live deployed URL**, automated grading runs
Lighthouse against that public page (a page fetch, not code execution), and a
human reviewer scores it on a rubric. Both feed a weighted final score, and
the ranking across a challenge's participants is what becomes the badge.

Percentile ranking needs (most of) a challenge's field graded before it means
anything, so a challenge has two clocks: `closes_at`, the enrolment/submission
window for everyone, and each `Participation.deadline`, an individual clock
that starts the moment a freelancer joins. `sweep_challenge_deadlines`
(`core.tasks`) expires anyone who ran out of time and finalises challenges
whose window has closed.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from core.models import TimestampedModel


class Challenge(TimestampedModel):
    """A published brief. Authored by staff, not by freelancers or clients."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    brief = models.TextField()
    skill = models.ForeignKey(
        "marketplace.Skill", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    #: Reference material — a Figma export, a spec PDF. Optional; briefs that
    #: are self-contained text need nothing here.
    reference_file = models.ForeignKey(
        "core.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    #: How long a participant has to submit, counted from when *they* join —
    #: not a fixed clock everyone races against, so joining on day six of an
    #: open week is not a worse deal than joining on day one.
    duration_hours = models.PositiveSmallIntegerField(default=24)
    #: Weight given to the automated (Lighthouse) score, 0-100; the rest goes
    #: to human review. 0 means fully human-reviewed — the honest setting for
    #: any challenge run before Lighthouse is actually wired into deploy
    #: infrastructure (`LIGHTHOUSE_ENABLED`, off by default; see D33).
    automated_weight = models.PositiveSmallIntegerField(default=50)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    opens_at = models.DateTimeField(default=timezone.now)
    #: No new joins and no submissions after this, regardless of an
    #: individual's own deadline.
    closes_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="challenges_authored"
    )

    class Meta:
        ordering = ["-opens_at"]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        if self.automated_weight > 100:
            raise ValidationError({"automated_weight": "Cannot exceed 100."})
        if self.closes_at and self.opens_at and self.closes_at <= self.opens_at:
            raise ValidationError({"closes_at": "Must be after the opening time."})

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:160] or "challenge"
            candidate, suffix = base, 2
            while Challenge.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{suffix}"
                suffix += 1
            self.slug = candidate
        return super().save(*args, **kwargs)

    @property
    def is_open(self) -> bool:
        now = timezone.now()
        return self.status == self.Status.PUBLISHED and self.opens_at <= now < self.closes_at

    @property
    def human_weight(self) -> int:
        return 100 - self.automated_weight

    @property
    def participant_count(self) -> int:
        return self.participations.count()

    @property
    def graded_count(self) -> int:
        return self.participations.filter(status=Participation.Status.GRADED).count()


class Participation(TimestampedModel):
    """One freelancer's attempt at one challenge. No retries in v1 — a second
    attempt at the same brief is a different product decision (do you keep the
    better score? the later one?) than this needs to answer yet."""

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        SUBMITTED = "submitted", "Submitted"
        GRADED = "graded", "Graded"
        EXPIRED = "expired", "Expired"

    class AutomatedStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"
        #: `LIGHTHOUSE_ENABLED` is off, or the fetch was refused by the SSRF
        #: guard. Distinct from FAILED — a challenge with `automated_weight`
        #: at 0 for exactly this reason should never look like a bug.
        UNAVAILABLE = "unavailable", "Unavailable"

    challenge = models.ForeignKey(
        Challenge, on_delete=models.CASCADE, related_name="participations"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="challenge_participations"
    )
    started_at = models.DateTimeField(default=timezone.now)
    deadline = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_PROGRESS)

    # --- Submission ---
    submission_url = models.URLField(max_length=500, blank=True)
    repo_url = models.URLField(max_length=500, blank=True)
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    # --- Automated grading ---
    automated_status = models.CharField(
        max_length=12, choices=AutomatedStatus.choices, default=AutomatedStatus.PENDING
    )
    automated_score = models.PositiveSmallIntegerField(null=True, blank=True)
    #: Raw Lighthouse category scores, kept for the freelancer to actually see
    #: *what* moved the number rather than just the number itself.
    automated_report = models.JSONField(default=dict, blank=True)
    automated_graded_at = models.DateTimeField(null=True, blank=True)

    # --- Human review ---
    human_score = models.PositiveSmallIntegerField(null=True, blank=True)
    human_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # --- Result ---
    final_score = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(fields=["challenge", "user"], name="one_attempt_per_user")
        ]
        indexes = [models.Index(fields=["status", "deadline"])]

    def __str__(self) -> str:
        return f"{self.user_id} on {self.challenge_id} ({self.status})"

    @property
    def is_overdue(self) -> bool:
        return self.status == self.Status.IN_PROGRESS and timezone.now() > self.deadline

    @property
    def needs_automated_grading(self) -> bool:
        return self.challenge.automated_weight > 0

    @property
    def needs_human_review(self) -> bool:
        return self.challenge.human_weight > 0

    def submit(self, *, submission_url: str, repo_url: str = "", notes: str = "") -> None:
        if self.status != self.Status.IN_PROGRESS:
            raise ValidationError("This attempt has already been submitted.")
        if timezone.now() > self.deadline:
            raise ValidationError("The deadline for this attempt has passed.")

        self.submission_url = submission_url
        self.repo_url = repo_url
        self.notes = notes
        self.submitted_at = timezone.now()
        self.status = self.Status.SUBMITTED
        if not self.needs_automated_grading:
            self.automated_status = self.AutomatedStatus.UNAVAILABLE
        self.save(
            update_fields=[
                "submission_url",
                "repo_url",
                "notes",
                "submitted_at",
                "status",
                "automated_status",
                "updated_at",
            ]
        )
        self._maybe_finalize_score()

    def apply_automated_result(
        self, *, status: str, score: int | None = None, report: dict | None = None
    ) -> None:
        self.automated_status = status
        self.automated_score = score
        self.automated_report = report or {}
        self.automated_graded_at = timezone.now()
        self.save(
            update_fields=[
                "automated_status",
                "automated_score",
                "automated_report",
                "automated_graded_at",
                "updated_at",
            ]
        )
        self._maybe_finalize_score()

    def apply_human_review(self, *, score: int, notes: str, reviewer) -> None:
        if not (0 <= score <= 100):
            raise ValidationError({"score": "Must be between 0 and 100."})
        self.human_score = score
        self.human_notes = notes
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save(
            update_fields=[
                "human_score",
                "human_notes",
                "reviewed_by",
                "reviewed_at",
                "updated_at",
            ]
        )
        self._maybe_finalize_score()

    def _maybe_finalize_score(self) -> None:
        """Combine automated and human scores once both sides that matter are in.

        A side "matters" when its weight is nonzero, or when it resolved to
        something other than pending/running (so an UNAVAILABLE automated leg
        on a 50/50 challenge does not block a human-graded result forever —
        the weight silently shifts to whichever side actually produced a
        number, rather than stalling the whole submission).
        """
        if self.status not in (self.Status.SUBMITTED, self.Status.GRADED):
            return

        auto_ready = (not self.needs_automated_grading) or self.automated_status in (
            self.AutomatedStatus.COMPLETE,
            self.AutomatedStatus.FAILED,
            self.AutomatedStatus.UNAVAILABLE,
        )
        human_ready = (not self.needs_human_review) or self.human_score is not None
        if not (auto_ready and human_ready):
            return

        has_auto = (
            self.automated_status == self.AutomatedStatus.COMPLETE
            and self.automated_score is not None
        )
        has_human = self.human_score is not None

        if has_auto and has_human:
            weight = self.challenge.automated_weight
            score = round(
                self.automated_score * weight / 100 + self.human_score * (100 - weight) / 100
            )
        elif has_auto:
            score = self.automated_score
        elif has_human:
            score = self.human_score
        else:
            # Neither side produced a usable number — nothing to finalize.
            return

        self.final_score = score
        self.status = self.Status.GRADED
        self.save(update_fields=["final_score", "status", "updated_at"])


class Badge(TimestampedModel):
    """The 'VERIFIED SKILL' mark on a profile. One per user per challenge,
    created only once its challenge has been finalised and ranked."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="challenge_badges"
    )
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="badges")
    participation = models.OneToOneField(
        Participation, on_delete=models.CASCADE, related_name="badge"
    )
    final_score = models.PositiveSmallIntegerField()
    #: 8 means "top 8%" — rank 1 of N scales to 100/N, rounded up, never 0.
    top_percent = models.PositiveSmallIntegerField()
    awarded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-awarded_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "challenge"], name="one_badge_per_user_per_challenge"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id}: Top {self.top_percent}% on {self.challenge_id}"

    @property
    def label(self) -> str:
        return f"Top {self.top_percent}%"


def finalize_challenge(challenge: Challenge) -> int:
    """Rank every graded participation and award badges. Idempotent — safe to
    call again if a late human review lands after the first pass (that
    participation is simply not among the graded set yet, so the ranking
    already excludes it; re-running after it grades re-ranks everyone).

    Returns the number of badges awarded or updated.
    """
    graded = list(
        challenge.participations.filter(status=Participation.Status.GRADED).order_by(
            "-final_score", "submitted_at"
        )
    )
    total = len(graded)
    if total == 0:
        challenge.status = Challenge.Status.COMPLETED
        challenge.save(update_fields=["status", "updated_at"])
        return 0

    awarded = 0
    for rank, participation in enumerate(graded, start=1):
        top_percent = max(1, round(100 * rank / total))
        Badge.objects.update_or_create(
            participation=participation,
            defaults={
                "user": participation.user,
                "challenge": challenge,
                "final_score": participation.final_score,
                "top_percent": top_percent,
                "awarded_at": timezone.now(),
            },
        )
        awarded += 1

    challenge.status = Challenge.Status.COMPLETED
    challenge.save(update_fields=["status", "updated_at"])
    return awarded
