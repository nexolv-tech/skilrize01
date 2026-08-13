"""
Foundation models every later phase builds on: timestamps, tenancy scoping,
the append-only audit log, notifications, and stored-file metadata.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from .scope import Visibility, require_scope


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# --- Tenancy ---------------------------------------------------------------


class ScopedManager(models.Manager):
    """Default manager for scopeable models. Refuses to run unscoped.

    The escape hatch lives here rather than on the queryset on purpose: once
    ``get_queryset`` has applied the scope filter, no downstream chained call
    can honestly remove it. ``Model.objects.unscoped()`` is therefore the one
    and only way across surfaces, and it is trivial to grep for in review.
    """

    def get_queryset(self) -> models.QuerySet:
        qs = super().get_queryset()
        scope = require_scope()
        if scope.is_unrestricted:
            return qs
        return qs.filter(scope.as_filter())

    def unscoped(self) -> models.QuerySet:
        """Deliberately reach across every surface.

        Reserved for administrative and system work — and, per Section 4.3,
        platform-admin access to university content is written to the audit log
        by the caller.
        """
        return super().get_queryset()


class ScopedModel(TimestampedModel):
    """Base class for anything that can live inside a university portal.

    Carries the two fields the access rules in Section 4.3 are written against,
    and swaps in a manager that will not run without a scope context.

    ``all_objects`` is registered as the base manager so Django's own internals
    (following a foreign key, ``refresh_from_db``) keep working; application
    code should always go through ``objects``.
    """

    visibility = models.CharField(
        max_length=16,
        choices=[(v, v.name.title()) for v in Visibility],
        default=Visibility.GLOBAL,
        db_index=True,
    )
    university = models.ForeignKey(
        "accounts.University",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
        db_index=True,
    )

    objects = ScopedManager()
    all_objects = models.Manager()  # noqa: DJ012 — ordering here is deliberate

    class Meta:
        abstract = True
        base_manager_name = "all_objects"
        default_manager_name = "objects"

    def clean(self) -> None:
        super().clean()
        from django.core.exceptions import ValidationError

        if self.visibility == Visibility.UNIVERSITY and self.university_id is None:
            raise ValidationError(
                {"university": "University-scoped content requires a university."}
            )
        if self.visibility == Visibility.GLOBAL and self.university_id is not None:
            raise ValidationError({"university": "Global content must not carry a university."})


# --- Audit -----------------------------------------------------------------


class AuditLog(models.Model):
    """Append-only record of administrative and security-relevant actions.

    Section 5.2: every administrative action that reads personal data, moves
    money, or changes another user's state is written here with actor, target,
    action, before and after values, timestamp, IP, and justification — and the
    log is not editable or deletable through the application, including by a
    Super Admin. The write-once behaviour is enforced below rather than left to
    convention.
    """

    class Action(models.TextChoices):
        CREATE = "create"
        UPDATE = "update"
        DELETE = "delete"
        READ_SENSITIVE = "read_sensitive"
        LOGIN = "login"
        LOGIN_FAILED = "login_failed"
        LOGOUT = "logout"
        PASSWORD_RESET = "password_reset"  # noqa: S105 — an action name, not a credential
        TWO_FACTOR_ENABLED = "two_factor_enabled"
        TWO_FACTOR_DISABLED = "two_factor_disabled"
        IMPERSONATE = "impersonate"
        SCOPE_DENIED = "scope_denied"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_actions",
    )
    action = models.CharField(max_length=32, choices=Action.choices, db_index=True)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    justification = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["target_type", "target_id"])]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} by {self.actor_id or 'system'}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError("Audit log entries are append-only and cannot be modified.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit log entries are append-only and cannot be deleted.")

    @classmethod
    def record(cls, *, actor=None, action: str, target=None, request=None, **fields) -> AuditLog:
        if target is not None:
            fields.setdefault("target_type", target.__class__.__name__)
            fields.setdefault("target_id", str(target.pk))
        if request is not None:
            fields.setdefault("ip_address", client_ip(request))
            fields.setdefault("user_agent", request.META.get("HTTP_USER_AGENT", "")[:400])
            fields.setdefault("request_id", getattr(request, "request_id", ""))
        return cls.objects.create(actor=actor, action=action, **fields)


def client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


# --- Notifications ---------------------------------------------------------


class NotificationCategory(models.TextChoices):
    CONTRACT = "contract", "Contract lifecycle"
    PAYMENT = "payment", "Payment and escrow"
    MESSAGE = "message", "Messages"
    ORDER = "order", "Proposals and orders"
    REVIEW = "review", "Reviews"
    DISPUTE = "dispute", "Disputes"
    VERIFICATION = "verification", "Verification"
    COMMUNITY = "community", "Community activity"
    SECURITY = "security", "Security"
    ANNOUNCEMENT = "announcement", "Platform announcements"
    CHALLENGE = "challenge", "Proof-of-work challenges"


class Channel(models.TextChoices):
    IN_APP = "in_app", "In-app"
    EMAIL = "email", "Email"
    PUSH = "push", "Push"
    SMS = "sms", "SMS"


#: Section 24: a user who turns off marketing email must still receive a
#: dispute notice. These categories cannot be silenced on any channel and are
#: exempt from quiet hours.
UNMUTABLE_CATEGORIES = frozenset(
    {
        NotificationCategory.SECURITY,
        NotificationCategory.PAYMENT,
        NotificationCategory.DISPUTE,
    }
)

#: SMS is reserved for security and payment-critical events only.
SMS_ELIGIBLE_CATEGORIES = frozenset({NotificationCategory.SECURITY, NotificationCategory.PAYMENT})


class NotificationPreference(TimestampedModel):
    """Per-user notification settings.

    Held as one row per user rather than a row per category-channel pair: it is
    always read as a whole, it is small, and it keeps a ten-category by
    four-channel matrix from becoming forty rows per user.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preference"
    )
    #: {category: {channel: bool}}. Missing keys fall back to the defaults.
    overrides = models.JSONField(default=dict, blank=True)
    digest_frequency = models.CharField(
        max_length=16,
        choices=[("instant", "Instant"), ("daily", "Daily"), ("weekly", "Weekly")],
        default="instant",
    )
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)

    DEFAULTS = {
        Channel.IN_APP: True,
        Channel.EMAIL: True,
        Channel.PUSH: True,
        Channel.SMS: False,
    }

    def __str__(self) -> str:
        return f"Notification preferences for {self.user_id}"

    def allows(self, category: str, channel: str) -> bool:
        # SMS is reserved for security and payment-critical events, whatever
        # the user has asked for.
        if channel == Channel.SMS and category not in SMS_ELIGIBLE_CATEGORIES:
            return False
        # A user who turns off marketing email must still receive a dispute
        # notice, so these categories ignore overrides entirely.
        if category in UNMUTABLE_CATEGORIES:
            return True
        chosen = self.overrides.get(str(category), {}).get(str(channel))
        return self.DEFAULTS.get(channel, False) if chosen is None else bool(chosen)

    def in_quiet_hours(self, at=None) -> bool:
        if not (self.quiet_hours_start and self.quiet_hours_end):
            return False
        now = (at or timezone.now()).astimezone(self.user.tz).time()
        start, end = self.quiet_hours_start, self.quiet_hours_end
        # A window that wraps past midnight is the common case.
        return start <= now < end if start <= end else now >= start or now < end


