"""
Identity: universities, the user account, both profile faces, and the
credentials that protect them.

One account is simultaneously a buyer and a seller (Section 5): the platform
never asks someone to choose at signup, because the same person hires and is
hired. Role capabilities are additive, so they are modelled as capabilities on
one user rather than as separate account types.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from core.crypto import EncryptedTextField
from core.models import TimestampedModel


class VerificationStatus(models.TextChoices):
    UNVERIFIED = "unverified", "Unverified"
    PENDING = "pending", "Pending review"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"


# --- Universities ----------------------------------------------------------


class University(TimestampedModel):
    """Onboarding a university is a configuration record, not an engineering
    project (Section 15.7). Everything a portal needs lives on this row."""

    name = models.CharField(max_length=255)
    short_code = models.CharField(max_length=20, unique=True)
    city = models.CharField(max_length=100, blank=True)
    logo = models.ForeignKey(
        "core.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    brand_color = models.CharField(max_length=7, blank=True, help_text="Hex, e.g. #5B4CE8")
    #: When true, an approved student ID card is required in addition to a
    #: verified university email address.
    require_id_card = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "universities"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ApprovedEmailDomain(TimestampedModel):
    """A domain that proves membership of one university, subdomains included."""

    university = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name="email_domains"
    )
    domain = models.CharField(max_length=255, unique=True, db_index=True)

    def __str__(self) -> str:
        return f"{self.domain} → {self.university.short_code}"

    def save(self, *args, **kwargs):
        self.domain = self.domain.strip().lower().lstrip("@")
        return super().save(*args, **kwargs)

    @classmethod
    def match(cls, email: str) -> University | None:
        """Find the university an address belongs to.

        Matches the exact domain and any parent of it, so a departmental
        subdomain resolves without every department needing its own record.
        """
        domain = email.rsplit("@", 1)[-1].strip().lower()
        candidates = [domain]
        parts = domain.split(".")
        candidates += [".".join(parts[i:]) for i in range(1, len(parts) - 1)]
        row = (
            cls.objects.filter(domain__in=candidates, university__is_active=True)
            .select_related("university")
            .order_by(models.functions.Length("domain").desc())
            .first()
        )
        return row.university if row else None


# --- Account ---------------------------------------------------------------


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        extra.setdefault("handle", self.model.generate_handle(email))
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra):
        extra.update(is_staff=True, is_superuser=True, admin_role=User.AdminRole.SUPER_ADMIN)
        extra.setdefault("email_verified", True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin, TimestampedModel):
    class AdminRole(models.TextChoices):
        NONE = "", "Not an administrator"
        SUPER_ADMIN = "super_admin", "Super Admin"
        FINANCE_ADMIN = "finance_admin", "Finance Admin"
        MODERATOR = "moderator", "Moderator"
        SUPPORT_AGENT = "support_agent", "Support Agent"
        DISPUTE_OFFICER = "dispute_officer", "Dispute Officer"
        VERIFICATION_OFFICER = "verification_officer", "Verification Officer"
        UNIVERSITY_MODERATOR = "university_moderator", "University Moderator"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public and search-indexable"
        PLATFORM = "platform", "Signed-in users only"
        PRIVATE = "private", "Private"

    # Identity
    email = models.EmailField(unique=True, db_index=True)
    handle = models.SlugField(max_length=40, unique=True)
    full_name = models.CharField(max_length=120, blank=True)
    avatar = models.ForeignKey(
        "core.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    headline = models.CharField(max_length=140, blank=True)
    bio = models.TextField(blank=True)
    country = models.CharField(max_length=2, blank=True, help_text="ISO 3166-1 alpha-2")
    city = models.CharField(max_length=100, blank=True)
    timezone_name = models.CharField(max_length=64, default="UTC")
    #: [{"code": "en", "proficiency": "native"}]
    languages = models.JSONField(default=list, blank=True)

    # Verification. Each of these is a separate proof and they are not
    # interchangeable.
    email_verified = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, blank=True)
    phone_verified = models.BooleanField(default=False)
    #: National identity card, required of every user and not only students,
    #: because the platform holds money on their behalf (Section 6.1).
    identity_status = models.CharField(
        max_length=16, choices=VerificationStatus.choices, default=VerificationStatus.UNVERIFIED
    )
    identity_document = models.ForeignKey(
        "core.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    # University layer
    university = models.ForeignKey(
        University, null=True, blank=True, on_delete=models.SET_NULL, related_name="students"
    )
    student_verification_status = models.CharField(
        max_length=16, choices=VerificationStatus.choices, default=VerificationStatus.UNVERIFIED
    )
    student_verified_at = models.DateTimeField(null=True, blank=True)

    # Access
    profile_visibility = models.CharField(
        max_length=16, choices=Visibility.choices, default=Visibility.PUBLIC
    )
    admin_role = models.CharField(
        max_length=32, choices=AdminRole.choices, blank=True, default=AdminRole.NONE
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    last_active_at = models.DateTimeField(null=True, blank=True)
    #: Set when the user erased their own account (GDPR Art. 17). Distinct from
    #: a suspension, which also clears `is_active` but can be reversed — an
    #: erased account has had its personal data removed and never comes back.
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email

    @staticmethod
    def generate_handle(email: str) -> str:
        base = "".join(c for c in email.split("@")[0].lower() if c.isalnum() or c == "-")[:24]
        return f"{base or 'member'}-{secrets.token_hex(3)}"

    @property
    def display_name(self) -> str:
        return self.full_name or self.handle

    @property
    def tz(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.timezone_name)
        except Exception:
            return ZoneInfo("UTC")

    @property
    def is_verified_student(self) -> bool:
        return (
            self.student_verification_status == VerificationStatus.VERIFIED
            and self.university_id is not None
        )

    # --- The profile completion gate (Section 8.4) -------------------------
    # A hard gate, not a soft suggestion: until it passes, a user may browse
    # but may not post projects, publish gigs, submit proposals, purchase, or
    # transact in any way.

    @property
    def profile_complete(self) -> bool:
        return not self.missing_profile_requirements()

    @property
    def can_transact(self) -> bool:
        return self.is_active and self.profile_complete

    def missing_profile_requirements(self) -> list[str]:
        """What is still outstanding, so the client can say so precisely."""
        from django.conf import settings

        missing = []
        if not self.email_verified:
            missing.append("email")
        # Required only once an SMS provider can actually deliver the code —
        # see PHONE_VERIFICATION_REQUIRED in settings.
        if settings.PHONE_VERIFICATION_REQUIRED and not self.phone_verified:
            missing.append("phone")
        if self.identity_status != VerificationStatus.VERIFIED:
            missing.append("identity")
        return missing

    @property
    def has_two_factor(self) -> bool:
        device = getattr(self, "two_factor", None)
        return bool(device and device.confirmed_at)

    @property
    def requires_two_factor(self) -> bool:
        """Mandatory for every administrative role, without exception."""
        return bool(self.admin_role) or self.is_staff or self.is_superuser


class LegalAcceptance(TimestampedModel):
    """A user's acceptance of one version of a legal document.

    Recorded at signup, and again whenever a document's version changes and
    the user accepts the new one — so the platform can show exactly which
    Terms a person agreed to and when (GDPR Art. 7(1) accountability; also the
    contract record if a dispute ever turns on what was agreed). Never edited
    after the fact: a new version is a new row.
    """

    class Document(models.TextChoices):
        TERMS = "terms", "Terms of Service"
        PRIVACY = "privacy", "Privacy Policy"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="legal_acceptances")
    document = models.CharField(max_length=16, choices=Document.choices)
    version = models.CharField(max_length=20)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "document", "version"], name="one_acceptance_per_document_version"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} accepted {self.document} v{self.version}"


# --- Profile faces ---------------------------------------------------------


class SellerProfile(TimestampedModel):
    """The seller face. Statistics here are computed by the platform and are
    never user-editable (Section 8.2)."""

    class Availability(models.TextChoices):
        AVAILABLE = "available", "Available now"
        LIMITED = "limited", "Limited availability"
        UNAVAILABLE = "unavailable", "Unavailable"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="seller_profile")
    overview = models.TextField(blank=True)
    skills = models.JSONField(default=list, blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    availability = models.CharField(
        max_length=16, choices=Availability.choices, default=Availability.AVAILABLE
    )
    hours_per_week = models.PositiveSmallIntegerField(null=True, blank=True)

    # Platform-computed. Written only by `accounts.reputation.recompute_for`,
    # never by a serializer, a view, or the admin.
    job_success_score = models.PositiveSmallIntegerField(null=True, blank=True)
    contracts_completed = models.PositiveIntegerField(default=0)
    on_time_delivery_rate = models.PositiveSmallIntegerField(null=True, blank=True)
    response_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    repeat_client_rate = models.PositiveSmallIntegerField(null=True, blank=True)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    #: Denormalised onto the profile because search ranks and filters by it on
    #: every query; deriving it per row would make the ladder a subquery.
    level = models.CharField(
        max_length=12,
        choices=[
            ("new", "New seller"),
            ("level_one", "Level 1"),
            ("level_two", "Level 2"),
            ("top_rated", "Top Rated"),
        ],
        default="new",
        db_index=True,
    )
    reputation_updated_at = models.DateTimeField(null=True, blank=True, db_index=True)

    def __str__(self) -> str:
        return f"Seller profile for {self.user.email}"


class BuyerProfile(TimestampedModel):
    """The buyer face. Two-way accountability matters, so hiring history is
    tracked as carefully as seller history (Section 8.3)."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="buyer_profile")
    company_name = models.CharField(max_length=140, blank=True)
    industry = models.CharField(max_length=80, blank=True)
    company_size = models.CharField(max_length=32, blank=True)
    payment_verified = models.BooleanField(default=False)

    contracts_posted = models.PositiveIntegerField(default=0)
    hire_rate = models.PositiveSmallIntegerField(null=True, blank=True)
    average_rating_given = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )

    def __str__(self) -> str:
        return f"Buyer profile for {self.user.email}"


