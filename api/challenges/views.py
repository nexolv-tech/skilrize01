"""
Endpoints for proof-of-work challenges.

Joining, submitting, and viewing your own attempt need nothing beyond
`IsAuthenticated` — challenges do not move money, so this deliberately does
not reuse `CanTransact`, which exists for the marketplace's money-adjacent
actions specifically (`accounts.auth`).
"""

from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core.pagination import StandardPagination

from .models import Challenge, Participation, finalize_challenge
from .permissions import IsStaffOrAdmin
from .serializers import (
    ChallengeCreateSerializer,
    ChallengeSerializer,
    HumanReviewInputSerializer,
    ParticipationSerializer,
    SubmissionInputSerializer,
)
from .url_safety import UnsafeURLError, assert_safe_url


def _bad(message: str, code: str = "invalid"):
    return Response({"detail": message, "code": code}, status=status.HTTP_400_BAD_REQUEST)


class ChallengeViewSet(viewsets.ModelViewSet):
    lookup_field = "slug"
    pagination_class = StandardPagination
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in (
            "create",
            "update",
            "partial_update",
            "submissions",
            "review",
            "finalize",
        ):
            return [IsStaffOrAdmin()]
        if self.action in ("join", "submit", "mine"):
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ChallengeCreateSerializer
        return ChallengeSerializer

    def get_queryset(self):
        user = self.request.user
        is_staff = user.is_authenticated and (user.is_staff or user.admin_role)

        qs = Challenge.objects.select_related("skill", "created_by")
        if not is_staff:
            qs = qs.exclude(status__in=[Challenge.Status.DRAFT, Challenge.Status.CANCELLED])
        if user.is_authenticated:
            qs = qs.prefetch_related(
                Prefetch(
                    "participations",
                    queryset=Participation.objects.filter(user=user),
                    to_attr="my_participations",
                )
            )
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def join(self, request, slug=None):
        challenge = self.get_object()
        if not challenge.is_open:
            return _bad("This challenge is not open for new participants.", "challenge_closed")
        if Participation.objects.filter(challenge=challenge, user=request.user).exists():
            return _bad("You have already joined this challenge.", "already_joined")

        deadline = min(
            timezone.now() + timedelta(hours=challenge.duration_hours), challenge.closes_at
        )
        participation = Participation.objects.create(
            challenge=challenge, user=request.user, deadline=deadline
        )
        return Response(ParticipationSerializer(participation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def submit(self, request, slug=None):
        challenge = self.get_object()
        participation = get_object_or_404(Participation, challenge=challenge, user=request.user)

        input_serializer = SubmissionInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        submission_url = input_serializer.validated_data["submission_url"]

        try:
            assert_safe_url(submission_url)
        except UnsafeURLError as exc:
            return _bad(str(exc), "unsafe_url")

        try:
            participation.submit(
                submission_url=submission_url,
                repo_url=input_serializer.validated_data.get("repo_url", ""),
                notes=input_serializer.validated_data.get("notes", ""),
            )
        except DjangoValidationError as exc:
            return _bad("; ".join(exc.messages), "submission_rejected")

        if participation.needs_automated_grading:
            from core.tasks import grade_challenge_submission

            grade_challenge_submission.delay(participation.id)

        return Response(ParticipationSerializer(participation).data)

    @action(detail=True, methods=["get"])
    def submissions(self, request, slug=None):
        """Staff review queue for one challenge — every non-in-progress attempt."""
        challenge = self.get_object()
        rows = (
            challenge.participations.exclude(status=Participation.Status.IN_PROGRESS)
            .select_related("user")
            .order_by("-submitted_at")
        )
        page = self.paginate_queryset(rows)
        serializer = ParticipationSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"submissions/(?P<participation_id>\d+)/review",
    )
    def review(self, request, slug=None, participation_id=None):
        challenge = self.get_object()
        participation = get_object_or_404(Participation, pk=participation_id, challenge=challenge)

        input_serializer = HumanReviewInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        try:
            participation.apply_human_review(
                score=input_serializer.validated_data["score"],
                notes=input_serializer.validated_data.get("notes", ""),
                reviewer=request.user,
            )
        except DjangoValidationError as exc:
            return _bad("; ".join(exc.messages), "review_rejected")

        return Response(ParticipationSerializer(participation).data)

    @action(detail=True, methods=["post"])
    def finalize(self, request, slug=None):
        """Rank participants and award badges now, without waiting for the
        scheduled sweep. Idempotent — see `finalize_challenge`."""
        challenge = self.get_object()
        awarded = finalize_challenge(challenge)
        return Response(
            {
                "badges_awarded": awarded,
                "challenge": ChallengeSerializer(challenge, context={"request": request}).data,
            }
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_participations(request):
    """Every challenge the caller has joined, most recent first."""
    rows = (
        Participation.objects.filter(user=request.user)
        .select_related("challenge", "challenge__skill")
        .order_by("-started_at")
    )
    return Response(ParticipationSerializer(rows, many=True).data)
