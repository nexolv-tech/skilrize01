"""Request and response shapes for the gig track."""

from __future__ import annotations

from django.db import transaction
from rest_framework import serializers

from accounts.serializers import PublicUserSerializer
from core.files import signed_url
from marketplace.models import Skill
from marketplace.serializers import CategorySerializer, SkillSerializer

from .models import BuyerRequest, CustomOffer, Gig, GigExtra, Order, Package


class PackageSerializer(serializers.ModelSerializer):
    has_unlimited_revisions = serializers.BooleanField(read_only=True)

    class Meta:
        model = Package
        fields = [
            "id",
            "tier",
            "name",
            "description",
            "price",
            "delivery_days",
            "revisions",
            "has_unlimited_revisions",
            "features",
            "is_active",
        ]
        read_only_fields = ["id", "has_unlimited_revisions"]


class GigExtraSerializer(serializers.ModelSerializer):
    class Meta:
        model = GigExtra
        fields = ["id", "title", "price", "extra_days", "is_active"]
        read_only_fields = ["id"]


class GigListSerializer(serializers.ModelSerializer):
    """The catalogue card."""

    seller_name = serializers.CharField(source="seller.display_name", read_only=True)
    seller_handle = serializers.CharField(source="seller.handle", read_only=True)
    seller_avatar = serializers.SerializerMethodField()
    seller_is_student = serializers.BooleanField(
        source="seller.is_verified_student", read_only=True
    )
    category_name = serializers.CharField(source="category.name", read_only=True)
    starting_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    cover_url = serializers.SerializerMethodField()

    class Meta:
        model = Gig
        fields = [
            "id",
            "title",
            "slug",
            "category_name",
            "tags",
            "starting_price",
            "rating_average",
            "rating_count",
            "orders_count",
            "cover_url",
            "seller_name",
            "seller_handle",
            "seller_avatar",
            "seller_is_student",
            "visibility",
            "published_at",
        ]
        read_only_fields = fields

    def get_seller_avatar(self, gig: Gig) -> str | None:
        avatar = gig.seller.avatar
        return signed_url(avatar) if avatar and avatar.is_downloadable else None

    def get_cover_url(self, gig: Gig) -> str | None:
        cover = gig.gallery.first()
        return signed_url(cover) if cover and cover.is_downloadable else None


class GigDetailSerializer(serializers.ModelSerializer):
    seller = PublicUserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    packages = PackageSerializer(many=True, read_only=True)
    extras = GigExtraSerializer(many=True, read_only=True)
    gallery_urls = serializers.SerializerMethodField()
    starting_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    is_owner = serializers.SerializerMethodField()
    can_order = serializers.SerializerMethodField()
    order_blocked_reason = serializers.SerializerMethodField()

    class Meta:
        model = Gig
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "faq",
            "requirements",
            "tags",
            "category",
            "skills",
            "packages",
            "extras",
            "gallery_urls",
            "status",
            "starting_price",
            "rating_average",
            "rating_count",
            "orders_count",
            "seller",
            "visibility",
            "published_at",
            "created_at",
            "is_owner",
            "can_order",
            "order_blocked_reason",
        ]
        read_only_fields = fields

    def _viewer(self):
        return getattr(self.context.get("request"), "user", None)

    def get_gallery_urls(self, gig: Gig) -> list[str]:
        return [signed_url(f) for f in gig.gallery.all() if f.is_downloadable]

    def get_is_owner(self, gig: Gig) -> bool:
        viewer = self._viewer()
        return bool(viewer and viewer.is_authenticated and viewer.pk == gig.seller_id)

    def get_can_order(self, gig: Gig) -> bool:
        viewer = self._viewer()
        return bool(viewer and viewer.is_authenticated and gig.accepts_order_from(viewer)[0])

    def get_order_blocked_reason(self, gig: Gig) -> str:
        viewer = self._viewer()
        if not (viewer and viewer.is_authenticated):
            return "Sign in to order this gig."
        return gig.accepts_order_from(viewer)[1]


