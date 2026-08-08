"""
Track A — projects and bidding.

A client describes what they need, freelancers compete with proposals, the
client selects, and work proceeds under a contract (which lives in the
``contracts`` app). This is the harder of the two marketplace models and the
one that proves the core loop, which is why the report sequences it first.

Everything here inherits ``ScopedModel``: a project posted inside a university
portal is invisible to the global marketplace and to every other university,
enforced at the data layer rather than remembered per-view.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from core.models import ScopedModel, TimestampedModel

# --- Taxonomy --------------------------------------------------------------


class Category(TimestampedModel):
    """Two levels: a top-level category and its subcategories.

    Browse pages built on these are the primary organic search-engine landing
    pages (Section 13.4), so the slug is a durable, public-facing identifier.
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    #: Key into the client-side icon set; the API never ships markup.
    icon = models.CharField(max_length=40, blank=True)
    description = models.CharField(max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return f"{self.parent.name} › {self.name}" if self.parent_id else self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:120]
        return super().save(*args, **kwargs)


class Skill(TimestampedModel):
    """A controlled vocabulary that drives search matching and recommendations.

    Free-text additions are allowed but land unapproved, so they surface to
    admins for taxonomy expansion rather than silently fragmenting the index
    (Section 8.2).
    """

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="skills"
    )
    is_approved = models.BooleanField(default=True)
    usage_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-usage_count", "name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:100]
        return super().save(*args, **kwargs)


# --- Projects --------------------------------------------------------------


class ProjectType(models.TextChoices):
    FIXED = "fixed", "Fixed price"
    HOURLY = "hourly", "Hourly"


class ExperienceLevel(models.TextChoices):
    ENTRY = "entry", "Entry level"
    INTERMEDIATE = "intermediate", "Intermediate"
    EXPERT = "expert", "Expert"


class ProjectSize(models.TextChoices):
    SMALL = "small", "Small"
    MEDIUM = "medium", "Medium"
    LARGE = "large", "Large"


class Project(ScopedModel):
    """A client's brief, open for proposals."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open for proposals"
        PAUSED = "paused", "Paused"
        CLOSED = "closed", "Closed"
        AWARDED = "awarded", "Awarded"

    class Listing(models.TextChoices):
        PUBLIC = "public", "Public"
        INVITE_ONLY = "invite_only", "Invite only"

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="projects"
    )
    skills = models.ManyToManyField(Skill, blank=True, related_name="projects")

    project_type = models.CharField(
        max_length=10, choices=ProjectType.choices, default=ProjectType.FIXED
    )
    #: Fixed-price budget.
    budget_min = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    budget_max = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    #: Hourly range and expected commitment.
    rate_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rate_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    weekly_hours = models.PositiveSmallIntegerField(null=True, blank=True)

    size = models.CharField(max_length=10, choices=ProjectSize.choices, default=ProjectSize.MEDIUM)
    expected_duration_days = models.PositiveIntegerField(null=True, blank=True)
    experience_level = models.CharField(
        max_length=14, choices=ExperienceLevel.choices, default=ExperienceLevel.INTERMEDIATE
    )

    attachments = models.ManyToManyField("core.StoredFile", blank=True, related_name="+")

    listing = models.CharField(max_length=12, choices=Listing.choices, default=Listing.PUBLIC)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)

    # Optional preferences. None of these hard-filter proposals; they inform
    # ranking and let a client state what they are looking for up front.
    preferred_country = models.CharField(max_length=2, blank=True)
    preferred_language = models.CharField(max_length=8, blank=True)
    min_job_success_score = models.PositiveSmallIntegerField(null=True, blank=True)
    verified_students_only = models.BooleanField(default=False)

    #: Denormalised so a list of 50 projects does not become 50 count queries.
    proposal_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    #: See the note on `gigs.Gig.search_vector` — same reasoning, same upkeep.
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"]),
            models.Index(fields=["visibility", "university", "status"]),
            GinIndex(fields=["search_vector"], name="project_search_vector_gin"),
            GinIndex(
                name="project_title_trigram",
                fields=["title"],
                opclasses=["gin_trgm_ops"],
            ),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        result = super().save(*args, **kwargs)
        # See the note on `gigs.Gig.save` — same reasoning: the vector is built
        # by Postgres from the stored row, and a counter bump must not trigger
        # a rebuild.
        indexed_fields = {"title", "description", "category", "experience_level"}
        touched = kwargs.get("update_fields")
        if touched is None or indexed_fields & set(touched):
            from core.indexing import reindex_project

            reindex_project(self.pk)
        return result

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.OPEN

    @property
    def budget_display(self) -> str:
        if self.project_type == ProjectType.HOURLY:
            if self.rate_min and self.rate_max:
                return f"{self.rate_min:.0f}–{self.rate_max:.0f} / hr"
            return f"{self.rate_min or self.rate_max or 0:.0f} / hr"
        if self.budget_min and self.budget_max and self.budget_min != self.budget_max:
            return f"{self.budget_min:.0f}–{self.budget_max:.0f}"
        return f"{self.budget_max or self.budget_min or 0:.0f}"

    def publish(self) -> None:
        self.status = self.Status.OPEN
        self.published_at = self.published_at or timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])

    def close(self) -> None:
        self.status = self.Status.CLOSED
        self.closed_at = timezone.now()
        self.save(update_fields=["status", "closed_at", "updated_at"])

    def accepts_proposal_from(self, user) -> tuple[bool, str]:
        """Whether ``user`` may bid, and why not if they may not."""
        if not self.is_open:
            return False, "This project is not accepting proposals."
        if self.client_id == user.pk:
            return False, "You cannot submit a proposal to your own project."
        if not user.can_transact:
            return False, "Complete your profile before submitting proposals."
        if self.verified_students_only and not user.is_verified_student:
            return False, "This project is open to verified students only."
        if (
            self.proposals.filter(freelancer=user)
            .exclude(status=Proposal.Status.WITHDRAWN)
            .exists()
        ):
            return False, "You have already submitted a proposal to this project."
        return True, ""


class ScreeningQuestion(TimestampedModel):
    """A question the client writes that every applicant must answer.

    Section 10.1 notes this alone filters out most low-effort proposals, which
    is why it is a first-class field rather than something clients improvise in
    the description.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="screening_questions"
    )
    text = models.CharField(max_length=300)
    order = models.PositiveSmallIntegerField(default=0)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.text[:60]


