"""Endpoints for the project and bidding track."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.auth import CanTransact
from core.models import AuditLog, NotificationCategory
from core.notify import dispatch

from .models import (
    Category,
    Invitation,
    Project,
    ProjectType,
    Proposal,
    Skill,
)
from .permissions import IsProjectOwnerOrReadOnly
from .serializers import (
    CategorySerializer,
    InvitationSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
    ProjectWriteSerializer,
    ProposalSerializer,
    ProposalWriteSerializer,
    SkillSerializer,
)


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# --- Taxonomy --------------------------------------------------------------


@api_view(["GET"])
@permission_classes([AllowAny])
def categories(request):
    queryset = Category.objects.filter(is_active=True, parent__isnull=True).prefetch_related(
        "children"
    )
    return Response(CategorySerializer(queryset, many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def skills(request):
    """Type-ahead over the approved skill vocabulary."""
    query = request.query_params.get("q", "").strip()
    queryset = Skill.objects.filter(is_approved=True)
    if query:
        queryset = queryset.filter(name__icontains=query)
    return Response(SkillSerializer(queryset[:25], many=True).data)


# --- Projects --------------------------------------------------------------


class ProjectViewSet(viewsets.ModelViewSet):
    """
    GET    /projects/            browse open projects on the active surface
    POST   /projects/            post a brief (draft unless published)
    GET    /projects/<id>/       one brief, with viewer-relative state
    PATCH  /projects/<id>/       edit (owner only)
    DELETE /projects/<id>/       withdraw a draft (owner only)
    """

    permission_classes = [IsProjectOwnerOrReadOnly]
    pagination_class = StandardPagination

    def get_queryset(self):
        # `Project.objects` is scope-enforcing: this queryset is already
        # filtered to the surface the request is operating on before a single
        # further filter is applied.
        queryset = Project.objects.select_related("client", "category").prefetch_related(
            "skills", "screening_questions"
        )

        user = self.request.user
        if self.request.query_params.get("mine") == "true":
            if not user.is_authenticated:
                return queryset.none()
            return queryset.filter(client=user)

        # Browse shows only work that can actually be bid on. Reaching a
        # specific brief is broader on purpose: a freelancer who already spent
        # a proposal slot must still be able to open it once it closes, and a
        # link to a finished project should not 404.
        if self.action == "list":
            visible = Q(status=Project.Status.OPEN, listing=Project.Listing.PUBLIC)
        else:
            visible = Q(listing=Project.Listing.PUBLIC) & ~Q(status=Project.Status.DRAFT)

        if user.is_authenticated:
            visible |= Q(client=user)
        return queryset.filter(visible)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProjectWriteSerializer
        if self.action == "list":
            return ProjectListSerializer
        return ProjectDetailSerializer

    def get_permissions(self):
        # Posting a brief is transacting: the profile gate applies.
        if self.action == "create":
            return [IsAuthenticated(), CanTransact()]
        return super().get_permissions()

    def filter_queryset(self, queryset):
        params = self.request.query_params

        if search := params.get("q", "").strip():
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        if category := params.get("category"):
            queryset = queryset.filter(
                Q(category__slug=category) | Q(category__parent__slug=category)
            )
        if skill_slugs := params.getlist("skill"):
            queryset = queryset.filter(skills__slug__in=skill_slugs).distinct()
        if project_type := params.get("type"):
            queryset = queryset.filter(project_type=project_type)
        if level := params.get("experience"):
            queryset = queryset.filter(experience_level=level)
        if size := params.get("size"):
            queryset = queryset.filter(size=size)
        if minimum := params.get("budget_min"):
            queryset = queryset.filter(Q(budget_max__gte=minimum) | Q(rate_max__gte=minimum))
        if params.get("students_only") == "true":
            queryset = queryset.filter(verified_students_only=True)

        ordering = {
            "newest": "-published_at",
            "budget": "-budget_max",
            "proposals": "proposal_count",
        }.get(params.get("sort", "newest"), "-published_at")
        return queryset.order_by(ordering, "-created_at")

    def perform_destroy(self, instance):
        # A brief that has already attracted proposals is closed, not deleted —
        # the freelancers who spent a slot on it deserve a record.
        if instance.proposal_count:
            instance.close()
        else:
            instance.delete()

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanTransact])
    def publish(self, request, pk=None):
        project = self.get_object()
        if project.client_id != request.user.pk:
            return Response({"detail": "Not yours to publish."}, status=status.HTTP_403_FORBIDDEN)
        project.publish()
        AuditLog.record(
            actor=request.user, action=AuditLog.Action.UPDATE, target=project, request=request
        )
        return Response(ProjectDetailSerializer(project, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        project = self.get_object()
        if project.client_id != request.user.pk:
            return Response({"detail": "Not yours to close."}, status=status.HTTP_403_FORBIDDEN)
        project.close()
        return Response(ProjectDetailSerializer(project, context={"request": request}).data)

    @action(detail=True, methods=["get", "post"], permission_classes=[IsAuthenticated])
    def proposals(self, request, pk=None):
        project = self.get_object()

        if request.method == "GET":
            # Only the client sees the field of bids. A freelancer sees exactly
            # their own — proposal contents are not public.
            if project.client_id == request.user.pk:
                queryset = project.proposals.exclude(status=Proposal.Status.WITHDRAWN)
            else:
                queryset = project.proposals.filter(freelancer=request.user)
            queryset = queryset.select_related("freelancer").prefetch_related("answers__question")
            return Response(ProposalSerializer(queryset, many=True).data)

        return self._submit_proposal(request, project)

    def _submit_proposal(self, request, project: Project):
        allowed, reason = project.accepts_proposal_from(request.user)
        if not allowed:
            return Response(
                {"detail": reason, "code": "proposal_not_allowed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Proposal credits are the primary defence against mass low-quality
        # bidding, and a core monetisation lever (Section 10.2). An invited
        # freelancer is exempt — they did not choose to spend the slot.
        invited = project.invitations.filter(freelancer=request.user).exists()
        if not invited and Proposal.remaining_quota(request.user) <= 0:
            return Response(
                {
                    "detail": (
                        f"You have reached your limit of {Proposal.quota_for(request.user)} "
                        "outstanding proposals. Withdraw one, or upgrade your plan."
                    ),
                    "code": "quota_exhausted",
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        serializer = ProposalWriteSerializer(
            data=request.data, context={"request": request, "project": project}
        )
        serializer.is_valid(raise_exception=True)
        proposal = serializer.save()

        dispatch(
            project.client,
            NotificationCategory.ORDER,
            "New proposal received",
            f"{request.user.display_name} submitted a proposal for “{project.title}”.",
            data={"project_id": project.id, "proposal_id": proposal.id},
        )
        return Response(ProposalSerializer(proposal).data, status=status.HTTP_201_CREATED)


# --- Proposals -------------------------------------------------------------


class ProposalViewSet(viewsets.ReadOnlyModelViewSet):
    """A freelancer's own proposals, plus the actions either side can take."""

    serializer_class = ProposalSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        user = self.request.user
        # You see a proposal if you wrote it or if it was written to you.
        queryset = (
            Proposal.objects.filter(Q(freelancer=user) | Q(project__client=user))
            .select_related("project", "freelancer")
            .prefetch_related("answers__question")
        )
        if state := self.request.query_params.get("status"):
            queryset = queryset.filter(status=state)
        return queryset

    def retrieve(self, request, *args, **kwargs):
        proposal = self.get_object()
        # Mark as read the first time the client opens it; response rate and
        # time-to-view are meaningful signals for the freelancer.
        if proposal.project.client_id == request.user.pk and proposal.client_viewed_at is None:
            proposal.client_viewed_at = timezone.now()
            proposal.save(update_fields=["client_viewed_at", "updated_at"])
        return Response(self.get_serializer(proposal).data)

    @action(detail=True, methods=["patch"])
    def edit(self, request, pk=None):
        proposal = self.get_object()
        if proposal.freelancer_id != request.user.pk:
            return Response({"detail": "Not yours to edit."}, status=status.HTTP_403_FORBIDDEN)
        if not proposal.is_editable:
            return Response(
                {
                    "detail": (
                        f"A proposal can only be edited within "
                        f"{Proposal.EDIT_WINDOW_MINUTES} minutes of submission."
                    ),
                    "code": "edit_window_closed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProposalWriteSerializer(
            proposal,
            data=request.data,
            partial=True,
            context={"request": request, "project": proposal.project},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProposalSerializer(proposal).data)

    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        proposal = self.get_object()
        if proposal.freelancer_id != request.user.pk:
            return Response({"detail": "Not yours to withdraw."}, status=status.HTTP_403_FORBIDDEN)
        proposal.status = Proposal.Status.WITHDRAWN
        proposal.withdrawn_at = timezone.now()
        proposal.save(update_fields=["status", "withdrawn_at", "updated_at"])
        return Response(ProposalSerializer(proposal).data)

    @action(detail=True, methods=["post"])
    def shortlist(self, request, pk=None):
        return self._client_decision(request, pk, Proposal.Status.SHORTLISTED)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        return self._client_decision(request, pk, Proposal.Status.DECLINED)

    def _client_decision(self, request, pk, new_status: str):
        proposal = self.get_object()
        if proposal.project.client_id != request.user.pk:
            return Response(
                {"detail": "Only the client can do that."}, status=status.HTTP_403_FORBIDDEN
            )
        if proposal.status == Proposal.Status.ACCEPTED:
            return Response(
                {"detail": "This proposal has already been accepted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        proposal.status = new_status
        proposal.save(update_fields=["status", "updated_at"])

        if new_status == Proposal.Status.DECLINED:
            dispatch(
                proposal.freelancer,
                NotificationCategory.ORDER,
                "Proposal not selected",
                f"Your proposal for “{proposal.project.title}” was not taken forward.",
                data={"proposal_id": proposal.id},
            )
        return Response(ProposalSerializer(proposal).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def proposal_quota(request):
    """What the freelancer has left this cycle."""
    return Response(
        {
            "limit": Proposal.quota_for(request.user),
            "outstanding": Proposal.outstanding_count(request.user),
            "remaining": Proposal.remaining_quota(request.user),
        }
    )


# --- Invitations -----------------------------------------------------------


class InvitationViewSet(viewsets.ModelViewSet):
    serializer_class = InvitationSerializer
    permission_classes = [IsAuthenticated]

    DEFAULT_TTL_DAYS = 7

    def get_queryset(self):
        user = self.request.user
        return Invitation.objects.filter(
            Q(freelancer=user) | Q(project__client=user)
        ).select_related("project", "freelancer")

    def create(self, request, *args, **kwargs):
        project = get_object_or_404(Project, pk=request.data.get("project"))
        if project.client_id != request.user.pk:
            return Response(
                {"detail": "You can only invite to your own project."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from accounts.models import User

        freelancer = get_object_or_404(User, pk=request.data.get("freelancer"), is_active=True)
        if freelancer.pk == request.user.pk:
            return Response(
                {"detail": "You cannot invite yourself."}, status=status.HTTP_400_BAD_REQUEST
            )

        invitation, created = Invitation.objects.get_or_create(
            project=project,
            freelancer=freelancer,
            defaults={
                "message": request.data.get("message", ""),
                "expires_at": timezone.now() + timedelta(days=self.DEFAULT_TTL_DAYS),
            },
        )
        if not created:
            return Response(
                {"detail": "That freelancer has already been invited."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dispatch(
            freelancer,
            NotificationCategory.ORDER,
            "You have been invited to apply",
            f"{request.user.display_name} invited you to “{project.title}”.",
            data={"project_id": project.id, "invitation_id": invitation.id},
        )
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        invitation = self.get_object()
        if invitation.freelancer_id != request.user.pk:
            return Response({"detail": "Not yours to answer."}, status=status.HTTP_403_FORBIDDEN)

        accepted = request.data.get("accept") is True
        invitation.status = Invitation.Status.ACCEPTED if accepted else Invitation.Status.DECLINED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at", "updated_at"])
        return Response(InvitationSerializer(invitation).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recommended_projects(request):
    """Open briefs matching the freelancer's declared skills.

    Deliberately simple: skill overlap and recency. Real ranking arrives with
    the search phase, tuned against actual transaction history.
    """
    profile = getattr(request.user, "seller_profile", None)
    skill_names = (profile.skills if profile else []) or []

    queryset = Project.objects.filter(
        status=Project.Status.OPEN, listing=Project.Listing.PUBLIC
    ).exclude(client=request.user)
    if skill_names:
        queryset = queryset.filter(skills__name__in=skill_names).distinct()
    if request.user.is_verified_student is False:
        queryset = queryset.filter(verified_students_only=False)

    queryset = queryset.select_related("client", "category").prefetch_related("skills")
    return Response(ProjectListSerializer(queryset[:12], many=True).data)


__all__ = [
    "InvitationViewSet",
    "ProjectType",
    "ProjectViewSet",
    "ProposalViewSet",
    "categories",
    "proposal_quota",
    "recommended_projects",
    "skills",
]