class GigWriteSerializer(serializers.ModelSerializer):
    packages = PackageSerializer(many=True)
    extras = GigExtraSerializer(many=True, required=False)
    skill_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Skill.objects.all(), required=False, write_only=True
    )

    class Meta:
        model = Gig
        fields = [
            "id",
            "title",
            "description",
            "category",
            "skill_ids",
            "tags",
            "faq",
            "requirements",
            "visibility",
            "university",
            "packages",
            "extras",
        ]

    def validate_title(self, value: str) -> str:
        cleaned = value.strip()
        # The constrained format is what keeps the catalogue comparable, so it
        # is corrected rather than rejected — a seller should not have to guess.
        if not cleaned.lower().startswith(Gig.TITLE_PREFIX.strip().lower()):
            cleaned = f"{Gig.TITLE_PREFIX}{cleaned[0].lower()}{cleaned[1:]}" if cleaned else cleaned
        if len(cleaned) > 200:
            raise serializers.ValidationError("Keep the title under 200 characters.")
        return cleaned

    def validate_tags(self, value: list) -> list:
        if len(value) > Gig.MAX_TAGS:
            raise serializers.ValidationError(f"At most {Gig.MAX_TAGS} tags.")
        return [str(tag).strip().lower()[:30] for tag in value if str(tag).strip()]

    def validate_packages(self, value: list) -> list:
        if not value:
            raise serializers.ValidationError("A gig needs at least a Basic package.")
        tiers = [package["tier"] for package in value]
        if len(tiers) != len(set(tiers)):
            raise serializers.ValidationError("Each tier can only be defined once.")
        if Package.Tier.BASIC not in tiers:
            raise serializers.ValidationError("The Basic tier is required.")

        # Tiers that are not ordered by price are confusing rather than clever.
        ordering = [Package.Tier.BASIC, Package.Tier.STANDARD, Package.Tier.PREMIUM]
        priced = sorted(value, key=lambda p: ordering.index(p["tier"]))
        prices = [p["price"] for p in priced]
        if any(later <= earlier for earlier, later in zip(prices, prices[1:], strict=False)):
            raise serializers.ValidationError("Each tier must cost more than the one below it.")
        return value

    def validate_requirements(self, value: list) -> list:
        for field in value:
            if not field.get("key") or not field.get("label"):
                raise serializers.ValidationError("Every requirement needs a key and a label.")
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs.get("visibility") == "university":
            author = self.context["request"].user
            if not author.is_verified_student:
                raise serializers.ValidationError(
                    {"visibility": "Only verified students can publish inside a campus portal."}
                )
            attrs["university"] = author.university
        return attrs

    @transaction.atomic
    def create(self, validated_data: dict) -> Gig:
        packages = validated_data.pop("packages")
        extras = validated_data.pop("extras", [])
        skills = validated_data.pop("skill_ids", [])

        gig = Gig.objects.create(seller=self.context["request"].user, **validated_data)
        gig.skills.set(skills)
        Package.objects.bulk_create([Package(gig=gig, **package) for package in packages])
        if extras:
            GigExtra.objects.bulk_create([GigExtra(gig=gig, **extra) for extra in extras])
        return gig

    @transaction.atomic
    def update(self, instance: Gig, validated_data: dict) -> Gig:
        packages = validated_data.pop("packages", None)
        extras = validated_data.pop("extras", None)
        skills = validated_data.pop("skill_ids", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if skills is not None:
            instance.skills.set(skills)
        if packages is not None:
            self._sync_packages(instance, packages)
        if extras is not None:
            self._sync_extras(instance, extras)
        return instance

    @staticmethod
    def _sync_packages(gig: Gig, packages: list[dict]) -> None:
        """Update tiers in place rather than rebuilding them.

        Orders reference a package with ``PROTECT``, so deleting and recreating
        would make a gig uneditable the moment it had its first sale. Editing in
        place is safe because an order carries its own price and terms snapshot
        — changing a tier's price never changes what an existing buyer owes.
        Tiers the seller removed are deactivated, not deleted, for the same
        reason.
        """
        seen = set()
        for spec in packages:
            tier = spec.pop("tier")
            Package.objects.update_or_create(
                gig=gig, tier=tier, defaults={**spec, "is_active": True}
            )
            seen.add(tier)
        gig.packages.exclude(tier__in=seen).update(is_active=False)

    @staticmethod
    def _sync_extras(gig: Gig, extras: list[dict]) -> None:
        seen = set()
        for spec in extras:
            title = spec.pop("title")
            GigExtra.objects.update_or_create(
                gig=gig, title=title, defaults={**spec, "is_active": True}
            )
            seen.add(title)
        gig.extras.exclude(title__in=seen).update(is_active=False)


class OrderSerializer(serializers.ModelSerializer):
    gig_title = serializers.CharField(source="gig.title", read_only=True)
    gig_slug = serializers.CharField(source="gig.slug", read_only=True)
    buyer_name = serializers.CharField(source="buyer.display_name", read_only=True)
    seller_name = serializers.CharField(source="seller.display_name", read_only=True)
    extras = GigExtraSerializer(many=True, read_only=True)
    revisions_left = serializers.IntegerField(read_only=True)
    is_late = serializers.BooleanField(read_only=True)
    missing_requirements = serializers.ListField(read_only=True)
    my_role = serializers.SerializerMethodField()
    requirements_form = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    cancel_blocked_reason = serializers.SerializerMethodField()
    refund = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "gig",
            "gig_title",
            "gig_slug",
            "package",
            "package_snapshot",
            "extras",
            "buyer",
            "buyer_name",
            "seller",
            "seller_name",
            "contract",
            "price",
            "delivery_days",
            "revisions_allowed",
            "revisions_used",
            "revisions_left",
            "requirements_answers",
            "requirements_form",
            "status",
            "is_late",
            "missing_requirements",
            "started_at",
            "due_at",
            "delivered_at",
            "accept_by",
            "completed_at",
            "created_at",
            "my_role",
            "can_cancel",
            "cancel_blocked_reason",
            "refund",
        ]
        read_only_fields = fields

    def get_my_role(self, order: Order) -> str:
        viewer = self.context["request"].user
        return "buyer" if viewer.pk == order.buyer_id else "seller"

    def get_requirements_form(self, order: Order) -> list:
        return order.gig.requirements or []

    def get_can_cancel(self, order: Order) -> bool:
        return order.cancellation_allowed_for(self.context["request"].user)[0]

    def get_cancel_blocked_reason(self, order: Order) -> str:
        return order.cancellation_allowed_for(self.context["request"].user)[1]

    def get_refund(self, order: Order) -> dict | None:
        """The buyer's refund for a cancelled order, if one is owed."""
        from payments.models import Refund

        if order.contract_id is None:
            return None
        refund = Refund.objects.filter(milestone__contract_id=order.contract_id).first()
        if refund is None:
            return None
        return {
            "amount": str(refund.amount),
            "status": refund.status,
            "refunded_at": refund.refunded_at,
        }


