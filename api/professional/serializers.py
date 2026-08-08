"""Shapes for the professional layer."""

from __future__ import annotations

from rest_framework import serializers

from core.files import signed_url

from .models import (
    Agency,
    AgencyMember,
    Contact,
    Deal,
    Interaction,
    Plan,
    RetainerPlan,
    RetainerSubscription,
    Subscription,
    Task,
    Workspace,
    WorkspaceMember,
)


class PlanSerializer(serializers.ModelSerializer):
    is_paid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Plan
        fields = [
            "id",
            "tier",
            "name",
            "tagline",
            "monthly_price",
            "yearly_price",
            "is_paid",
            "proposal_quota",
            "team_seats",
            "crm_contact_limit",
            "search_boost",
            "advanced_analytics",
            "can_sell_retainers",
            "can_create_agency",
            "priority_support",
            "features",
        ]
        read_only_fields = fields


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    is_live = serializers.BooleanField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "interval",
            "status",
            "is_live",
            "started_at",
            "current_period_end",
            "cancel_at_period_end",
            "cancelled_at",
        ]
        read_only_fields = fields


# --- CRM --------------------------------------------------------------------


class ContactSerializer(serializers.ModelSerializer):
    open_deals = serializers.SerializerMethodField()
    pipeline_value = serializers.SerializerMethodField()

    class Meta:
        model = Contact
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "company",
            "source",
            "tags",
            "notes",
            "linked_user",
            "is_archived",
            "last_interaction_at",
            "open_deals",
            "pipeline_value",
            "created_at",
        ]
        read_only_fields = ["id", "last_interaction_at", "created_at"]

    def get_open_deals(self, contact: Contact) -> int:
        return contact.deals.filter(stage__in=Deal.OPEN_STAGES).count()

    def get_pipeline_value(self, contact: Contact) -> str:
        total = sum(deal.value for deal in contact.deals.filter(stage__in=Deal.OPEN_STAGES))
        return str(total)


class DealSerializer(serializers.ModelSerializer):
    contact_name = serializers.CharField(source="contact.name", read_only=True)
    is_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = Deal
        fields = [
            "id",
            "contact",
            "contact_name",
            "title",
            "value",
            "stage",
            "is_open",
            "expected_close",
            "contract",
            "closed_at",
            "lost_reason",
            "created_at",
        ]
        read_only_fields = ["id", "contact_name", "closed_at", "created_at"]

    def validate_contact(self, contact):
        """A deal may only hang off a contact you own.

        Checked here because it is a property of the data: without it, a deal
        id plus somebody else's contact id would attach your pipeline to their
        client list.
        """
        if contact.owner_id != self.context["request"].user.pk:
            raise serializers.ValidationError("That contact is not yours.")
        return contact


class InteractionSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.display_name", read_only=True)

    class Meta:
        model = Interaction
        fields = ["id", "contact", "deal", "author_name", "kind", "body", "occurred_at"]
        read_only_fields = ["id", "author_name"]


class TaskSerializer(serializers.ModelSerializer):
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "contact",
            "deal",
            "title",
            "due_at",
            "completed_at",
            "is_overdue",
            "created_at",
        ]
        read_only_fields = ["id", "is_overdue", "created_at"]


# --- Agencies ---------------------------------------------------------------


class AgencyMemberSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source="user.display_name", read_only=True)
    handle = serializers.CharField(source="user.handle", read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = AgencyMember
        fields = [
            "id",
            "user",
            "display_name",
            "handle",
            "avatar_url",
            "role",
            "status",
            "revenue_share",
            "joined_at",
        ]
        read_only_fields = ["id", "display_name", "handle", "avatar_url", "joined_at"]

    def get_avatar_url(self, member: AgencyMember) -> str | None:
        return signed_url(member.user.avatar) if member.user.avatar_id else None


class AgencySerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    seats_used = serializers.IntegerField(read_only=True)
    my_role = serializers.SerializerMethodField()
    my_status = serializers.SerializerMethodField()

    class Meta:
        model = Agency
        fields = [
            "id",
            "name",
            "slug",
            "tagline",
            "description",
            "logo_url",
            "owner",
            "seats_used",
            "my_role",
            "my_status",
            "is_active",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "logo_url",
            "owner",
            "seats_used",
            "my_status",
            "created_at",
        ]

    def get_logo_url(self, agency: Agency) -> str | None:
        return signed_url(agency.logo) if agency.logo_id else None

    def get_my_role(self, agency: Agency) -> str | None:
        request = self.context.get("request")
        return agency.role_of(getattr(request, "user", None))

    def get_my_status(self, agency: Agency) -> str | None:
        """Membership state including a pending invitation.

        `my_role` deliberately reports nothing until a membership is active, so
        an invitee is not treated as a member before they accept. That leaves
        the invitation itself invisible, which is what this exposes — without
        it the only trace of an invite is the notification, and a notification
        that has scrolled away is an invite that can never be accepted.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        member = (
            agency.members.filter(user=user).exclude(status=AgencyMember.Status.REMOVED).first()
        )
        return member.status if member else None


class WorkspaceMemberSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source="user.display_name", read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = ["id", "user", "display_name", "is_client"]
        read_only_fields = ["id", "display_name"]


class WorkspaceSerializer(serializers.ModelSerializer):
    members = WorkspaceMemberSerializer(many=True, read_only=True)
    contract_count = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = [
            "id",
            "agency",
            "name",
            "description",
            "client_contact",
            "members",
            "contract_count",
            "is_archived",
            "created_at",
        ]
        read_only_fields = ["id", "members", "contract_count", "created_at"]

    def get_contract_count(self, workspace: Workspace) -> int:
        return workspace.contracts.count()


# --- Retainers --------------------------------------------------------------


class RetainerPlanSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source="seller.display_name", read_only=True)
    seller_handle = serializers.CharField(source="seller.handle", read_only=True)
    active_subscriber_count = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)

    class Meta:
        model = RetainerPlan
        fields = [
            "id",
            "seller",
            "seller_name",
            "seller_handle",
            "title",
            "description",
            "monthly_price",
            "deliverables",
            "max_subscribers",
            "minimum_months",
            "active_subscriber_count",
            "is_full",
            "is_active",
            "visibility",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "seller",
            "seller_name",
            "seller_handle",
            "active_subscriber_count",
            "is_full",
            "created_at",
        ]

    def validate_deliverables(self, value):
        if not value:
            raise serializers.ValidationError("State what the buyer receives each month.")
        return value


class RetainerSubscriptionSerializer(serializers.ModelSerializer):
    plan_title = serializers.CharField(source="plan.title", read_only=True)
    seller_name = serializers.CharField(source="plan.seller.display_name", read_only=True)
    #: The seller's own list is otherwise a row of anonymous subscriptions —
    #: knowing that somebody subscribed is not the same as knowing who.
    buyer_name = serializers.CharField(source="buyer.display_name", read_only=True)
    buyer_handle = serializers.CharField(source="buyer.handle", read_only=True)
    monthly_price = serializers.DecimalField(
        source="plan.monthly_price", max_digits=10, decimal_places=2, read_only=True
    )
    can_cancel_now = serializers.BooleanField(read_only=True)

    class Meta:
        model = RetainerSubscription
        fields = [
            "id",
            "plan",
            "plan_title",
            "seller_name",
            "buyer_name",
            "buyer_handle",
            "monthly_price",
            "status",
            "started_at",
            "current_period_end",
            "cancel_at_period_end",
            "months_billed",
            "can_cancel_now",
        ]
        read_only_fields = fields
