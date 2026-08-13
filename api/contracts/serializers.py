"""Request and response shapes for contracts, milestones, time, and reviews."""

from __future__ import annotations

from rest_framework import serializers

from accounts.serializers import PublicUserSerializer
from core.files import signed_url

from .models import Contract, ContractEvent, ContractType, Milestone, Review, TimeEntry


class MilestoneSerializer(serializers.ModelSerializer):
    deliverable_urls = serializers.SerializerMethodField()
    is_funded = serializers.BooleanField(read_only=True)

    class Meta:
        model = Milestone
        fields = [
            "id",
            "order",
            "title",
            "description",
            "amount",
            "due_date",
            "status",
            "is_funded",
            "delivery_note",
            "deliverable_urls",
            "funded_at",
            "delivered_at",
            "released_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "is_funded",
            "funded_at",
            "delivered_at",
            "released_at",
            "deliverable_urls",
        ]

    def get_deliverable_urls(self, milestone: Milestone) -> list[dict]:
        return [
            {"name": f.original_name, "url": signed_url(f)}
            for f in milestone.deliverables.all()
            if f.is_downloadable
        ]


class TimeEntrySerializer(serializers.ModelSerializer):
    hours = serializers.FloatField(read_only=True)
    is_protected = serializers.BooleanField(read_only=True)

    class Meta:
        model = TimeEntry
        fields = [
            "id",
            "worked_on",
            "minutes",
            "hours",
            "memo",
            "source",
            "activity_level",
            "is_protected",
            "is_disputed",
            "dispute_note",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "hours",
            "is_protected",
            "is_disputed",
            "dispute_note",
            "created_at",
        ]


class ContractEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.display_name", read_only=True)
    actor_id = serializers.IntegerField(source="actor.id", read_only=True)
    attachment_urls = serializers.SerializerMethodField()

    class Meta:
        model = ContractEvent
        fields = [
            "id",
            "kind",
            "body",
            "payload",
            "actor_id",
            "actor_name",
            "attachment_urls",
            "created_at",
        ]
        read_only_fields = fields

    def get_attachment_urls(self, event: ContractEvent) -> list[dict]:
        return [
            {"name": f.original_name, "url": signed_url(f)}
            for f in event.attachments.all()
            if f.is_downloadable
        ]


class ReviewSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.display_name", read_only=True)
    author_handle = serializers.CharField(source="author.handle", read_only=True)
    is_published = serializers.BooleanField(read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "contract",
            "role",
            "overall",
            "communication",
            "quality",
            "deadline",
            "value",
            "clarity",
            "payment_promptness",
            "comment",
            "response",
            "is_published",
            "published_at",
            "author_name",
            "author_handle",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "contract",
            "role",
            "is_published",
            "published_at",
            "author_name",
            "author_handle",
            "created_at",
        ]


class ReviewWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = [
            "overall",
            "communication",
            "quality",
            "deadline",
            "value",
            "clarity",
            "payment_promptness",
            "comment",
            "private_feedback",
        ]

    def validate(self, attrs: dict) -> dict:
        role = self.context["role"]
        # Each side answers only the sub-ratings that make sense for it: a
        # freelancer cannot rate their own quality of work, and a client cannot
        # rate their own payment promptness.
        if role == Review.Role.CLIENT:
            missing = [f for f in ("quality", "deadline", "value") if not attrs.get(f)]
            if missing:
                raise serializers.ValidationError(
                    {field: "This rating is required." for field in missing}
                )
            attrs["clarity"] = None
            attrs["payment_promptness"] = None
        else:
            missing = [f for f in ("clarity", "payment_promptness") if not attrs.get(f)]
            if missing:
                raise serializers.ValidationError(
                    {field: "This rating is required." for field in missing}
                )
            attrs["quality"] = None
            attrs["deadline"] = None
            attrs["value"] = None
        return attrs


class ContractListSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.display_name", read_only=True)
    freelancer_name = serializers.CharField(source="freelancer.display_name", read_only=True)
    funded_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    released_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = [
            "id",
            "title",
            "contract_type",
            "status",
            "total_amount",
            "hourly_rate",
            "funded_amount",
            "released_amount",
            "client_name",
            "freelancer_name",
            "my_role",
            "created_at",
            "accepted_at",
            "ended_at",
        ]
        read_only_fields = fields

    def get_my_role(self, contract: Contract) -> str:
        viewer = self.context["request"].user
        return "client" if viewer.pk == contract.client_id else "freelancer"


class ContractDetailSerializer(ContractListSerializer):
    client = PublicUserSerializer(read_only=True)
    freelancer = PublicUserSerializer(read_only=True)
    milestones = MilestoneSerializer(many=True, read_only=True)
    logged_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True)
    my_review_id = serializers.SerializerMethodField()
    counterparty_review = serializers.SerializerMethodField()

    class Meta(ContractListSerializer.Meta):
        fields = ContractListSerializer.Meta.fields + [
            "client",
            "freelancer",
            "milestones",
            "logged_amount",
            "terms",
            "weekly_hour_limit",
            "project",
            "project_title",
            "visibility",
            "delivered_at",
            "review_deadline",
            "started_at",
            "my_review_id",
            "counterparty_review",
        ]
        read_only_fields = fields

    def get_my_review_id(self, contract: Contract) -> int | None:
        viewer = self.context["request"].user
        mine = contract.reviews.filter(author=viewer).first()
        return mine.id if mine else None

    def get_counterparty_review(self, contract: Contract) -> dict | None:
        """The other side's review — only once it has actually been published.

        This is where double-blind is enforced in practice: an unpublished
        review is simply not in the payload, so it cannot leak through the API
        and influence what the viewer writes.
        """
        viewer = self.context["request"].user
        theirs = contract.reviews.exclude(author=viewer).filter(published_at__isnull=False).first()
        return ReviewSerializer(theirs).data if theirs else None


class ContractCreateSerializer(serializers.Serializer):
    """Turn an accepted proposal into a contract.

    The client sends a proposal id and, optionally, a milestone plan. Amounts,
    parties, and scope all come from the proposal — never from the request
    body, or a client could quietly award a different price than was bid.
    """

    proposal = serializers.IntegerField()
    contract_type = serializers.ChoiceField(choices=ContractType.choices, required=False)
    milestones = MilestoneSerializer(many=True, required=False)
    weekly_hour_limit = serializers.IntegerField(required=False, min_value=1, max_value=168)


# --- Admin console (Phase 9) -------------------------------------------------


class AdminContractSerializer(serializers.ModelSerializer):
    """A Finance Admin's view — every contract, not just the caller's own,
    so unlike `ContractListSerializer` there is no `my_role` to compute:
    the viewer is party to none of these."""

    client_name = serializers.CharField(source="client.display_name", read_only=True)
    freelancer_name = serializers.CharField(source="freelancer.display_name", read_only=True)
    funded_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    released_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Contract
        fields = [
            "id",
            "title",
            "contract_type",
            "status",
            "total_amount",
            "hourly_rate",
            "funded_amount",
            "released_amount",
            "client_name",
            "freelancer_name",
            "created_at",
            "delivered_at",
            "review_deadline",
            "ended_at",
        ]
        read_only_fields = fields


class AdminContractDetailSerializer(AdminContractSerializer):
    client = PublicUserSerializer(read_only=True)
    freelancer = PublicUserSerializer(read_only=True)
    milestones = MilestoneSerializer(many=True, read_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True, default=None)

    class Meta(AdminContractSerializer.Meta):
        fields = AdminContractSerializer.Meta.fields + [
            "client",
            "freelancer",
            "milestones",
            "project",
            "project_title",
            "visibility",
            "started_at",
        ]
        read_only_fields = fields