class CreateOrderSerializer(serializers.Serializer):
    """What a buyer sends. Price is never among it — the server prices the
    order from the package and extras it actually finds."""

    package = serializers.IntegerField()
    extras = serializers.ListField(child=serializers.IntegerField(), required=False)


class BuyerRequestSerializer(serializers.ModelSerializer):
    buyer_name = serializers.CharField(source="buyer.display_name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    is_live = serializers.BooleanField(read_only=True)

    class Meta:
        model = BuyerRequest
        fields = [
            "id",
            "description",
            "category",
            "category_name",
            "budget",
            "delivery_days",
            "status",
            "is_live",
            "expires_at",
            "buyer",
            "buyer_name",
            "visibility",
            "created_at",
        ]
        # The lifetime is set by the server, not chosen by the requester.
        read_only_fields = [
            "id",
            "buyer",
            "buyer_name",
            "status",
            "is_live",
            "expires_at",
            "created_at",
        ]


class CustomOfferSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source="seller.display_name", read_only=True)
    buyer_name = serializers.CharField(source="buyer.display_name", read_only=True)
    is_live = serializers.BooleanField(read_only=True)

    class Meta:
        model = CustomOffer
        fields = [
            "id",
            "seller",
            "seller_name",
            "buyer",
            "buyer_name",
            "gig",
            "buyer_request",
            "description",
            "price",
            "delivery_days",
            "revisions",
            "status",
            "is_live",
            "expires_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "seller",
            "seller_name",
            "buyer_name",
            "status",
            "is_live",
            "expires_at",
            "created_at",
        ]
