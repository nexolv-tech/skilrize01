"""Contract lifecycle endpoints."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.auth import CanTransact
from core import files as filestore
from core.models import AuditLog, NotificationCategory, StoredFile
from core.notify import dispatch
from marketplace.models import Project, ProjectType, Proposal

from .models import Contract, ContractEvent, ContractType, Milestone, Review, TimeEntry
from .permissions import IsContractParty
from .serializers import (
    ContractCreateSerializer,
    ContractDetailSerializer,
    ContractEventSerializer,
    ContractListSerializer,
    ReviewSerializer,
    ReviewWriteSerializer,
    TimeEntrySerializer,
)


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _forbidden(message: str):
    return Response({"detail": message, "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)


def _bad(message: str, code: str = "invalid"):
    return Response({"detail": message, "code": code}, status=status.HTTP_400_BAD_REQUEST)


class ContractViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /contracts/                      contracts you are a party to
    GET  /contracts/<id>/                 one contract in full
    POST /contracts/award/                accept a proposal, create the contract
    POST /contracts/<id>/accept/          freelancer accepts the offer
    POST /contracts/<id>/milestones/<n>/… fund, deliver, release
    """

    permission_classes = [IsAuthenticated, IsContractParty]
    pagination_class = StandardPagination

    def get_queryset(self):
        user = self.request.user
        # A user only ever sees contracts they are a party to. Same principle
        # as scope enforcement, applied to a two-party object.
        queryset = (
            Contract.objects.filter(Q(client=user) | Q(freelancer=user))
            .select_related("client", "freelancer", "project")
            .prefetch_related("milestones")
        )
        if state := self.request.query_params.get("status"):
            queryset = queryset.filter(status=state)
        # Narrow to the side the user is asking about — "work I hired for" is a
        # different list from "work I was hired for".
        role = self.request.query_params.get("role")
        if role == "client":
            queryset = queryset.filter(client=user)
        elif role == "freelancer":
            queryset = queryset.filter(freelancer=user)
        return queryset

    def get_serializer_class(self):
        return ContractListSerializer if self.action == "list" else ContractDetailSerializer

    # --- Award ------------------------------------------------------------

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, CanTransact])
    @transaction.atomic
    def award(self, request):
        """Accept a proposal and open a contract from it."""
        serializer = ContractCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        proposal = get_object_or_404(
            Proposal.objects.select_related("project", "freelancer"), pk=data["proposal"]
        )
        project: Project = proposal.project

        if project.client_id != request.user.pk:
            return _forbidden("Only the client who posted this project can award it.")
        if proposal.status == Proposal.Status.WITHDRAWN:
            return _bad("That proposal has been withdrawn.")
        if hasattr(proposal, "contract") and proposal.contract is not None:
            return _bad("This proposal has already been awarded.", "already_awarded")

        hourly = project.project_type == ProjectType.HOURLY
        contract_type = data.get("contract_type") or (
            ContractType.HOURLY if hourly else ContractType.FIXED
        )
        milestone_specs = data.get("milestones") or []
        if not hourly and milestone_specs:
            contract_type = ContractType.MILESTONE

        contract = Contract.objects.create(
            project=project,
            proposal=proposal,
            client=request.user,
            freelancer=proposal.freelancer,
            title=project.title,
            contract_type=contract_type,
            total_amount=None if hourly else proposal.bid_amount,
            hourly_rate=proposal.hourly_rate if hourly else None,
            weekly_hour_limit=data.get("weekly_hour_limit") or project.weekly_hours,
            # The contract lives on the same surface as the brief it came from,
            # so a campus contract never becomes globally visible.
            visibility=project.visibility,
            university=project.university,
        )

        # A fixed-price contract with no stated plan is one milestone, not a
        # special case — funding and release then have one implementation.
        if not hourly:
            specs = milestone_specs or [
                {"title": "Full delivery", "amount": proposal.bid_amount, "order": 0}
            ]
            total = sum(Decimal(str(spec["amount"])) for spec in specs)
            if proposal.bid_amount and abs(total - proposal.bid_amount) > Decimal("0.01"):
                return _bad("Milestone amounts must add up to the agreed price.")
            Milestone.objects.bulk_create(
                [
                    Milestone(
                        contract=contract,
                        order=spec.get("order", index),
                        title=spec["title"],
                        description=spec.get("description", ""),
                        amount=Decimal(str(spec["amount"])),
                        due_date=spec.get("due_date"),
                    )
                    for index, spec in enumerate(specs)
                ]
            )

        proposal.status = Proposal.Status.ACCEPTED
        proposal.save(update_fields=["status", "updated_at"])
        project.status = Project.Status.AWARDED
        project.save(update_fields=["status", "updated_at"])

        ContractEvent.log(
            contract,
            ContractEvent.Kind.STATUS,
            actor=request.user,
            body="Contract offered.",
        )
        AuditLog.record(
            actor=request.user, action=AuditLog.Action.CREATE, target=contract, request=request
        )
        dispatch(
            proposal.freelancer,
            NotificationCategory.CONTRACT,
            "You have been awarded a contract",
            f"{request.user.display_name} offered you “{project.title}”.",
            data={"contract_id": contract.id},
        )
        return Response(
            ContractDetailSerializer(contract, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """The freelancer accepts, which freezes the terms."""
        contract = self.get_object()
        if contract.freelancer_id != request.user.pk:
            return _forbidden("Only the freelancer can accept this offer.")
        if contract.status != Contract.Status.PENDING:
            return _bad("This contract is no longer awaiting acceptance.")

        contract.accept()
        ContractEvent.log(
            contract,
            ContractEvent.Kind.STATUS,
            actor=request.user,
            body="Contract accepted. Terms are now fixed.",
        )
        dispatch(
            contract.client,
            NotificationCategory.CONTRACT,
            "Contract accepted",
            f"{request.user.display_name} accepted “{contract.title}”.",
            data={"contract_id": contract.id},
        )
        return Response(self._detail(contract, request))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        contract = self.get_object()
        if contract.status in (Contract.Status.COMPLETED, Contract.Status.CANCELLED):
            return _bad("This contract is already closed.")
        # Anything already funded is a money question, and money questions go
        # through the dispute path rather than a unilateral cancel.
        if contract.funded_amount > 0:
            return _bad(
                "Funds are held against this contract. Release or dispute them first.",
                "funds_held",
            )

        contract.status = Contract.Status.CANCELLED
        contract.ended_at = timezone.now()
        contract.save(update_fields=["status", "ended_at", "updated_at"])
        ContractEvent.log(
            contract,
            ContractEvent.Kind.STATUS,
            actor=request.user,
            body=f"Contract cancelled by {request.user.display_name}.",
        )
        return Response(self._detail(contract, request))

    # --- Milestones -------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="milestones/(?P<milestone_id>[^/.]+)/fund")
    def fund_milestone(self, request, pk=None, milestone_id=None):
        """Secure the money for one milestone.

        Phase 3 replaces this with a gateway capture and a ledger entry. Until
        then it is an explicit client action, recorded, so the rest of the
        lifecycle can be built and tested against real state transitions.
        """
        contract = self.get_object()
        milestone = get_object_or_404(contract.milestones, pk=milestone_id)

        if contract.client_id != request.user.pk:
            return _forbidden("Only the client funds a milestone.")
        if contract.status != Contract.Status.ACTIVE:
            return _bad("The contract must be active before funding.")
        if milestone.status != Milestone.Status.PENDING:
            return _bad("This milestone is already funded.")

        milestone.fund()
        ContractEvent.log(
            contract,
            ContractEvent.Kind.FUNDED,
            actor=request.user,
            body=f"“{milestone.title}” funded.",
            milestone_id=milestone.id,
            amount=str(milestone.amount),
        )
        AuditLog.record(
            actor=request.user,
            action=AuditLog.Action.UPDATE,
            target=milestone,
            request=request,
            justification="Milestone funded (manual, pre-gateway).",
        )
        dispatch(
            contract.freelancer,
            NotificationCategory.PAYMENT,
            "Milestone funded",
            f"“{milestone.title}” is funded — you can safely start work.",
            data={"contract_id": contract.id},
        )
        return Response(self._detail(contract, request))

    @action(detail=True, methods=["post"], url_path="milestones/(?P<milestone_id>[^/.]+)/deliver")
    def deliver_milestone(self, request, pk=None, milestone_id=None):
        contract = self.get_object()
        milestone = get_object_or_404(contract.milestones, pk=milestone_id)

        if contract.freelancer_id != request.user.pk:
            return _forbidden("Only the freelancer delivers work.")
        if not milestone.is_funded:
            return _bad(
                "This milestone is not funded yet. Do not start unfunded work.", "not_funded"
            )
        if milestone.status in (Milestone.Status.RELEASED, Milestone.Status.DELIVERED):
            return _bad("This milestone has already been delivered.")

        uploaded = request.FILES.getlist("files")
        stored = [
            filestore.store(item, owner=request.user, purpose=StoredFile.Purpose.DELIVERABLE)
            for item in uploaded
        ]

        milestone.deliver(note=request.data.get("note", ""))
        if stored:
            milestone.deliverables.add(*stored)

        contract.mark_delivered()
        event = ContractEvent.log(
            contract,
            ContractEvent.Kind.DELIVERED,
            actor=request.user,
            body=request.data.get("note", "") or f"“{milestone.title}” delivered.",
            milestone_id=milestone.id,
        )
        if stored:
            event.attachments.add(*stored)

        dispatch(
            contract.client,
            NotificationCategory.CONTRACT,
            "Work delivered",
            (
                f"{request.user.display_name} delivered “{milestone.title}”. "
                f"You have {Contract.REVIEW_WINDOW_DAYS} days to review it."
            ),
            data={"contract_id": contract.id},
        )
        return Response(self._detail(contract, request))

    @action(detail=True, methods=["post"], url_path="milestones/(?P<milestone_id>[^/.]+)/release")
    def release_milestone(self, request, pk=None, milestone_id=None):
        """Accept the delivery and release the money."""
        contract = self.get_object()
        milestone = get_object_or_404(contract.milestones, pk=milestone_id)

        if contract.client_id != request.user.pk:
            return _forbidden("Only the client releases payment.")
        if milestone.status != Milestone.Status.DELIVERED:
            return _bad("Nothing has been delivered for this milestone yet.")

        milestone.release()
        ContractEvent.log(
            contract,
            ContractEvent.Kind.RELEASED,
            actor=request.user,
            body=f"Payment released for “{milestone.title}”.",
            milestone_id=milestone.id,
            amount=str(milestone.amount),
        )
        AuditLog.record(
            actor=request.user,
            action=AuditLog.Action.UPDATE,
            target=milestone,
            request=request,
            justification="Milestone released to freelancer.",
        )

        # The contract closes when nothing is left outstanding.
        outstanding = contract.milestones.exclude(
            status__in=[Milestone.Status.RELEASED, Milestone.Status.CANCELLED]
        ).exists()
        if not outstanding:
            contract.complete()
            ContractEvent.log(contract, ContractEvent.Kind.STATUS, body="Contract completed.")
            for party in (contract.client, contract.freelancer):
                dispatch(
                    party,
                    NotificationCategory.REVIEW,
                    "Contract complete — leave a review",
                    f"“{contract.title}” is finished. Reviews stay hidden until both sides submit.",
                    data={"contract_id": contract.id},
                )
        else:
            contract.status = Contract.Status.ACTIVE
            contract.save(update_fields=["status", "updated_at"])

        dispatch(
            contract.freelancer,
            NotificationCategory.PAYMENT,
            "Payment released",
            f"{milestone.amount} released for “{milestone.title}”.",
            data={"contract_id": contract.id},
        )
        return Response(self._detail(contract, request))

    # --- Work diary -------------------------------------------------------

    @action(detail=True, methods=["get", "post"], url_path="time")
    def time(self, request, pk=None):
        contract = self.get_object()

        if request.method == "GET":
            return Response(TimeEntrySerializer(contract.time_entries.all(), many=True).data)

        if contract.freelancer_id != request.user.pk:
            return _forbidden("Only the freelancer logs time.")
        if contract.contract_type != ContractType.HOURLY:
            return _bad("Time can only be logged against an hourly contract.")
        if contract.status != Contract.Status.ACTIVE:
            return _bad("The contract must be active to log time.")

        serializer = TimeEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Section 10.5: the weekly cap is enforced by the system so a client
        # cannot be surprised by an unbounded invoice.
        entry_date = serializer.validated_data["worked_on"]
        week_start = entry_date - timedelta(days=entry_date.weekday())
        logged_this_week = (
            contract.time_entries.filter(
                worked_on__gte=week_start, worked_on__lt=week_start + timedelta(days=7)
            ).aggregate(total=Sum("minutes"))["total"]
            or 0
        )

        if contract.weekly_hour_limit:
            proposed = logged_this_week + serializer.validated_data["minutes"]
            if proposed > contract.weekly_hour_limit * 60:
                return _bad(
                    f"That would exceed the agreed limit of "
                    f"{contract.weekly_hour_limit} hours for this week.",
                    "weekly_limit",
                )

        entry = serializer.save(
            contract=contract,
            freelancer=request.user,
            # Time added by hand is recorded as such, and is not protected in a
            # dispute. The desktop tracker is what sets `tracker`.
            source=TimeEntry.Source.MANUAL,
        )
        ContractEvent.log(
            contract,
            ContractEvent.Kind.TIME,
            actor=request.user,
            body=f"{entry.hours}h — {entry.memo}",
            minutes=entry.minutes,
        )
        return Response(TimeEntrySerializer(entry).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="time/(?P<entry_id>[^/.]+)/dispute")
    def dispute_time(self, request, pk=None, entry_id=None):
        """A client disputes specific blocks, with a reason — not a whole invoice."""
        contract = self.get_object()
        entry = get_object_or_404(contract.time_entries, pk=entry_id)

        if contract.client_id != request.user.pk:
            return _forbidden("Only the client can dispute logged time.")
        if entry.is_protected:
            return _bad(
                "Tracked time carries activity data and is protected in a dispute.",
                "time_protected",
            )

        entry.is_disputed = True
        entry.dispute_note = request.data.get("note", "")[:280]
        entry.save(update_fields=["is_disputed", "dispute_note", "updated_at"])
        return Response(TimeEntrySerializer(entry).data)

    # --- Timeline and messages -------------------------------------------

    @action(detail=True, methods=["get", "post"], url_path="events")
    def events(self, request, pk=None):
        contract = self.get_object()

        if request.method == "GET":
            queryset = contract.events.select_related("actor").prefetch_related("attachments")
            return Response(ContractEventSerializer(queryset, many=True).data)

        body = (request.data.get("body") or "").strip()
        uploaded = request.FILES.getlist("files")
        if not body and not uploaded:
            return _bad("Write a message or attach a file.")

        event = ContractEvent.log(
            contract, ContractEvent.Kind.MESSAGE, actor=request.user, body=body
        )
        if uploaded:
            event.attachments.add(
                *[
                    filestore.store(item, owner=request.user, purpose=StoredFile.Purpose.ATTACHMENT)
                    for item in uploaded
                ]
            )

        dispatch(
            contract.counterparty(request.user),
            NotificationCategory.MESSAGE,
            f"New message on “{contract.title}”",
            body[:140],
            data={"contract_id": contract.id},
        )
        return Response(ContractEventSerializer(event).data, status=status.HTTP_201_CREATED)

    # --- Reviews ----------------------------------------------------------

    @action(detail=True, methods=["get", "post"], url_path="review")
    def review(self, request, pk=None):
        contract = self.get_object()

        if request.method == "GET":
            # Only published reviews are ever returned — an unsubmitted
            # counterpart must not be able to read yours first.
            queryset = contract.reviews.filter(published_at__isnull=False)
            return Response(ReviewSerializer(queryset, many=True).data)

        if contract.status != Contract.Status.COMPLETED:
            return _bad("Only a completed contract can be reviewed.", "not_completed")
        if contract.reviews.filter(author=request.user).exists():
            return _bad("You have already reviewed this contract.", "already_reviewed")
        if contract.ended_at and timezone.now() > contract.ended_at + timedelta(
            days=Review.WINDOW_DAYS
        ):
            return _bad("The review window for this contract has closed.", "window_closed")

        role = (
            Review.Role.CLIENT if request.user.pk == contract.client_id else Review.Role.FREELANCER
        )
        serializer = ReviewWriteSerializer(data=request.data, context={"role": role})
        serializer.is_valid(raise_exception=True)

        review = serializer.save(
            contract=contract,
            author=request.user,
            subject=contract.counterparty(request.user),
            role=role,
        )
        published = Review.publish_pair_if_ready(contract)
        ContractEvent.log(
            contract, ContractEvent.Kind.REVIEW, actor=request.user, body="Review submitted."
        )

        if published:
            for party in (contract.client, contract.freelancer):
                dispatch(
                    party,
                    NotificationCategory.REVIEW,
                    "Reviews are now public",
                    f"Both reviews for “{contract.title}” have been published.",
                    data={"contract_id": contract.id},
                )

        return Response(
            {
                **ReviewSerializer(review).data,
                "published": bool(published),
                "detail": (
                    "Both reviews are now public."
                    if published
                    else "Saved. It stays hidden until the other side reviews too."
                ),
            },
            status=status.HTTP_201_CREATED,
        )

    # --- Helpers ----------------------------------------------------------

    def _detail(self, contract: Contract, request) -> dict:
        contract.refresh_from_db()
        return ContractDetailSerializer(contract, context={"request": request}).data
