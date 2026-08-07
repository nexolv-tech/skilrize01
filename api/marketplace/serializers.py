"""Request and response shapes for the project and bidding track."""

from __future__ import annotations

from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from accounts.serializers import PublicUserSerializer

from .models import (
    Category,
    Invitation,
    Project,
    ProjectType,
    Proposal,
    ScreeningAnswer,
    ScreeningQuestion,
    Skill,
)


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "icon", "description", "children"]
        read_only_fields = fields

    def get_children(self, category: Category) -> list[dict]:
        # Only expanded at the top level; a subcategory returns an empty list
        # rather than recursing forever.
        if category.parent_id is not None:
            return []
        return [
            {"id": child.id, "name": child.name, "slug": child.slug}
            for child in category.children.filter(is_active=True)
        ]


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "slug"]
        read_only_fields = fields


class ScreeningQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScreeningQuestion
        fields = ["id", "text", "order", "is_required"]


class ProjectListSerializer(serializers.ModelSerializer):
    """The card in a browse list. Deliberately lean."""

    client_name = serializers.CharField(source="client.display_name", read_only=True)
    client_country = serializers.CharField(source="client.country", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    budget_display = serializers.CharField(read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "title",
            "description",
            "project_type",
            "budget_display",
            "budget_min",
            "budget_max",
            "rate_min",
            "rate_max",
            "weekly_hours",
            "size",
            "experience_level",
            "expected_duration_days",
            "category_name",
            "skills",
            "proposal_count",
            "status",
            "client_name",
            "client_country",
            "verified_students_only",
            "visibility",
            "published_at",
            "created_at",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # A browse card shows a preview, not the whole brief.
        if len(data["description"]) > 280:
            data["description"] = data["description"][:280].rstrip() + "…"
        return data


class ProjectDetailSerializer(serializers.ModelSerializer):
    client = PublicUserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    screening_questions = ScreeningQuestionSerializer(many=True, read_only=True)
    budget_display = serializers.CharField(read_only=True)

    # Viewer-relative state, so the client never has to work it out itself.
    is_owner = serializers.SerializerMethodField()
    can_propose = serializers.SerializerMethodField()
    propose_blocked_reason = serializers.SerializerMethodField()
    my_proposal_id = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "title",
            "description",
            "project_type",
            "budget_display",
            "budget_min",
            "budget_max",
            "rate_min",
            "rate_max",
            "weekly_hours",
            "size",
            "experience_level",
            "expected_duration_days",
            "category",
            "skills",
            "screening_questions",
            "listing",
            "status",
            "preferred_country",
            "preferred_language",
            "min_job_success_score",
            "verified_students_only",
            "proposal_count",
            "client",
            "visibility",
            "published_at",
            "created_at",
            "is_owner",
            "can_propose",
            "propose_blocked_reason",
            "my_proposal_id",
        ]
        read_only_fields = fields

    def _viewer(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_is_owner(self, project: Project) -> bool:
        viewer = self._viewer()
        return bool(viewer and viewer.is_authenticated and viewer.pk == project.client_id)

    def get_can_propose(self, project: Project) -> bool:
        viewer = self._viewer()
        if not (viewer and viewer.is_authenticated):
            return False
        return project.accepts_proposal_from(viewer)[0]

    def get_propose_blocked_reason(self, project: Project) -> str:
        viewer = self._viewer()
        if not (viewer and viewer.is_authenticated):
            return "Sign in to submit a proposal."
        return project.accepts_proposal_from(viewer)[1]

    def get_my_proposal_id(self, project: Project) -> int | None:
        viewer = self._viewer()
        if not (viewer and viewer.is_authenticated):
            return None
        mine = project.proposals.filter(freelancer=viewer).first()
        return mine.id if mine else None


class ProjectWriteSerializer(serializers.ModelSerializer):
    """Creating and editing a brief.

    ``client``, ``status`` and every count are derived server-side — the client
    supplies the brief and nothing else.
    """

    skill_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Skill.objects.all(), required=False, write_only=True
    )
    screening_questions = ScreeningQuestionSerializer(many=True, required=False)

    class Meta:
        model = Project
        fields = [
            "id",
            "title",
            "description",
            "category",
            "skill_ids",
            "project_type",
            "budget_min",
            "budget_max",
            "rate_min",
            "rate_max",
            "weekly_hours",
            "size",
            "expected_duration_days",
            "experience_level",
            "listing",
            "preferred_country",
            "preferred_language",
            "min_job_success_score",
            "verified_students_only",
            "visibility",
            "university",
            "screening_questions",
        ]

    def validate(self, attrs: dict) -> dict:
        project_type = attrs.get("project_type") or getattr(
            self.instance, "project_type", ProjectType.FIXED
        )

        if project_type == ProjectType.FIXED:
            low = attrs.get("budget_min") or getattr(self.instance, "budget_min", None)
            high = attrs.get("budget_max") or getattr(self.instance, "budget_max", None)
            if not (low or high):
                raise serializers.ValidationError(
                    {"budget_max": "A fixed-price project needs a budget."}
                )
            if low and high and low > high:
                raise serializers.ValidationError(
                    {"budget_min": "The minimum budget cannot exceed the maximum."}
                )
        else:
            low = attrs.get("rate_min") or getattr(self.instance, "rate_min", None)
            high = attrs.get("rate_max") or getattr(self.instance, "rate_max", None)
            if not (low or high):
                raise serializers.ValidationError(
                    {"rate_max": "An hourly project needs a rate range."}
                )
            if low and high and low > high:
                raise serializers.ValidationError(
                    {"rate_min": "The minimum rate cannot exceed the maximum."}
                )

        # A university-scoped brief must belong to a university the author is
        # actually verified for. The view sets this; the check is here so it
        # cannot be bypassed by a direct serializer call.
        if attrs.get("visibility") == "university":
            author = self.context["request"].user
            if not author.is_verified_student:
                raise serializers.ValidationError(
                    {"visibility": "Only verified students can post inside a campus portal."}
                )
            attrs["university"] = author.university

        return attrs

    @transaction.atomic
    def create(self, validated_data: dict) -> Project:
        skills = validated_data.pop("skill_ids", [])
        questions = validated_data.pop("screening_questions", [])
        project = Project.objects.create(client=self.context["request"].user, **validated_data)
        project.skills.set(skills)
        self._sync_questions(project, questions)
        return project

    @transaction.atomic
    def update(self, instance: Project, validated_data: dict) -> Project:
        skills = validated_data.pop("skill_ids", None)
        questions = validated_data.pop("screening_questions", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if skills is not None:
            instance.skills.set(skills)
        if questions is not None:
            self._sync_questions(instance, questions)
        return instance

    @staticmethod
    def _sync_questions(project: Project, questions: list[dict]) -> None:
        project.screening_questions.all().delete()
        ScreeningQuestion.objects.bulk_create(
            [
                ScreeningQuestion(
                    project=project,
                    text=question["text"],
                    order=question.get("order", index),
                    is_required=question.get("is_required", True),
                )
                for index, question in enumerate(questions)
            ]
        )


class ScreeningAnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source="question.text", read_only=True)

    class Meta:
        model = ScreeningAnswer
        fields = ["question", "question_text", "answer"]


class ProposalSerializer(serializers.ModelSerializer):
    freelancer = PublicUserSerializer(read_only=True)
    answers = ScreeningAnswerSerializer(many=True, read_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True)
    project_type = serializers.CharField(source="project.project_type", read_only=True)
    is_editable = serializers.BooleanField(read_only=True)

    class Meta:
        model = Proposal
        fields = [
            "id",
            "project",
            "project_title",
            "project_type",
            "freelancer",
            "cover_letter",
            "bid_amount",
            "hourly_rate",
            "estimated_days",
            "proposed_milestones",
            "status",
            "is_boosted",
            "is_editable",
            "client_viewed_at",
            "created_at",
            "answers",
        ]
        read_only_fields = [
            "id",
            "project",
            "freelancer",
            "status",
            "is_boosted",
            "client_viewed_at",
            "created_at",
            "answers",
        ]


class ProposalWriteSerializer(serializers.ModelSerializer):
    answers = ScreeningAnswerSerializer(many=True, required=False)

    class Meta:
        model = Proposal
        fields = [
            "cover_letter",
            "bid_amount",
            "hourly_rate",
            "estimated_days",
            "proposed_milestones",
            "answers",
        ]

    def validate(self, attrs: dict) -> dict:
        project: Project = self.context["project"]

        if project.project_type == ProjectType.FIXED:
            if not attrs.get("bid_amount"):
                raise serializers.ValidationError({"bid_amount": "Enter your price for this work."})
        elif not attrs.get("hourly_rate"):
            raise serializers.ValidationError({"hourly_rate": "Enter your hourly rate."})

        # Every required screening question must be answered. This is the whole
        # point of the client having written them.
        required = set(
            project.screening_questions.filter(is_required=True).values_list("id", flat=True)
        )
        answered = {
            answer["question"].id
            for answer in attrs.get("answers", [])
            if answer.get("answer", "").strip()
        }
        if required - answered:
            raise serializers.ValidationError(
                {"answers": "Please answer every required screening question."}
            )

        milestones = attrs.get("proposed_milestones") or []
        if milestones and project.project_type == ProjectType.FIXED:
            total = sum(float(m.get("amount", 0)) for m in milestones)
            if abs(total - float(attrs["bid_amount"])) > 0.01:
                raise serializers.ValidationError(
                    {"proposed_milestones": "Milestone amounts must add up to your total price."}
                )

        return attrs

    @transaction.atomic
    def create(self, validated_data: dict) -> Proposal:
        answers = validated_data.pop("answers", [])
        project: Project = self.context["project"]

        proposal = Proposal.objects.create(
            project=project, freelancer=self.context["request"].user, **validated_data
        )
        ScreeningAnswer.objects.bulk_create(
            [
                ScreeningAnswer(
                    proposal=proposal, question=answer["question"], answer=answer["answer"]
                )
                for answer in answers
            ]
        )
        # Incremented in the database rather than in Python, so two proposals
        # landing at once cannot both read the same count and overwrite it.
        Project.objects.filter(pk=project.pk).update(proposal_count=F("proposal_count") + 1)
        project.refresh_from_db(fields=["proposal_count"])
        return proposal


class InvitationSerializer(serializers.ModelSerializer):
    freelancer = PublicUserSerializer(read_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True)
    is_live = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invitation
        fields = [
            "id",
            "project",
            "project_title",
            "freelancer",
            "message",
            "status",
            "is_live",
            "expires_at",
            "created_at",
        ]
        read_only_fields = ["id", "status", "is_live", "expires_at", "created_at"]
