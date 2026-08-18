"""Endpoints for the gig track."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.auth import CanMoveMoney, CanTransact
from contracts.models import Contract, ContractEvent, ContractType, Milestone
from core import files as filestore
from core.models import AuditLog, NotificationCategory, StoredFile
from core.notify import dispatch
from core.pagination import StandardPagination

from .models import BuyerRequest, CustomOffer, Gig, GigExtra, Order, Package
from .permissions import IsGigOwnerOrReadOnly, IsOrderParty
from .serializers import (
    BuyerRequestSerializer,
    CreateOrderSerializer,
    CustomOfferSerializer,
    GigDetailSerializer,
    GigListSerializer,
    GigWriteSerializer,
    OrderSerializer,
)


def _forbidden(message: str):
    return Response({"detail": message, "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)


def _bad(message: str, code: str = "invalid"):
    return Response({"detail": message, "code": code}, status=status.HTTP_400_BAD_REQUEST)


# --- Gigs ------------------------------------------------------------------


class GigViewSet(viewsets.ModelViewSet):
    """
    GET  /gigs/           browse the catalogue on the active surface
    POST /gigs/           publish a service (draft until activated)
    GET  /gigs/<id>/      one gig, with viewer-relative state
    POST /gigs/<id>/order/  purchase a package
    """

    permission_classes = [IsGigOwnerOrReadOnly]
    pagination_class = StandardPagination

    def get_queryset(self):
        queryset = Gig.objects.select_related("seller", "category").prefetch_related(
            "packages", "extras", "skills", "gallery"
        )
        user = self.request.user

        if self.request.query_params.get("mine") == "true":
            return queryset.filter(seller=user) if user.is_authenticated else queryset.none()

        # Browse shows only what can be bought; a direct link still resolves a
        # paused gig so existing buyers and inbound links do not hit a 404.
        visible = (
            Q(status=Gig.Status.ACTIVE) if self.action == "list" else ~Q(status=Gig.Status.DRAFT)
        )
        if user.is_authenticated:
            visible |= Q(seller=user)
        return queryset.filter(visible)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return GigWriteSerializer
        if self.action == "list":
            return GigListSerializer
        return GigDetailSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), CanTransact()]
        return super().get_permissions()

    def filter_queryset(self, queryset):
        params = self.request.query_params

        if search := params.get("q", "").strip():
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(tags__icontains=search)
            )
        if category := params.get("category"):
            queryset = queryset.filter(
                Q(category__slug=category) | Q(category__parent__slug=category)
            )
        if maximum := params.get("price_max"):
            queryset = queryset.filter(packages__price__lte=maximum).distinct()
        if days := params.get("delivery_days"):
            queryset = queryset.filter(packages__delivery_days__lte=days).distinct()
        if rating := params.get("rating_min"):
            queryset = queryset.filter(rating_average__gte=rating)
        if params.get("students_only") == "true":
            queryset = queryset.filter(seller__student_verification_status="verified")

        ordering = {
            "newest": "-published_at",
            "rating": "-rating_average",
            "popular": "-orders_count",
        }.get(params.get("sort", "popular"), "-orders_count")
        return queryset.order_by(ordering, "-created_at")

    def retrieve(self, request, *args, **kwargs):
        gig = self.get_object()
        # Click-through is a ranking signal, so it is counted in the database
        # rather than read-modify-written in Python.
        Gig.objects.filter(pk=gig.pk).update(clicks=F("clicks") + 1)
        return Response(self.get_serializer(gig).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanTransact])
    def publish(self, request, pk=None):
        gig = self.get_object()
        if gig.seller_id != request.user.pk:
            return _forbidden("Not yours to publish.")
        if not gig.packages.filter(is_active=True).exists():
            return _bad("Add at least a Basic package before publishing.")
        gig.publish()
        return Response(GigDetailSerializer(gig, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        """Vacation mode: pauses cleanly without damaging ranking."""
        gig = self.get_object()
        if gig.seller_id != request.user.pk:
            return _forbidden("Not yours to pause.")
        gig.status = Gig.Status.PAUSED if gig.status == Gig.Status.ACTIVE else Gig.Status.ACTIVE
        gig.save(update_fields=["status", "updated_at"])
        return Response(GigDetailSerializer(gig, context={"request": request}).data)

    @action(detail=True, methods=["post"], parser_classes=[])
    def gallery(self, request, pk=None):
        gig = self.get_object()
        if gig.seller_id != request.user.pk:
            return _forbidden("Not yours to edit.")
        uploaded = request.FILES.getlist("files")
        if not uploaded:
            return _bad("No files were provided.")
        stored = [
            filestore.store(item, owner=request.user, purpose=StoredFile.Purpose.PORTFOLIO)
            for item in uploaded
        ]
        gig.gallery.add(*stored)
        return Response(
            GigDetailSerializer(gig, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    # --- Ordering ---------------------------------------------------------

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanMoveMoney])
    @transaction.atomic
    def order(self, request, pk=None):
        """Buy a package. The buyer has transferred payment directly to
        the platform's own bank account (see
        `GET /payments/bank-transfer-instructions/`) — this call is them
        confirming that, the same trust basis `contracts.fund_milestone`
        runs on (Phase 3, D42)."""
        gig = self.get_object()
        allowed, reason = gig.accepts_order_from(request.user)
        if not allowed:
            return _bad(reason, "order_not_allowed")

        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        package = get_object_or_404(
            Package, pk=serializer.validated_data["package"], gig=gig, is_active=True
        )
        extras = list(
            GigExtra.objects.filter(
                pk__in=serializer.validated_data.get("extras", []), gig=gig, is_active=True
            )
        )

        # Priced from what the server found, never from the request body.
        total = package.price + sum((extra.price for extra in extras), Decimal("0"))
        delivery_days = max(1, package.delivery_days + sum(extra.extra_days for extra in extras))

        contract = Contract.objects.create(
            client=request.user,
            freelancer=gig.seller,
            title=gig.title,
            contract_type=ContractType.FIXED,
            total_amount=total,
            visibility=gig.visibility,
            university=gig.university,
        )
        milestone = Milestone.objects.create(
            contract=contract, order=0, title=package.name or "Delivery", amount=total
        )
        # A gig purchase is paid up front and needs no separate freelancer
        # acceptance, so the contract is live and the milestone funded
        # from the moment the order exists — the buyer has already
        # transferred the money to the platform's own account by the time
        # this request is made (Phase 3, D42).
        contract.accept()

        from payments.models import EscrowFunding

        EscrowFunding.objects.create(
            milestone=milestone,
            amount=milestone.amount,
            reference_note=str(request.data.get("reference_note", ""))[:200],
            funded_by=request.user,
        )
        milestone.fund()

        order = Order.objects.create(
            gig=gig,
            package=package,
            buyer=request.user,
            seller=gig.seller,
            contract=contract,
            price=total,
            delivery_days=delivery_days,
            revisions_allowed=package.revisions,
            package_snapshot={
                "tier": package.tier,
                "name": package.name,
                "price": str(package.price),
                "delivery_days": package.delivery_days,
                "revisions": package.revisions,
                "features": package.features,
                "extras": [{"title": e.title, "price": str(e.price)} for e in extras],
            },
        )
        order.extras.set(extras)
        Gig.objects.filter(pk=gig.pk).update(orders_count=F("orders_count") + 1)

        ContractEvent.log(
            contract,
            ContractEvent.Kind.FUNDED,
            actor=request.user,
            body="Order placed and funded — held in escrow. Waiting for requirements.",
        )
        AuditLog.record(
            actor=request.user, action=AuditLog.Action.CREATE, target=order, request=request
        )
        dispatch(
            gig.seller,
            NotificationCategory.ORDER,
            "New order received",
            f"{request.user.display_name} ordered “{gig.title}”.",
            data={"order_id": order.id},
        )
        return Response(
            OrderSerializer(order, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


# --- Orders ----------------------------------------------------------------


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated, IsOrderParty]
    pagination_class = StandardPagination

    def get_queryset(self):
        user = self.request.user
        queryset = (
            Order.objects.filter(Q(buyer=user) | Q(seller=user))
            .select_related("gig", "package", "buyer", "seller", "contract")
            .prefetch_related("extras")
        )
        if state := self.request.query_params.get("status"):
            queryset = queryset.filter(status=state)
        if role := self.request.query_params.get("role"):
            queryset = (
                queryset.filter(buyer=user) if role == "buyer" else queryset.filter(seller=user)
            )
        return queryset

    @action(detail=True, methods=["post"])
    def requirements(self, request, pk=None):
        """Submit the requirements form. This is what starts the clock."""
        order = self.get_object()
        if order.buyer_id != request.user.pk:
            return _forbidden("Only the buyer submits requirements.")
        if order.status != Order.Status.PENDING_REQUIREMENTS:
            return _bad("Requirements have already been submitted.")

        answers = request.data.get("answers")
        if not isinstance(answers, dict):
            return _bad("Send the answers as an object keyed by requirement.")

        # Checked against a detached copy, so a rejected submission leaves the
        # order exactly as it was. Half-saved answers would show as "submitted"
        # to the seller while the clock was still stopped.
        candidate = Order(gig=order.gig, requirements_answers=answers)
        if candidate.missing_requirements:
            return _bad(
                f"Still needed: {', '.join(candidate.missing_requirements)}.",
                "missing_requirements",
            )

        order.requirements_answers = answers
        order.save(update_fields=["requirements_answers", "updated_at"])

        order.start()
        ContractEvent.log(
            order.contract,
            ContractEvent.Kind.STATUS,
            actor=request.user,
            body="Requirements submitted — delivery clock started.",
        )
        dispatch(
            order.seller,
            NotificationCategory.ORDER,
            "Requirements received",
            f"You can start “{order.gig.title}”. Due in {order.delivery_days} days.",
            data={"order_id": order.id},
        )
        return Response(self._detail(order, request))

    @action(detail=True, methods=["post"])
    def deliver(self, request, pk=None):
        order = self.get_object()
        if order.seller_id != request.user.pk:
            return _forbidden("Only the seller delivers.")
        if order.status not in (Order.Status.ACTIVE, Order.Status.REVISION):
            return _bad("This order is not ready for delivery.")

        uploaded = request.FILES.getlist("files")
        stored = [
            filestore.store(item, owner=request.user, purpose=StoredFile.Purpose.DELIVERABLE)
            for item in uploaded
        ]
        note = request.data.get("note", "")

        milestone = order.contract.milestones.first()
        if milestone:
            milestone.deliver(note=note)
            if stored:
                milestone.deliverables.add(*stored)
        order.contract.mark_delivered()
        order.mark_delivered()

        event = ContractEvent.log(
            order.contract,
            ContractEvent.Kind.DELIVERED,
            actor=request.user,
            body=note or "Delivery submitted.",
        )
        if stored:
            event.attachments.add(*stored)

        dispatch(
            order.buyer,
            NotificationCategory.ORDER,
            "Your order has been delivered",
            (
                f"“{order.gig.title}” is ready. Accept it, or request a revision within "
                f"{Order.ACCEPTANCE_WINDOW_DAYS} days."
            ),
            data={"order_id": order.id},
        )
        return Response(self._detail(order, request))

    @action(detail=True, methods=["post"], url_path="request-revision")
    def request_revision(self, request, pk=None):
        order = self.get_object()
        if order.buyer_id != request.user.pk:
            return _forbidden("Only the buyer requests a revision.")
        if order.status != Order.Status.DELIVERED:
            return _bad("There is nothing delivered to revise.")
        if order.revisions_left <= 0:
            return _bad(
                "You have used every revision included in this package. The seller can send "
                "a paid custom offer for more.",
                "no_revisions_left",
            )

        note = (request.data.get("note") or "").strip()
        if not note:
            return _bad("Say what needs changing — a revision without direction wastes both sides.")

        order.request_revision()
        ContractEvent.log(
            order.contract,
            ContractEvent.Kind.MESSAGE,
            actor=request.user,
            body=f"Revision requested: {note}",
        )
        dispatch(
            order.seller,
            NotificationCategory.ORDER,
            "Revision requested",
            note[:140],
            data={"order_id": order.id},
        )
        return Response(self._detail(order, request))

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """Accept the delivery, which releases the escrowed money and
        queues the seller's payout — the platform's commission split out,
        the same arithmetic `contracts.release_milestone` uses (Phase 3,
        D42). Not gated on the seller having a complete `PayoutProfile`
        first: that is the seller's gap to close, not something the buyer
        accepting their own delivery should be blocked by — the `Payout`
        row is created regardless and simply sits `PENDING` until there
        is somewhere to send it.
        """
        order = self.get_object()
        if order.buyer_id != request.user.pk:
            return _forbidden("Only the buyer accepts a delivery.")
        if order.status != Order.Status.DELIVERED:
            return _bad("There is nothing to accept yet.")

        milestone = order.contract.milestones.first()
        if milestone and milestone.status == Milestone.Status.DELIVERED:
            milestone.release()

            from decimal import Decimal

            from django.conf import settings as django_settings

            from payments.models import Payout

            payout = Payout.compute(
                milestone=milestone,
                freelancer=order.seller,
                commission_percent=Decimal(str(django_settings.PLATFORM_COMMISSION_PERCENT)),
            )
            payout.save()
        order.contract.complete()
        order.complete()

        ContractEvent.log(
            order.contract,
            ContractEvent.Kind.RELEASED,
            actor=request.user,
            body=f"Order accepted. Rs {order.price} released from escrow.",
        )
        AuditLog.record(
            actor=request.user,
            action=AuditLog.Action.UPDATE,
            target=order,
            request=request,
            justification="Gig order accepted and payment released.",
        )
        for party in (order.buyer, order.seller):
            dispatch(
                party,
                NotificationCategory.REVIEW,
                "Order complete — leave a review",
                f"“{order.gig.title}” is finished. Reviews stay hidden until both sides submit.",
                data={"order_id": order.id, "contract_id": order.contract_id},
            )
        return Response(self._detail(order, request))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Mutual cancellation before any work is delivered."""
        order = self.get_object()
        if order.status in (Order.Status.COMPLETED, Order.Status.CANCELLED):
            return _bad("This order is already closed.")
        if order.status == Order.Status.DELIVERED:
            return _bad(
                "Work has been delivered. Accept it or request a revision instead.",
                "already_delivered",
            )

        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status", "updated_at"])
        order.contract.status = Contract.Status.CANCELLED
        order.contract.ended_at = timezone.now()
        order.contract.save(update_fields=["status", "ended_at", "updated_at"])

        ContractEvent.log(
            order.contract,
            ContractEvent.Kind.STATUS,
            actor=request.user,
            body=f"Order cancelled by {request.user.display_name}.",
        )
        return Response(self._detail(order, request))

    def _detail(self, order: Order, request) -> dict:
        order.refresh_from_db()
        return OrderSerializer(order, context={"request": request}).data


