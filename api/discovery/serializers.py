"""Response shapes for search, showcase, and promotions."""

from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from core.files import signed_url

from .models import Promotion, ShowcaseItem


class SellerBadgeSerializer(serializers.Serializer):
    """The reputation summary that rides along with every search result.

    Included on the result rather than fetched per seller because the whole
    point of a level badge is that it is visible while comparing, and a second
    request per row would guarantee it renders late or not at all.
    """

    handle = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    level = serializers.SerializerMethodField()
    job_success_score = serializers.SerializerMethodField()

    def get_avatar_url(self, user) -> str | None:
        return signed_url(user.avatar) if user.avatar_id else None

    def get_level(self, user) -> str:
        profile = getattr(user, "seller_profile", None)
        return profile.level if profile else "new"

    def get_job_success_score(self, user) -> int | None:
        profile = getattr(user, "seller_profile", None)
        return profile.job_success_score if profile else None


class SearchGigSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    seller = SellerBadgeSerializer(read_only=True)
    category = serializers.CharField(source="category.name", read_only=True, default=None)
    rating_average = serializers.DecimalField(
        max_digits=3, decimal_places=2, read_only=True, allow_null=True
    )
    rating_count = serializers.IntegerField(read_only=True)
    starting_price = serializers.SerializerMethodField()
    #: Labelled in the payload, not just in the UI. A paid placement that a
    #: client could render as an organic result would be an undisclosed advert.
    is_promoted = serializers.BooleanField(read_only=True)
    #: Exposed so ranking can be argued with rather than guessed at.
    score = serializers.FloatField(read_only=True, required=False)

    def get_starting_price(self, gig) -> str | None:
        cheapest = min((package.price for package in gig.packages.all()), default=None)
        return str(cheapest) if cheapest is not None else None


class SearchProjectSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    description = serializers.SerializerMethodField()
    category = serializers.CharField(source="category.name", read_only=True, default=None)
    project_type = serializers.CharField(read_only=True)
    experience_level = serializers.CharField(read_only=True)
    budget_display = serializers.CharField(read_only=True)
    proposal_count = serializers.IntegerField(read_only=True)
    published_at = serializers.DateTimeField(read_only=True)
    score = serializers.FloatField(read_only=True, required=False)

    def get_description(self, project) -> str:
        return project.description[:280]


class ShowcaseItemSerializer(serializers.ModelSerializer):
    seller = SellerBadgeSerializer(read_only=True)
    cover_url = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    awaiting = serializers.SerializerMethodField()

    class Meta:
        model = ShowcaseItem
        fields = [
            "id",
            "contract",
            "title",
            "summary",
            "seller",
            "cover_url",
            "category_name",
            "skills",
            "rating_at_publication",
            "seller_approved",
            "client_approved",
            "awaiting",
            "published_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_cover_url(self, item: ShowcaseItem) -> str | None:
        return signed_url(item.cover) if item.cover_id else None

    def get_awaiting(self, item: ShowcaseItem) -> str | None:
        """Who still has to agree. Null once it is live."""
        if item.published_at:
            return None
        if not item.seller_approved:
            return "seller"
        if not item.client_approved:
            return "client"
        return None


class PromotionSerializer(serializers.ModelSerializer):
    gig_title = serializers.CharField(source="gig.title", read_only=True)
    click_through_rate = serializers.FloatField(read_only=True)
    is_live = serializers.BooleanField(read_only=True)

    class Meta:
        model = Promotion
        fields = [
            "id",
            "gig",
            "gig_title",
            "daily_budget",
            "total_budget",
            "spent",
            "starts_at",
            "ends_at",
            "status",
            "impressions",
            "clicks",
            "click_through_rate",
            "is_live",
            "created_at",
        ]
        read_only_fields = ["id", "spent", "status", "impressions", "clicks", "created_at"]


class PromotionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promotion
        fields = ["gig", "daily_budget", "total_budget", "starts_at", "ends_at"]

    def validate_gig(self, gig):
        """You may only promote a gig you own, and only a live one.

        Checked here rather than in the view because it is a property of the
        data, and a promotion pointing at somebody else's listing would be a
        way to spend money boosting a competitor into a slot you control.
        """
        request = self.context["request"]
        if gig.seller_id != request.user.pk:
            raise serializers.ValidationError("You can only promote your own service.")
        from gigs.models import Gig

        if gig.status != Gig.Status.ACTIVE:
            raise serializers.ValidationError("Only an active service can be promoted.")
        return gig

    def validate(self, attrs):
        starts = attrs.get("starts_at") or timezone.now()
        ends = attrs.get("ends_at")
        if ends and ends <= starts:
            raise serializers.ValidationError({"ends_at": "A promotion must end after it starts."})
        if attrs["total_budget"] < attrs["daily_budget"]:
            raise serializers.ValidationError(
                {"total_budget": "The total budget cannot be less than one day's budget."}
            )
        return attrs
