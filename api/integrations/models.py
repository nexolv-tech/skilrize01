"""
Third-party integrations — Phase 10.

Two independent capabilities, both deliberately read-only or action-triggered
rather than anything that moves money or writes back to the third party:

**Meetings.** A contract party schedules a real Zoom or Google Meet call; the
provider adapter creates it via the provider's own API and stores the join
link. This does not replace the platform's own messaging — it schedules a
call alongside a contract, nothing more.

**Activity feeds.** A contract party points the feed at a GitHub repo (or,
later, a Figma file / Notion page) they already have access to, and recent
activity shows up on the contract as read-only evidence of progress — never
write access, never code execution (the same boundary Phase 13 drew around
challenge grading, D33).

Every provider is gated behind its own `<PROVIDER>_ENABLED` setting, off by
default, mirroring `LIGHTHOUSE_ENABLED`: no Zoom/Google/GitHub/Figma/Notion
OAuth app has real credentials issued in this environment yet. The connect
flow and every adapter call are real API calls regardless — the day
credentials exist, this starts working with zero further code changes.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.crypto import EncryptedTextField
from core.models import TimestampedModel


class Provider(models.TextChoices):
    ZOOM = "zoom", "Zoom"
    GOOGLE_MEET = "google_meet", "Google Meet"
    GITHUB = "github", "GitHub"
    FIGMA = "figma", "Figma"
    NOTION = "notion", "Notion"


#: Which capability each provider serves — used to validate that e.g. a
#: meeting can't be requested from GitHub, without hard-coding the split in
#: more than one place.
MEETING_PROVIDERS = {Provider.ZOOM, Provider.GOOGLE_MEET}
ACTIVITY_PROVIDERS = {Provider.GITHUB, Provider.FIGMA, Provider.NOTION}


class IntegrationConnection(TimestampedModel):
    """One user's OAuth grant to one provider.

    Tokens get the same treatment as the OTP secrets in `accounts.models`
    (Section 7.3): unreadable at rest, decrypted only when a provider call
    actually needs them.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="integration_connections"
    )
    provider = models.CharField(max_length=16, choices=Provider.choices)
    access_token = EncryptedTextField()
    refresh_token = EncryptedTextField(blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)
    #: Whatever the provider calls the connected identity — an email, a
    #: GitHub login. Shown back to the user so "connected" is never a bare
    #: checkmark with no way to tell which account it's attached to.
    external_label = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider"], name="one_connection_per_user_per_provider"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id}: {self.provider}"

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())


class Meeting(TimestampedModel):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CANCELLED = "cancelled", "Cancelled"

    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.CASCADE, related_name="meetings"
    )
    scheduled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    provider = models.CharField(max_length=16, choices=Provider.choices)
    topic = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=30)
    join_url = models.URLField(max_length=500)
    external_meeting_id = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)

    class Meta:
        ordering = ["-start_time"]

    def __str__(self) -> str:
        return f"{self.topic} ({self.provider}) on contract {self.contract_id}"


class ActivityFeedSource(TimestampedModel):
    """A repo/file a contract party has pointed the feed at.

    `external_ref` is provider-shaped rather than a URL: `owner/repo` for
    GitHub, a file key for Figma, a page id for Notion — whatever that
    provider's own API takes to identify the resource.
    """

    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.CASCADE, related_name="activity_sources"
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    provider = models.CharField(max_length=16, choices=Provider.choices)
    external_ref = models.CharField(max_length=300)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "provider", "external_ref"],
                name="one_source_per_contract_per_ref",
            )
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.external_ref} on contract {self.contract_id}"


class ActivityEvent(TimestampedModel):
    """One cached item from a source's feed — a commit, a file version, a
    page edit. Fetched read-only; nothing here ever writes back to the
    provider."""

    source = models.ForeignKey(ActivityFeedSource, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=40)
    summary = models.CharField(max_length=500)
    actor_label = models.CharField(max_length=200, blank=True)
    occurred_at = models.DateTimeField()
    external_url = models.URLField(max_length=500, blank=True)
    external_id = models.CharField(max_length=200)

    class Meta:
        ordering = ["-occurred_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"], name="one_event_per_source_per_external_id"
            )
        ]
        indexes = [models.Index(fields=["source", "-occurred_at"])]

    def __str__(self) -> str:
        return f"{self.event_type}: {self.summary[:40]}"
