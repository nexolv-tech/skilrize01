"""Core endpoints: health, signed file delivery, notifications, uploads."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from . import files as filestore
from .models import Channel, Notification, NotificationCategory, StoredFile
from .notify import preferences_for


@require_GET
def health(request):
    """Liveness probe. Deliberately says nothing about internals."""
    return JsonResponse({"status": "ok", "time": timezone.now().isoformat()})


@require_GET
def serve_signed_file(request, token: str):
    """Deliver a stored file to the holder of a valid, unexpired token.

    The token is the authorisation: it is minted for one object, expires in
    minutes, and cannot be forged without the signing key. Delivery is forced
    as an attachment with nosniff so that a file which is somehow still hostile
    cannot execute in the browser.
    """
    try:
        key = filestore.verify(token)
    except ValidationError as exc:
        return JsonResponse({"detail": str(exc.messages[0])}, status=status.HTTP_403_FORBIDDEN)

    record = StoredFile.objects.filter(key=key).first()
    if record is None:
        raise Http404
    if not record.is_downloadable:
        return JsonResponse(
            {"detail": "This file is still being scanned."}, status=status.HTTP_409_CONFLICT
        )

    try:
        data = filestore.get_storage().read(key)
    except (FileNotFoundError, ValidationError) as exc:
        raise Http404 from exc

    response = FileResponse(
        iter([data]),
        content_type=record.content_type,
        as_attachment=True,
        filename=record.original_name,
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=0, no-store"
    return response


# --- Serializers -----------------------------------------------------------


class StoredFileSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = StoredFile
        fields = [
            "id",
            "purpose",
            "original_name",
            "content_type",
            "size_bytes",
            "scan_status",
            "url",
            "created_at",
        ]
        read_only_fields = fields

    def get_url(self, obj: StoredFile) -> str | None:
        return filestore.signed_url(obj) if obj.is_downloadable else None


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "category", "title", "body", "data", "is_read", "created_at"]
        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.Serializer):
    overrides = serializers.DictField(required=False)
    digest_frequency = serializers.ChoiceField(
        choices=["instant", "daily", "weekly"], required=False
    )
    quiet_hours_start = serializers.TimeField(required=False, allow_null=True)
    quiet_hours_end = serializers.TimeField(required=False, allow_null=True)

    def validate_overrides(self, value: dict) -> dict:
        categories = {str(c) for c in NotificationCategory.values}
        channels = {str(c) for c in Channel.values}
        for category, per_channel in value.items():
            if category not in categories:
                raise serializers.ValidationError(f"Unknown category '{category}'.")
            if not isinstance(per_channel, dict):
                raise serializers.ValidationError("Each category maps channels to booleans.")
            unknown = set(per_channel) - channels
            if unknown:
                raise serializers.ValidationError(f"Unknown channel(s): {', '.join(unknown)}.")
        return value


# --- Endpoints -------------------------------------------------------------


class NotificationListView(ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.request.user.notifications.all()
        if self.request.query_params.get("unread") == "true":
            queryset = queryset.filter(read_at__isnull=True)
        return queryset


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notifications_read(request):
    """Mark specific notifications read, or all of them when no ids are given."""
    ids = request.data.get("ids")
    queryset = request.user.notifications.filter(read_at__isnull=True)
    if ids:
        queryset = queryset.filter(pk__in=ids)
    updated = queryset.update(read_at=timezone.now())
    return Response({"updated": updated})


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def notification_preferences(request):
    preference = preferences_for(request.user)

    if request.method == "PATCH":
        serializer = NotificationPreferenceSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(preference, field, value)
        preference.save()

    return Response(
        {
            "overrides": preference.overrides,
            "digest_frequency": preference.digest_frequency,
            "quiet_hours_start": preference.quiet_hours_start,
            "quiet_hours_end": preference.quiet_hours_end,
            "defaults": {str(k): v for k, v in preference.DEFAULTS.items()},
            "categories": [
                {"value": value, "label": label} for value, label in NotificationCategory.choices
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload(request):
    """Accept one file through the full validation pipeline."""
    uploaded = request.FILES.get("file")
    if uploaded is None:
        return Response(
            {"detail": "No file was provided.", "code": "invalid"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    purpose = request.data.get("purpose", StoredFile.Purpose.ATTACHMENT)
    record = filestore.store(uploaded, owner=request.user, purpose=str(purpose))
    return Response(StoredFileSerializer(record).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def config(request):
    """Client bootstrap: what this deployment supports."""
    return Response(
        {
            "environment": settings.ENVIRONMENT,
            "notification_categories": [
                {"value": v, "label": label} for v, label in NotificationCategory.choices
            ],
        }
    )