# --- Credentials -----------------------------------------------------------


def _hash(raw: str) -> str:
    """Tokens and codes are stored hashed, never in the clear."""
    return hashlib.sha256(raw.encode()).hexdigest()


class SecurityToken(TimestampedModel):
    """Single-use, expiring tokens and codes.

    Covers email confirmation, password recovery, and the SMS/email OTPs. All
    of them share the same rules — single use, short expiry, invalidated on use
    — so they share one table rather than three near-identical ones.
    """

    class Purpose(models.TextChoices):
        EMAIL_VERIFY = "email_verify", "Email verification"
        PASSWORD_RESET = "password_reset", "Password reset"
        PHONE_OTP = "phone_otp", "Phone verification"
        STUDENT_EMAIL_OTP = "student_email_otp", "University email verification"
        #: Sent when an account with no authenticator signs in from a device it
        #: has never used. Standing in for the second factor that user has not
        #: enrolled, so a stolen password alone is never enough.
        DEVICE_VERIFY = "device_verify", "New device verification"

    #: Section 6.2: OTPs allow at most five attempts before they are burned.
    MAX_ATTEMPTS = 5
    LIFETIMES = {
        Purpose.EMAIL_VERIFY: timedelta(hours=24),
        Purpose.PASSWORD_RESET: timedelta(minutes=30),
        Purpose.PHONE_OTP: timedelta(minutes=10),
        Purpose.STUDENT_EMAIL_OTP: timedelta(minutes=10),
        # Short: the user is sitting at the sign-in screen waiting for it.
        Purpose.DEVICE_VERIFY: timedelta(minutes=10),
    }

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="security_tokens")
    purpose = models.CharField(max_length=32, choices=Purpose.choices, db_index=True)
    token_hash = models.CharField(max_length=64, db_index=True)
    #: For OTPs sent somewhere other than the account's primary address.
    destination = models.CharField(max_length=255, blank=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["user", "purpose", "used_at"])]

    def __str__(self) -> str:
        return f"{self.purpose} for {self.user_id}"

    @property
    def is_usable(self) -> bool:
        return (
            self.used_at is None
            and self.attempts < self.MAX_ATTEMPTS
            and self.expires_at > timezone.now()
        )

    @classmethod
    def issue(cls, user: User, purpose: str, *, destination: str = "", digits: int = 0):
        """Create a token and return ``(row, raw_value)``.

        Any earlier unused token for the same purpose is burned first, so a
        user always has exactly one live code and an old email cannot be
        replayed after a new one is requested.
        """
        cls.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(
            used_at=timezone.now()
        )
        raw = f"{secrets.randbelow(10**digits):0{digits}d}" if digits else secrets.token_urlsafe(32)
        row = cls.objects.create(
            user=user,
            purpose=purpose,
            token_hash=_hash(raw),
            destination=destination,
            expires_at=timezone.now() + cls.LIFETIMES[purpose],
        )
        return row, raw

    @classmethod
    def consume(cls, user: User, purpose: str, raw: str) -> bool:
        """Verify and burn a token. Returns whether it was valid."""
        row = (
            cls.objects.filter(user=user, purpose=purpose, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if row is None or not row.is_usable:
            return False
        if not secrets.compare_digest(row.token_hash, _hash(raw)):
            row.attempts += 1
            row.save(update_fields=["attempts", "updated_at"])
            return False
        row.used_at = timezone.now()
        row.save(update_fields=["used_at", "updated_at"])
        return True


class RefreshSession(TimestampedModel):
    """One device's refresh token, and the family it belongs to.

    Section 6.3 requires rotation with reuse detection: presenting an already
    consumed refresh token invalidates the entire token family and forces
    re-authentication. That is what contains a stolen token — the thief's use
    and the victim's next use cannot both succeed, and whichever happens second
    kills the family.

    The family is also what the "active sessions" screen lists and what a user
    revokes when they sign a device out.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    family = models.UUIDField(db_index=True)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    #: Set when this token is rotated away. A token with a successor that is
    #: presented again is, by definition, a replay.
    rotated_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    device_label = models.CharField(max_length=120, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-last_seen_at"]

    def __str__(self) -> str:
        return f"Session {self.family} for {self.user_id}"

    @property
    def is_live(self) -> bool:
        return (
            self.revoked_at is None and self.rotated_at is None and self.expires_at > timezone.now()
        )

    @staticmethod
    def hash_token(raw: str) -> str:
        return _hash(raw)

    def revoke_family(self) -> int:
        """Kill every token in this family, live or already rotated."""
        return RefreshSession.objects.filter(
            user_id=self.user_id, family=self.family, revoked_at__isnull=True
        ).update(revoked_at=timezone.now())


class StudentVerification(TimestampedModel):
    """One attempt to prove membership of a university.

    Kept as its own row rather than as more columns on `User` for two reasons.
    A rejected attempt has to survive — a reviewer needs to see that this person
    already tried twice with a doctored card — and the denormalised state on
    `User` (`university`, `student_verification_status`) is read on *every*
    scoped request by `core.scope.resolve_for`, so it must stay a cheap column
    read rather than a join.

    That makes `User` the fast path and this the record of how it got there. The
    two are kept in step by `approve()` and `reject()`, which are the only
    supported ways to move the state.
    """

    class Status(models.TextChoices):
        EMAIL_PENDING = "email_pending", "Awaiting email confirmation"
        AWAITING_ID = "awaiting_id", "Awaiting student ID card"
        UNDER_REVIEW = "under_review", "Awaiting reviewer"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="student_verifications")
    university = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name="verifications"
    )
    #: The university address being proved. Deliberately separate from
    #: `User.email`: the account is very often a personal address, and forcing
    #: students to sign up with an address they lose at graduation would be a
    #: guaranteed account-recovery problem in three years' time.
    university_email = models.EmailField()
    email_verified_at = models.DateTimeField(null=True, blank=True)

    id_card = models.ForeignKey(
        "core.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.EMAIL_PENDING, db_index=True
    )

    reviewed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    #: Shown to the student verbatim, so it has to be written for them.
    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]
        constraints = [
            # One live attempt per user. A student who wants to try a different
            # university must have the previous attempt resolved first, which
            # keeps the review queue free of duplicates competing for a decision.
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status__in=["email_pending", "awaiting_id", "under_review"]),
                name="one_open_student_verification_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.university_email} → {self.university.short_code} ({self.status})"

    @property
    def is_open(self) -> bool:
        return self.status in {
            self.Status.EMAIL_PENDING,
            self.Status.AWAITING_ID,
            self.Status.UNDER_REVIEW,
        }

    def mark_email_verified(self) -> None:
        """Advance past the email step, and finish outright where that is all
        the university asks for."""
        self.email_verified_at = timezone.now()
        self.status = (
            self.Status.AWAITING_ID if self.university.require_id_card else self.Status.UNDER_REVIEW
        )
        self.save(update_fields=["email_verified_at", "status", "updated_at"])

    def approve(self, reviewer: User | None = None) -> None:
        """Grant the student their portal.

        This is the single write that opens a university surface to a user, so
        it is also the only place `User.university` is set. Anything else
        setting it would be a way into a portal that never passed review.
        """
        self.status = self.Status.APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])

        self.user.university = self.university
        self.user.student_verification_status = VerificationStatus.VERIFIED
        self.user.student_verified_at = timezone.now()
        self.user.save(
            update_fields=[
                "university",
                "student_verification_status",
                "student_verified_at",
                "updated_at",
            ]
        )

    def reject(self, reason: str, reviewer: User | None = None) -> None:
        self.status = self.Status.REJECTED
        self.rejection_reason = reason
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "rejection_reason",
                "reviewed_by",
                "reviewed_at",
                "updated_at",
            ]
        )

        # Revoking the portal is the whole point of a rejection that follows an
        # earlier approval — a student who has graduated or was mis-approved
        # must lose the surface, not merely stop gaining one.
        if self.user.university_id == self.university_id:
            self.user.university = None
            self.user.student_verification_status = VerificationStatus.REJECTED
            self.user.student_verified_at = None
            self.user.save(
                update_fields=[
                    "university",
                    "student_verification_status",
                    "student_verified_at",
                    "updated_at",
                ]
            )


class KnownDevice(TimestampedModel):
    """A device this account has signed in from before, and when it earned trust.

    A correct password arriving from a device nobody has ever seen is the
    clearest cheap signal of a stolen credential. Blocking the session outright
    would be wrong — that case is overwhelmingly a real person on a new laptop —
    so instead the device gets full read access immediately and a hold on
    anything that moves money until ``trusted_at`` passes. The alert email sent
    at the same moment is what makes the window useful: it gives the real owner
    time to revoke before a thief can spend anything.

    The fingerprint is a keyed hash of a random id the device keeps: a
    long-lived cookie in a browser, secure storage in the app
    (`accounts.devices`). Rows from before D52 were keyed by the user agent and
    are re-keyed to the id the next time that device signs in. It is a
    heuristic for "have we seen this before", never an authentication factor.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    fingerprint = models.CharField(max_length=64)
    label = models.CharField(max_length=120, blank=True)
    first_ip = models.GenericIPAddressField(null=True, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    #: When this device may begin transacting. Set on creation to first-seen
    #: plus the cool-off window, and brought forward when the user confirms the
    #: device from a session that is already trusted.
    trusted_at = models.DateTimeField()

    class Meta:
        ordering = ["-last_seen_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "fingerprint"], name="unique_device_per_user")
        ]

    def __str__(self) -> str:
        return f"Device {self.fingerprint[:8]} for {self.user_id}"

    @property
    def is_trusted(self) -> bool:
        return self.trusted_at <= timezone.now()

    @property
    def seconds_until_trusted(self) -> int:
        remaining = (self.trusted_at - timezone.now()).total_seconds()
        return max(int(remaining), 0)


class TwoFactorDevice(TimestampedModel):
    """TOTP enrolment. The shared secret is encrypted at field level."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="two_factor")
    secret = EncryptedTextField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    #: Hashes only. Recovery codes are shown exactly once, at enrolment.
    recovery_code_hashes = models.JSONField(default=list, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    #: The TOTP time-step of the last accepted code. A code from that step or
    #: earlier is refused, so a code read over someone's shoulder cannot be
    #: replayed inside its own validity window.
    last_used_counter = models.BigIntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return f"2FA for {self.user_id}"

    @staticmethod
    def generate_recovery_codes(count: int = 10) -> list[str]:
        return [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(count)]

    def set_recovery_codes(self, codes: list[str]) -> None:
        self.recovery_code_hashes = [_hash(c) for c in codes]

    def consume_recovery_code(self, code: str) -> bool:
        digest = _hash(code.strip().lower())
        if digest not in self.recovery_code_hashes:
            return False
        self.recovery_code_hashes = [h for h in self.recovery_code_hashes if h != digest]
        self.save(update_fields=["recovery_code_hashes", "updated_at"])
        return True
