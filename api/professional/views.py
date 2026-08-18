"""
Endpoints for the professional layer.

Every CRM queryset is filtered by `owner=request.user` at the source rather
than checked afterwards. A pipeline is commercially sensitive in a way a public
listing is not — it names who somebody is talking to and for how much — so the
rule is that a query can never *construct* a set containing another user's
contacts, not merely that it refuses to return one.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.auth import CanMoveMoney
from core.models import AuditLog, NotificationCategory
from core.notify import dispatch
from core.pagination import StandardPagination

from .entitlements import for_user, seed_default_plans
from .models import (
    Agency,
    AgencyMember,
    Contact,
    Deal,
    Plan,
    RetainerPlan,
    RetainerSubscription,
    Subscription,
    Task,
    Workspace,
    WorkspaceMember,
)
from .serializers import (
    AgencyMemberSerializer,
    AgencySerializer,
    ContactSerializer,
    DealSerializer,
    InteractionSerializer,
    PlanSerializer,
    RetainerPlanSerializer,
    RetainerSubscriptionSerializer,
    SubscriptionSerializer,
    TaskSerializer,
    WorkspaceSerializer,
)


def _bad(message: str, code: str = "invalid"):
    return Response({"detail": message, "code": code}, status=status.HTTP_400_BAD_REQUEST)


def _forbidden(message: str, code: str = "forbidden"):
    return Response({"detail": message, "code": code}, status=status.HTTP_403_FORBIDDEN)


def _upgrade_required(what: str):
    """A refusal that names the fix.

    `upgrade_required` is a distinct code from a plain permission denial so the
    client can offer the upgrade inline. A paywall the user cannot act on from
    where they hit it is a paywall most of them simply leave.
    """
    return Response(
        {"detail": what, "code": "upgrade_required"}, status=status.HTTP_402_PAYMENT_REQUIRED
    )


# --- Plans and subscriptions ------------------------------------------------


@api_view(["GET"])
@permission_classes([AllowAny])
def plans(request):
    """The pricing table. Public — it is a marketing surface."""
    rows = Plan.objects.filter(is_public=True)
    if not rows.exists():
        seed_default_plans()
        rows = Plan.objects.filter(is_public=True)
    return Response(PlanSerializer(rows, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_subscription(request):
    """The caller's plan and what it entitles them to."""
    live = (
        Subscription.objects.filter(
            user=request.user,
            status__in=Subscription.LIVE_STATUSES,
            current_period_end__gt=timezone.now(),
        )
        .select_related("plan")
        .first()
    )
    rights = for_user(request.user)

    return Response(
        {
            "subscription": SubscriptionSerializer(live).data if live else None,
            "entitlements": {
                "tier": rights.tier,
                "plan_name": rights.plan_name,
                "proposal_quota": rights.proposal_quota,
                "team_seats": rights.team_seats,
                "crm_contact_limit": rights.crm_contact_limit,
                "search_boost": rights.search_boost,
                "advanced_analytics": rights.advanced_analytics,
                "can_sell_retainers": rights.can_sell_retainers,
                "can_create_agency": rights.can_create_agency,
                "priority_support": rights.priority_support,
                "renews_at": rights.renews_at,
            },
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def subscribe(request):
    """Start or change a plan.

    Switching to Free needs no declaration — nothing is being paid for, so
    `existing.cancel()` is the whole story. A paid tier runs on the same
    trust basis `contracts.fund_milestone` and `gigs.order` do (Phase 3,
    D42): the caller has already transferred the plan's price to the
    platform's own bank account (`GET /payments/bank-transfer-instructions/`
    gives the details), and this call is them confirming that — gated by
    `CanMoveMoney` for the same reason funding or releasing a milestone is,
    since it is the same kind of declaration.
    """
    tier = (request.data.get("tier") or "").strip()
    interval = request.data.get("interval") or Subscription.Interval.MONTHLY

    plan = Plan.objects.filter(tier=tier, is_public=True).first()
    if plan is None:
        return _bad("No such plan.", "unknown_plan")

    existing = Subscription.objects.filter(
        user=request.user, status__in=Subscription.LIVE_STATUSES
    ).first()

    if plan.tier == Plan.Tier.FREE:
        if existing:
            existing.cancel()
        return Response({"subscription": None, "detail": "Moved to the free plan."})

    if existing and existing.plan_id == plan.pk:
        return Response(SubscriptionSerializer(existing).data)

    if not CanMoveMoney().has_permission(request, None):
        return _forbidden("Complete your profile before transacting.", "profile_incomplete")

    if existing:
        # Switching tiers ends the old subscription outright rather than
        # stacking a second one — the partial unique constraint would refuse it
        # anyway, and proration is a billing concern for a real gateway, not
        # a bank-transfer declaration.
        existing.status = Subscription.Status.CANCELLED
        existing.cancelled_at = timezone.now()
        existing.save(update_fields=["status", "cancelled_at", "updated_at"])

    span = timedelta(days=365 if interval == Subscription.Interval.YEARLY else 30)
    subscription = Subscription.objects.create(
        user=request.user,
        plan=plan,
        interval=interval,
        status=Subscription.Status.ACTIVE,
        current_period_end=timezone.now() + span,
    )

    from payments.models import SubscriptionPayment

    price = plan.yearly_price if interval == Subscription.Interval.YEARLY else plan.monthly_price
    SubscriptionPayment.objects.create(
        subscription=subscription,
        amount=price,
        reference_note=str(request.data.get("reference_note", ""))[:200],
        paid_by=request.user,
    )

    AuditLog.record(
        actor=request.user,
        action=AuditLog.Action.CREATE,
        target=subscription,
        request=request,
        justification=f"Subscribed to {plan.name} ({interval}), bank transfer reported.",
    )
    dispatch(
        request.user,
        NotificationCategory.ANNOUNCEMENT,
        f"You are on {plan.name}",
        "Your new limits are active immediately.",
    )
    return Response(SubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_subscription(request):
    subscription = Subscription.objects.filter(
        user=request.user, status__in=Subscription.LIVE_STATUSES
    ).first()
    if subscription is None:
        return _bad("You do not have a paid plan.", "no_subscription")

    # Ends at the period boundary by default: they paid through it and keep
    # what they paid for.
    subscription.cancel(immediately=bool(request.data.get("immediately")))
    return Response(SubscriptionSerializer(subscription).data)


# --- CRM --------------------------------------------------------------------


class ContactViewSet(viewsets.ModelViewSet):
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        queryset = Contact.objects.filter(owner=self.request.user).prefetch_related("deals")
        if self.request.query_params.get("archived") != "true":
            queryset = queryset.filter(is_archived=False)
        if search := self.request.query_params.get("q", "").strip():
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(company__icontains=search)
                | Q(email__icontains=search)
            )
        return queryset

    def create(self, request, *args, **kwargs):
        rights = for_user(request.user)
        used = Contact.objects.filter(owner=request.user, is_archived=False).count()
        if not rights.allows(used, rights.crm_contact_limit):
            return _upgrade_required(
                f"Your plan includes {rights.crm_contact_limit} contacts. Upgrade for unlimited."
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get", "post"])
    def interactions(self, request, pk=None):
        contact = self.get_object()

        if request.method == "GET":
            rows = contact.interactions.select_related("author")
            return Response(InteractionSerializer(rows, many=True).data)

        serializer = InteractionSerializer(data={**request.data, "contact": contact.pk})
        serializer.is_valid(raise_exception=True)
        interaction = serializer.save(author=request.user, contact=contact)
        contact.touch()
        return Response(InteractionSerializer(interaction).data, status=status.HTTP_201_CREATED)


class DealViewSet(viewsets.ModelViewSet):
    serializer_class = DealSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        queryset = Deal.objects.filter(owner=self.request.user).select_related("contact")
        if stage := self.request.query_params.get("stage"):
            queryset = queryset.filter(stage=stage)
        if self.request.query_params.get("open") == "true":
            queryset = queryset.filter(stage__in=Deal.OPEN_STAGES)
        return queryset

    def perform_create(self, serializer):
        deal = serializer.save(owner=self.request.user)
        deal.contact.touch()

    @action(detail=True, methods=["post"])
    def stage(self, request, pk=None):
        deal = self.get_object()
        wanted = request.data.get("stage")
        if wanted not in dict(Deal.Stage.choices):
            return _bad("Unknown stage.")
        deal.move_to(wanted, reason=request.data.get("reason", ""))
        return Response(DealSerializer(deal, context={"request": request}).data)


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        queryset = Task.objects.filter(owner=self.request.user)
        if self.request.query_params.get("open") == "true":
            queryset = queryset.filter(completed_at__isnull=True)
        return queryset

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = self.get_object()
        task.completed_at = None if task.completed_at else timezone.now()
        task.save(update_fields=["completed_at", "updated_at"])
        return Response(TaskSerializer(task).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pipeline_summary(request):
    """The CRM dashboard: value by stage, plus what is overdue."""
    deals = Deal.objects.filter(owner=request.user)
    by_stage = (
        deals.filter(stage__in=Deal.OPEN_STAGES)
        .values("stage")
        .annotate(count=Count("id"), value=Sum("value"))
    )

    won = deals.filter(stage=Deal.Stage.WON)
    lost = deals.filter(stage=Deal.Stage.LOST).count()
    won_count = won.count()
    decided = won_count + lost

    return Response(
        {
            "stages": [
                {"stage": row["stage"], "count": row["count"], "value": str(row["value"] or 0)}
                for row in by_stage
            ],
            "open_value": str(
                deals.filter(stage__in=Deal.OPEN_STAGES).aggregate(t=Sum("value"))["t"] or 0
            ),
            "won_value": str(won.aggregate(t=Sum("value"))["t"] or 0),
            # Only computed once something has actually been decided — a win
            # rate over zero closed deals is a divide-by-zero dressed as 0%.
            "win_rate": round(won_count * 100 / decided) if decided else None,
            "contacts": Contact.objects.filter(owner=request.user, is_archived=False).count(),
            "overdue_tasks": Task.objects.filter(
                owner=request.user, completed_at__isnull=True, due_at__lt=timezone.now()
            ).count(),
        }
    )


# --- Agencies ---------------------------------------------------------------


class AgencyViewSet(viewsets.ModelViewSet):
    serializer_class = AgencySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = Agency.objects.filter(is_active=True)
        if self.request.query_params.get("mine") == "true" and self.request.user.is_authenticated:
            # Invitations are included: an invite the recipient cannot find is
            # an invite that is never accepted, and this is the only list they
            # would think to look in.
            queryset = queryset.filter(
                members__user=self.request.user,
                members__status__in=[AgencyMember.Status.ACTIVE, AgencyMember.Status.INVITED],
            )
        return queryset.distinct()

    def create(self, request, *args, **kwargs):
        if not for_user(request.user).can_create_agency:
            return _upgrade_required("Creating an agency needs an Elite plan.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        with transaction.atomic():
            agency = serializer.save(owner=self.request.user)
            AgencyMember.objects.create(
                agency=agency,
                user=self.request.user,
                role=AgencyMember.Role.OWNER,
                status=AgencyMember.Status.ACTIVE,
                joined_at=timezone.now(),
            )

    @action(detail=True, methods=["get", "post"])
    def members(self, request, pk=None):
        agency = self.get_object()

        if request.method == "GET":
            rows = agency.members.select_related("user").exclude(status=AgencyMember.Status.REMOVED)
            return Response(AgencyMemberSerializer(rows, many=True).data)

        if not agency.can_manage(request.user):
            return _forbidden("Only an owner or admin can invite.", "not_an_admin")

        # Seats are the thing being sold. Checked against the *owner's* plan,
        # not the inviter's — the agency is the owner's, and an admin on a free
        # plan must not be able to grow it past what was paid for.
        rights = for_user(agency.owner)
        if agency.seats_used >= rights.team_seats:
            return _upgrade_required(f"Your plan includes {rights.team_seats} seats.")

        from accounts.models import User

        handle = (request.data.get("handle") or "").strip()
        invitee = get_object_or_404(User, handle=handle, is_active=True)

        member, created = AgencyMember.objects.get_or_create(
            agency=agency,
            user=invitee,
            defaults={
                "role": request.data.get("role", AgencyMember.Role.MEMBER),
                "revenue_share": request.data.get("revenue_share", 0),
            },
        )
        if not created and member.status == AgencyMember.Status.ACTIVE:
            return _bad("Already a member.", "already_member")
        if not created:
            member.status = AgencyMember.Status.INVITED
            member.save(update_fields=["status", "updated_at"])

        dispatch(
            invitee,
            NotificationCategory.ANNOUNCEMENT,
            f"{agency.name} invited you",
            "Open Agencies to accept or decline.",
            data={"agency_id": agency.pk},
        )
        return Response(AgencyMemberSerializer(member).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        agency = self.get_object()
        member = agency.members.filter(
            user=request.user, status=AgencyMember.Status.INVITED
        ).first()
        if member is None:
            return _bad("No invitation to accept.")
        member.accept()
        return Response(AgencyMemberSerializer(member).data)

    @action(detail=True, methods=["post"], url_path="members/(?P<member_id>[^/.]+)/remove")
    def remove_member(self, request, pk=None, member_id=None):
        agency = self.get_object()
        member = get_object_or_404(agency.members, pk=member_id)

        # Removing yourself is always allowed, and is the same operation as
        # declining an invitation or leaving. Without it an invite you do not
        # want sits in your list permanently, since only an admin could clear
        # it and the whole point is that you did not want to join them.
        leaving = member.user_id == request.user.pk
        if not leaving and not agency.can_manage(request.user):
            return _forbidden("Only an owner or admin can remove members.", "not_an_admin")

        if member.role == AgencyMember.Role.OWNER:
            return _bad("The owner cannot be removed.", "owner_protected")

        member.status = AgencyMember.Status.REMOVED
        member.save(update_fields=["status", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Shared workspaces ------------------------------------------------------


class WorkspaceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        # Membership, not ownership: a workspace exists to be shared, and a
        # client invited into one must be able to open it.
        return (
            Workspace.objects.filter(
                Q(created_by=self.request.user) | Q(members__user=self.request.user)
            )
            .prefetch_related("members__user")
            .distinct()
        )

    def perform_create(self, serializer):
        with transaction.atomic():
            workspace = serializer.save(created_by=self.request.user)
            WorkspaceMember.objects.create(workspace=workspace, user=self.request.user)

    @action(detail=True, methods=["post"])
    def invite(self, request, pk=None):
        workspace = self.get_object()
        from accounts.models import User

        invitee = get_object_or_404(
            User, handle=(request.data.get("handle") or "").strip(), is_active=True
        )
        member, _ = WorkspaceMember.objects.get_or_create(
            workspace=workspace,
            user=invitee,
            defaults={"is_client": bool(request.data.get("is_client"))},
        )
        dispatch(
            invitee,
            NotificationCategory.ANNOUNCEMENT,
            f"Added to {workspace.name}",
            "A shared workspace was opened with you.",
            data={"workspace_id": workspace.pk},
        )
        return Response(WorkspaceSerializer(workspace).data, status=status.HTTP_201_CREATED)


# --- Retainers --------------------------------------------------------------


class RetainerPlanViewSet(viewsets.ModelViewSet):
    serializer_class = RetainerPlanSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        # Scope-enforcing manager: a campus retainer never reaches the global
        # catalogue, and `core.test_tenancy` covers this model automatically.
        queryset = RetainerPlan.objects.filter(is_active=True).select_related("seller")
        if handle := self.request.query_params.get("seller"):
            queryset = queryset.filter(seller__handle=handle)
        if self.request.query_params.get("mine") == "true" and self.request.user.is_authenticated:
            queryset = RetainerPlan.objects.filter(seller=self.request.user)
        return queryset

    def create(self, request, *args, **kwargs):
        if not for_user(request.user).can_sell_retainers:
            return _upgrade_required("Selling retainers needs a Pro or Elite plan.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    @action(detail=True, methods=["post"])
    def subscribe(self, request, pk=None):
        """Engage a retainer.

        Money is deferred exactly as it is for platform plans — this records
        the engagement and starts the period clock.
        """
        plan = self.get_object()
        if plan.seller_id == request.user.pk:
            return _bad("You cannot subscribe to your own retainer.")
        if not plan.is_active:
            return _bad("This retainer is not accepting subscribers.")
        if plan.is_full:
            return _bad("This retainer is full.", "retainer_full")

        existing = RetainerSubscription.objects.filter(
            plan=plan, buyer=request.user, status__in=RetainerSubscription.LIVE_STATUSES
        ).first()
        if existing:
            return Response(RetainerSubscriptionSerializer(existing).data)

        subscription = RetainerSubscription.objects.create(
            plan=plan,
            buyer=request.user,
            current_period_end=timezone.now() + timedelta(days=30),
            months_billed=0,
        )
        dispatch(
            plan.seller,
            NotificationCategory.ORDER,
            "New retainer subscriber",
            f"{request.user.display_name} subscribed to “{plan.title}”.",
            data={"retainer_id": plan.pk},
        )
        return Response(
            RetainerSubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_retainers(request):
    """Both sides: what you sell, and what you are subscribed to."""
    selling = RetainerSubscription.objects.filter(plan__seller=request.user).select_related(
        "plan", "buyer"
    )
    buying = RetainerSubscription.objects.filter(buyer=request.user).select_related(
        "plan", "plan__seller"
    )
    return Response(
        {
            "selling": RetainerSubscriptionSerializer(selling, many=True).data,
            "buying": RetainerSubscriptionSerializer(buying, many=True).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_retainer(request, pk):
    subscription = get_object_or_404(
        RetainerSubscription.objects.select_related("plan"), pk=pk, buyer=request.user
    )
    subscription.cancel()
    return Response(RetainerSubscriptionSerializer(subscription).data)
