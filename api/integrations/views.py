"""
Endpoints for third-party integrations.

OAuth is API-only, no server-side session: `authorize_url` hands the caller
a signed `state` token (their id + the provider, expiring in 10 minutes)
instead of anything stored server-side, and `connect` verifies that token
rather than trusting a callback to say who it's for. The frontend's own
`/integrations/callback/<provider>` route is the OAuth redirect target — it
reads `code`/`state` off the query string and POSTs them here while the user
is still authenticated normally, the same way every other write on this API
works.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from contracts.models import Contract

from .models import ActivityFeedSource, IntegrationConnection, Meeting, Provider
from .providers import registry
from .providers.base import IntegrationError, IntegrationUnavailable
from .serializers import (
    ActivitySourceSerializer,
    AddActivitySourceInputSerializer,
    ConnectionSerializer,
    MeetingSerializer,
    ScheduleMeetingInputSerializer,
)
from .sync import sync_source

_STATE_SALT = "integrations.oauth"
_STATE_MAX_AGE = 600  # 10 minutes — long enough for a real OAuth consent screen


def _bad(message: str, code: str = "invalid"):
    return Response({"detail": message, "code": code}, status=status.HTTP_400_BAD_REQUEST)


def _forbidden(message: str):
    return Response({"detail": message, "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)


def _redirect_uri(provider: str) -> str:
    return f"{settings.FRONTEND_URL}/integrations/callback/{provider}"


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def providers_status(request):
    """Every provider this platform knows about, whether it's enabled in
    this environment, and whether the caller has connected it — enough for
    the frontend to render one settings screen without five separate calls."""
    connections = {c.provider: c for c in IntegrationConnection.objects.filter(user=request.user)}
    rows = []
    for value, label in Provider.choices:
        module = registry.get(value)
        connection = connections.get(value)
        rows.append(
            {
                "provider": value,
                "label": label,
                "is_enabled": module.is_enabled(),
                "is_connected": connection is not None,
                "external_label": connection.external_label if connection else "",
            }
        )
    return Response(rows)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def authorize(request, provider):
    if provider not in Provider.values:
        return _bad("Unknown provider.", "unknown_provider")
    module = registry.get(provider)
    state = signing.dumps({"user_id": request.user.id, "provider": provider}, salt=_STATE_SALT)
    try:
        url = module.authorize_url(_redirect_uri(provider), state)
    except IntegrationUnavailable as exc:
        return _bad(str(exc), "integration_unavailable")
    return Response({"authorize_url": url, "state": state})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def connect(request, provider):
    if provider not in Provider.values:
        return _bad("Unknown provider.", "unknown_provider")

    code = request.data.get("code")
    state = request.data.get("state")
    if not code or not state:
        return _bad("code and state are required.")

    try:
        payload = signing.loads(state, salt=_STATE_SALT, max_age=_STATE_MAX_AGE)
    except signing.BadSignature:
        return _bad(
            "This connect link has expired or was tampered with. Try connecting again.",
            "bad_state",
        )
    if payload.get("user_id") != request.user.id or payload.get("provider") != provider:
        return _bad(
            "This connect link does not belong to your session. Try connecting again.",
            "bad_state",
        )

    module = registry.get(provider)
    try:
        result = module.exchange_code(code, _redirect_uri(provider))
    except IntegrationUnavailable as exc:
        return _bad(str(exc), "integration_unavailable")
    except IntegrationError as exc:
        return _bad(str(exc), "integration_error")

    expires_at = None
    if result.get("expires_in"):
        expires_at = timezone.now() + timedelta(seconds=result["expires_in"])

    connection, _created = IntegrationConnection.objects.update_or_create(
        user=request.user,
        provider=provider,
        defaults={
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token", ""),
            "expires_at": expires_at,
            "external_label": result.get("external_label", ""),
        },
    )
    return Response(ConnectionSerializer(connection).data, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def disconnect(request, provider):
    IntegrationConnection.objects.filter(user=request.user, provider=provider).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# --- Contract-scoped: meetings ---------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def contract_meetings(request, contract_id):
    contract = get_object_or_404(Contract, pk=contract_id)
    if not contract.involves(request.user):
        return _forbidden("You are not a party to this contract.")

    if request.method == "GET":
        meetings = contract.meetings.select_related("scheduled_by").all()
        return Response(MeetingSerializer(meetings, many=True).data)

    input_serializer = ScheduleMeetingInputSerializer(data=request.data)
    input_serializer.is_valid(raise_exception=True)
    data = input_serializer.validated_data
    provider = data["provider"]

    connection = IntegrationConnection.objects.filter(user=request.user, provider=provider).first()
    if not connection:
        return _bad(
            "Connect your account for this provider before scheduling a meeting.", "not_connected"
        )

    module = registry.get(provider)
    try:
        result = module.create_meeting(
            access_token=connection.access_token,
            topic=data["topic"],
            start_time=data["start_time"],
            duration_minutes=data["duration_minutes"],
        )
    except IntegrationUnavailable as exc:
        return _bad(str(exc), "integration_unavailable")
    except IntegrationError as exc:
        return _bad(str(exc), "integration_error")

    meeting = Meeting.objects.create(
        contract=contract,
        scheduled_by=request.user,
        provider=provider,
        topic=data["topic"],
        start_time=data["start_time"],
        duration_minutes=data["duration_minutes"],
        join_url=result["join_url"],
        external_meeting_id=result.get("external_id", ""),
    )
    return Response(MeetingSerializer(meeting).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_meeting(request, meeting_id):
    meeting = get_object_or_404(Meeting, pk=meeting_id)
    if not meeting.contract.involves(request.user):
        return _forbidden("You are not a party to this contract.")
    meeting.status = Meeting.Status.CANCELLED
    meeting.save(update_fields=["status", "updated_at"])
    return Response(MeetingSerializer(meeting).data)


# --- Contract-scoped: activity feeds ---------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def contract_activity_sources(request, contract_id):
    contract = get_object_or_404(Contract, pk=contract_id)
    if not contract.involves(request.user):
        return _forbidden("You are not a party to this contract.")

    if request.method == "GET":
        sources = contract.activity_sources.select_related("added_by").prefetch_related("events")
        return Response(ActivitySourceSerializer(sources, many=True).data)

    input_serializer = AddActivitySourceInputSerializer(data=request.data)
    input_serializer.is_valid(raise_exception=True)
    data = input_serializer.validated_data

    source, created = ActivityFeedSource.objects.get_or_create(
        contract=contract,
        provider=data["provider"],
        external_ref=data["external_ref"],
        defaults={"added_by": request.user},
    )
    return Response(
        ActivitySourceSerializer(source).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sync_activity_source_now(request, source_id):
    """Sync on demand rather than waiting for the periodic sweep — useful the
    first time a source is added, when there is nothing to show yet."""
    source = get_object_or_404(ActivityFeedSource, pk=source_id)
    if not source.contract.involves(request.user):
        return _forbidden("You are not a party to this contract.")

    connection = IntegrationConnection.objects.filter(
        user=request.user, provider=source.provider
    ).first()
    if not connection:
        return _bad("Connect your account for this provider before syncing.", "not_connected")

    try:
        sync_source(source, connection)
    except IntegrationUnavailable as exc:
        return _bad(str(exc), "integration_unavailable")
    except IntegrationError as exc:
        return _bad(str(exc), "integration_error")
    except DjangoValidationError as exc:
        return _bad("; ".join(exc.messages), "sync_failed")

    return Response(ActivitySourceSerializer(source).data)
