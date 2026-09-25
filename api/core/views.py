"""Core endpoints: health, signed file delivery, notifications, uploads."""

from __future__ import annotations

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from . import files as filestore
from . import push
from .models import Channel, Notification, NotificationCategory, PushDevice, StoredFile
from .notify import preferences_for
from .throttling import throttled


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

    # Video is served in byte ranges when asked: Safari will not play a
    # <video> from a server that cannot, and every browser needs it to seek.
    partial = _byte_range(request, len(data)) if record.content_type.startswith("video/") else None
    if partial == "unsatisfiable":
        response = HttpResponse(status=416)
        response["Content-Range"] = f"bytes */{len(data)}"
        return response
    if partial is not None:
        start, end = partial
        response = HttpResponse(data[start : end + 1], status=206, content_type=record.content_type)
        response["Content-Range"] = f"bytes {start}-{end}/{len(data)}"
        response["Content-Disposition"] = "attachment"
    else:
        response = FileResponse(
            iter([data]),
            content_type=record.content_type,
            as_attachment=True,
            filename=record.original_name,
        )
    if record.content_type.startswith("video/"):
        response["Accept-Ranges"] = "bytes"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=0, no-store"
    return response


def _byte_range(request, total: int):
    """The single ``Range: bytes=`` span asked for, as (start, end) inclusive;
    None when no usable range was asked for; "unsatisfiable" when it lies
    outside the file."""
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", request.META.get("HTTP_RANGE", "").strip())
    if not match or match.groups() == ("", ""):
        return None
    first, last = match.groups()
    if first == "":  # the final N bytes
        start, end = max(0, total - int(last)), total - 1
    else:
        start = int(first)
        end = min(int(last), total - 1) if last else total - 1
    if start >= total or start > end:
        return "unsatisfiable"
    return start, end


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


class PushDeviceSerializer(serializers.ModelSerializer):
    """Read shape for a registered device. The token is deliberately not a
    field: a client already knows its own token, and echoing every device's
    token back on a list request would hand one compromised session the
    addresses of every other device on the account."""

    class Meta:
        model = PushDevice
        fields = ["id", "platform", "label", "is_active", "last_seen_at", "created_at"]
        read_only_fields = fields


class PushDeviceRegisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)
    platform = serializers.ChoiceField(choices=PushDevice.Platform.choices)
    label = serializers.CharField(max_length=120, required=False, allow_blank=True)


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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@throttled("push_device", writes_only=True)
def push_devices(request):
    """List this account's registered devices, or register the caller's.

    Registration is an upsert on the token, not a create — see `PushDevice`'s
    docstring on why a token can legitimately arrive already attached to a
    different account. Re-registering also reactivates a device previously
    pruned as dead, which is exactly what a reinstalled app looks like.
    """
    if request.method == "GET":
        devices = request.user.push_devices.all()
        return Response(PushDeviceSerializer(devices, many=True).data)

    serializer = PushDeviceRegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    device, created = PushDevice.objects.update_or_create(
        token=data["token"],
        defaults={
            "user": request.user,
            "platform": data["platform"],
            "label": data.get("label", ""),
            "is_active": True,
            "last_seen_at": timezone.now(),
        },
    )
    return Response(
        PushDeviceSerializer(device).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unregister_push_device(request):
    """Drop a device's registration — what a mobile client calls on sign-out.

    Takes the token in the body rather than an id in the path: at sign-out
    the client knows its own token and has no reason to have learned its
    server-side id, and `PushDeviceSerializer` deliberately never told it.
    Scoped to the caller's own devices, so knowing a token is not enough to
    unregister somebody else's handset.
    """
    token = request.data.get("token")
    if not token:
        return Response(
            {"detail": "token is required.", "code": "invalid"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    deleted, _ = PushDevice.objects.filter(user=request.user, token=token).delete()
    return Response({"unregistered": deleted})


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
            # So a mobile client can skip asking for the OS push permission
            # prompt entirely when this deployment could not deliver one.
            "push_enabled": push.is_enabled(),
            # The versions a signup accepts — see `accounts.LegalAcceptance`.
            "legal": {
                "terms_version": settings.LEGAL_TERMS_VERSION,
                "privacy_version": settings.LEGAL_PRIVACY_VERSION,
            },
            # Shown at checkout before sign-in, so a buyer knows the fee
            # arithmetic before committing to anything.
            "commission_percent": settings.PLATFORM_COMMISSION_PERCENT,
        }
    )