class Notification(TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    category = models.CharField(max_length=24, choices=NotificationCategory.choices, db_index=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    #: Deep-link target and any structured payload the client needs.
    data = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at"])]

    def __str__(self) -> str:
        return f"{self.category}: {self.title}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


# --- Files -----------------------------------------------------------------


class StoredFile(TimestampedModel):
    """Metadata for an uploaded file. The bytes live in private storage.

    Section 7.2: nothing user-uploaded is ever served from the application
    origin, so there is no public URL field here — access is exclusively
    through a short-lived signed token minted at request time.
    """

    class Purpose(models.TextChoices):
        AVATAR = "avatar", "Profile photo"
        PORTFOLIO = "portfolio", "Portfolio media"
        IDENTITY = "identity", "Identity document"
        DELIVERABLE = "deliverable", "Contract deliverable"
        ATTACHMENT = "attachment", "Message attachment"

    class ScanStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        CLEAN = "clean", "Clean"
        INFECTED = "infected", "Infected"
        FAILED = "failed", "Scan failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="files"
    )
    purpose = models.CharField(max_length=24, choices=Purpose.choices, db_index=True)
    #: Opaque storage key. Never derived from the user-supplied filename.
    key = models.CharField(max_length=255, unique=True)
    original_name = models.CharField(max_length=255)
    #: The type proven by magic-byte inspection, not the one the client claimed.
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    checksum = models.CharField(max_length=64, db_index=True)
    scan_status = models.CharField(
        max_length=16, choices=ScanStatus.choices, default=ScanStatus.PENDING
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.original_name} ({self.purpose})"

    @property
    def is_downloadable(self) -> bool:
        """A file is only released once scanning has cleared it."""
        return self.scan_status == self.ScanStatus.CLEAN