# --- Buyer requests and custom offers --------------------------------------


class BuyerRequestViewSet(viewsets.ModelViewSet):
    serializer_class = BuyerRequestSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    DEFAULT_TTL_DAYS = 14

    def get_queryset(self):
        queryset = BuyerRequest.objects.select_related("buyer", "category")
        if self.request.query_params.get("mine") == "true":
            return queryset.filter(buyer=self.request.user)
        return queryset.filter(status=BuyerRequest.Status.OPEN)

    def perform_create(self, serializer):
        serializer.save(
            buyer=self.request.user,
            expires_at=timezone.now() + timedelta(days=self.DEFAULT_TTL_DAYS),
        )


class CustomOfferViewSet(viewsets.ModelViewSet):
    serializer_class = CustomOfferSerializer
    permission_classes = [IsAuthenticated]

    DEFAULT_TTL_DAYS = 7

    def get_queryset(self):
        user = self.request.user
        return CustomOffer.objects.filter(Q(seller=user) | Q(buyer=user)).select_related(
            "seller", "buyer", "gig"
        )

    def perform_create(self, serializer):
        serializer.save(
            seller=self.request.user,
            expires_at=timezone.now() + timedelta(days=self.DEFAULT_TTL_DAYS),
        )

    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        offer = self.get_object()
        if offer.buyer_id != request.user.pk:
            return _forbidden("Only the buyer can answer this offer.")
        if not offer.is_live:
            return _bad("This offer is no longer open.")

        accepted = request.data.get("accept") is True
        offer.status = CustomOffer.Status.ACCEPTED if accepted else CustomOffer.Status.DECLINED
        offer.responded_at = timezone.now()
        offer.save(update_fields=["status", "responded_at", "updated_at"])
        return Response(CustomOfferSerializer(offer).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def seller_dashboard(request):
    """The seller's own catalogue performance."""
    gigs = Gig.objects.filter(seller=request.user)
    active_orders = Order.objects.filter(
        seller=request.user,
        status__in=[
            Order.Status.PENDING_REQUIREMENTS,
            Order.Status.ACTIVE,
            Order.Status.REVISION,
            Order.Status.DELIVERED,
        ],
    )
    return Response(
        {
            "gigs": gigs.count(),
            "active_gigs": gigs.filter(status=Gig.Status.ACTIVE).count(),
            "impressions": sum(gig.impressions for gig in gigs),
            "clicks": sum(gig.clicks for gig in gigs),
            "orders_in_flight": active_orders.count(),
            "orders_completed": Order.objects.filter(
                seller=request.user, status=Order.Status.COMPLETED
            ).count(),
        }
    )