# --- Proposals -------------------------------------------------------------


class Proposal(TimestampedModel):
    """A freelancer's bid on a project."""

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        SHORTLISTED = "shortlisted", "Shortlisted"
        DECLINED = "declined", "Declined"
        WITHDRAWN = "withdrawn", "Withdrawn"
        ACCEPTED = "accepted", "Accepted"

    #: Free-plan ceiling on *outstanding* proposals (decision D6). A completed,
    #: declined, or withdrawn proposal frees its slot immediately.
    FREE_PLAN_QUOTA = 30
    FREE_PLAN_STUDENT_QUOTA = 50

    #: Section 10.2: a submitted proposal may be edited briefly, then it is
    #: fixed — otherwise a client's shortlist means nothing.
    EDIT_WINDOW_MINUTES = 30

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="proposals")
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="proposals"
    )
    cover_letter = models.TextField()
    #: Whichever of these applies is decided by the project's own type.
    bid_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_days = models.PositiveIntegerField(null=True, blank=True)

    #: An optional milestone plan. If the client accepts, this becomes the
    #: contract's structure verbatim.
    proposed_milestones = models.JSONField(default=list, blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SUBMITTED)
    #: Paid placement at the top of the client's list, always labelled as such.
    is_boosted = models.BooleanField(default=False)
    client_viewed_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-is_boosted", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "freelancer"], name="one_proposal_per_freelancer_per_project"
            )
        ]

    def __str__(self) -> str:
        return f"Proposal by {self.freelancer_id} on {self.project_id}"

    @property
    def is_outstanding(self) -> bool:
        """Counts against the quota until it is resolved either way."""
        return self.status in (self.Status.SUBMITTED, self.Status.SHORTLISTED)

    @property
    def is_editable(self) -> bool:
        if self.status != self.Status.SUBMITTED:
            return False
        age = (timezone.now() - self.created_at).total_seconds() / 60
        return age <= self.EDIT_WINDOW_MINUTES

    @classmethod
    def quota_for(cls, user) -> int:
        return cls.FREE_PLAN_STUDENT_QUOTA if user.is_verified_student else cls.FREE_PLAN_QUOTA

    @classmethod
    def outstanding_count(cls, user) -> int:
        return cls.objects.filter(
            freelancer=user, status__in=[cls.Status.SUBMITTED, cls.Status.SHORTLISTED]
        ).count()

    @classmethod
    def remaining_quota(cls, user) -> int:
        return max(0, cls.quota_for(user) - cls.outstanding_count(user))


class ScreeningAnswer(TimestampedModel):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(
        ScreeningQuestion, on_delete=models.CASCADE, related_name="answers"
    )
    answer = models.TextField()

    class Meta:
        ordering = ["question__order"]
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "question"], name="one_answer_per_question_per_proposal"
            )
        ]

    def __str__(self) -> str:
        return self.answer[:60]


class Invitation(TimestampedModel):
    """A client asking a specific freelancer to apply.

    An invitee bypasses the proposal quota — they did not choose to spend a
    slot, the client chose for them (Section 10.3).
    """

    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        VIEWED = "viewed", "Viewed"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        EXPIRED = "expired", "Expired"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="invitations")
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invitations"
    )
    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SENT)
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "freelancer"], name="one_invitation_per_freelancer_per_project"
            )
        ]

    def __str__(self) -> str:
        return f"Invitation to {self.freelancer_id} for {self.project_id}"

    @property
    def is_live(self) -> bool:
        return self.status in (self.Status.SENT, self.Status.VIEWED) and (
            self.expires_at > timezone.now()
        )
