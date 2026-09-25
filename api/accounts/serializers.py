"""Request and response shapes for the identity API."""

from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from core.files import signed_url
from core.models import AuditLog

from .models import (
    BuyerProfile,
    RefreshSession,
    SellerProfile,
    StudentVerification,
    University,
    User,
)


class UniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = University
        fields = ["id", "name", "short_code", "city", "brand_color"]
        read_only_fields = fields


def _badges_for(user) -> list:
    """Verified-skill badges, most recent first.

    Imported lazily — `challenges` depends on nothing in `accounts` beyond the
    user FK every app has, but importing it at module load time would still
    make identity's own serializer module load order depend on a much later
    phase for no benefit.
    """
    from challenges.serializers import BadgeSerializer

    badges = user.challenge_badges.select_related("challenge", "challenge__skill").order_by(
        "-awarded_at"
    )
    return BadgeSerializer(badges, many=True).data


class SellerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerProfile
        fields = [
            "overview",
            "skills",
            "hourly_rate",
            "availability",
            "hours_per_week",
            "job_success_score",
            "contracts_completed",
            "on_time_delivery_rate",
            "response_time_minutes",
            "repeat_client_rate",
        ]
        # Section 8.2: statistics are computed by the platform and are not
        # editable by the user.
        read_only_fields = [
            "job_success_score",
            "contracts_completed",
            "on_time_delivery_rate",
            "response_time_minutes",
            "repeat_client_rate",
        ]


class BuyerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = BuyerProfile
        fields = [
            "company_name",
            "industry",
            "company_size",
            "payment_verified",
            "contracts_posted",
            "hire_rate",
            "average_rating_given",
        ]
        read_only_fields = [
            "payment_verified",
            "contracts_posted",
            "hire_rate",
            "average_rating_given",
        ]


class UserSerializer(serializers.ModelSerializer):
    """The authenticated user's own view of their account."""

    display_name = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    university = UniversitySerializer(read_only=True)
    seller_profile = SellerProfileSerializer(read_only=True)
    buyer_profile = BuyerProfileSerializer(read_only=True)

    profile_complete = serializers.BooleanField(read_only=True)
    can_transact = serializers.BooleanField(read_only=True)
    missing_requirements = serializers.SerializerMethodField()
    is_verified_student = serializers.BooleanField(read_only=True)
    has_two_factor = serializers.BooleanField(read_only=True)
    profile_strength = serializers.SerializerMethodField()
    badges = serializers.SerializerMethodField()
    admin_role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "handle",
            "full_name",
            "display_name",
            "avatar_url",
            "headline",
            "bio",
            "country",
            "city",
            "timezone_name",
            "languages",
            "profile_visibility",
            "email_verified",
            "phone_number",
            "phone_verified",
            "identity_status",
            "university",
            "student_verification_status",
            "is_verified_student",
            "admin_role",
            "profile_complete",
            "can_transact",
            "missing_requirements",
            "has_two_factor",
            "profile_strength",
            "seller_profile",
            "buyer_profile",
            "badges",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "email",
            "handle",
            "email_verified",
            "phone_verified",
            "identity_status",
            "student_verification_status",
            "admin_role",
            "created_at",
        ]

    def get_avatar_url(self, user: User) -> str | None:
        return signed_url(user.avatar) if user.avatar and user.avatar.is_downloadable else None

    def get_missing_requirements(self, user: User) -> list[str]:
        return user.missing_profile_requirements()

    def get_admin_role(self, user: User) -> str:
        """A Django superuser is a Super Admin to the API
        (`require_admin_role`), so the console treats them as one too."""
        if user.is_superuser and not user.admin_role:
            return User.AdminRole.SUPER_ADMIN
        return user.admin_role

    def get_profile_strength(self, user: User) -> int:
        """A completion meter, because complete profiles convert far better and
        users respond to a visible progress indicator (Section 8.4)."""
        checks = [
            user.email_verified,
            user.phone_verified,
            user.identity_status == "verified",
            bool(user.full_name),
            bool(user.headline),
            bool(user.bio),
            bool(user.avatar_id),
            bool(user.country),
            bool(user.languages),
            user.has_two_factor,
        ]
        return round(100 * sum(bool(c) for c in checks) / len(checks))

    def get_badges(self, user: User) -> list:
        return _badges_for(user)


class PublicUserSerializer(serializers.ModelSerializer):
    """What anyone else sees. Deliberately narrow.

    Contact details are never displayed publicly, earnings are never exact, and
    student portal activity never appears here (Section 8.4).
    """

    display_name = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    is_verified_student = serializers.BooleanField(read_only=True)
    university_name = serializers.CharField(source="university.name", read_only=True)
    seller_profile = SellerProfileSerializer(read_only=True)
    badges = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "handle",
            "display_name",
            "avatar_url",
            "headline",
            "bio",
            "country",
            "city",
            "languages",
            "is_verified_student",
            "university_name",
            "seller_profile",
            "badges",
            "created_at",
        ]
        read_only_fields = fields

    def get_avatar_url(self, user: User) -> str | None:
        return signed_url(user.avatar) if user.avatar and user.avatar.is_downloadable else None

    def get_badges(self, user: User) -> list:
        return _badges_for(user)


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    full_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    #: One checkbox, never pre-ticked: "I'm 18 or older and I accept the Terms
    #: of Service and Privacy Policy." Enforced here rather than trusted to the
    #: form, because an account that never accepted the Terms has no contract
    #: with the platform at all.
    accept_terms = serializers.BooleanField()

    def validate_accept_terms(self, value: bool) -> bool:
        if value is not True:
            raise serializers.ValidationError(
                "Confirm you're 18 or older and accept the Terms of Service and Privacy "
                "Policy to create an account."
            )
        return value

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            # Signup does reveal that an address is taken — it has to, or the
            # user cannot proceed. Password *recovery* is where enumeration is
            # avoided, and it is handled accordingly.
            raise serializers.ValidationError("An account with this email already exists.")
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TwoFactorChallengeSerializer(serializers.Serializer):
    challenge = serializers.CharField()
    code = serializers.CharField(max_length=32)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, validators=[validate_password])


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])


class OTPSerializer(serializers.Serializer):
    code = serializers.CharField(min_length=4, max_length=8)


class PhoneSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)


class StudentEmailSerializer(serializers.Serializer):
    university_email = serializers.EmailField()


class StudentVerificationSerializer(serializers.ModelSerializer):
    """The student's own view of where their application has got to."""

    university = UniversitySerializer(read_only=True)
    id_card_required = serializers.SerializerMethodField()
    next_step = serializers.SerializerMethodField()

    class Meta:
        model = StudentVerification
        fields = [
            "id",
            "university",
            "university_email",
            "email_verified_at",
            "status",
            "rejection_reason",
            "id_card_required",
            "next_step",
            "created_at",
            "reviewed_at",
        ]
        read_only_fields = fields

    def get_id_card_required(self, row: StudentVerification) -> bool:
        return row.university.require_id_card

    def get_next_step(self, row: StudentVerification) -> str:
        """What the student has to do now, decided server-side.

        The client renders whatever this says rather than re-deriving it from
        the status. Two implementations of the same branching is how the UI
        ends up telling someone to upload a card the university does not ask
        for.
        """
        return {
            StudentVerification.Status.EMAIL_PENDING: "confirm_email",
            StudentVerification.Status.AWAITING_ID: "upload_id_card",
            StudentVerification.Status.UNDER_REVIEW: "wait_for_review",
            StudentVerification.Status.APPROVED: "done",
            StudentVerification.Status.REJECTED: "start_again",
        }[row.status]


class SessionSerializer(serializers.ModelSerializer):
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = RefreshSession
        fields = [
            "id",
            "family",
            "device_label",
            "ip_address",
            "last_seen_at",
            "created_at",
            "is_current",
        ]
        read_only_fields = fields

    def get_is_current(self, session: RefreshSession) -> bool:
        return str(session.family) == self.context.get("current_family")


class StepUpSerializer(serializers.Serializer):
    """Proof required before a sensitive change (Section 6.4)."""

    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    code = serializers.CharField(required=False, allow_blank=True)


# --- Admin console (Phase 9) -------------------------------------------------


class AdminStudentVerificationSerializer(serializers.ModelSerializer):
    """A reviewer's view of one application — unlike the student's own
    `StudentVerificationSerializer`, this exposes who is applying and the
    submitted document itself."""

    applicant_handle = serializers.CharField(source="user.handle", read_only=True)
    applicant_name = serializers.CharField(source="user.display_name", read_only=True)
    applicant_email = serializers.EmailField(source="user.email", read_only=True)
    university_name = serializers.CharField(source="university.name", read_only=True)
    id_card_url = serializers.SerializerMethodField()
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.display_name", read_only=True, default=None
    )

    class Meta:
        model = StudentVerification
        fields = [
            "id",
            "applicant_handle",
            "applicant_name",
            "applicant_email",
            "university_name",
            "university_email",
            "email_verified_at",
            "id_card_url",
            "status",
            "rejection_reason",
            "reviewed_by_name",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_id_card_url(self, row: StudentVerification) -> str | None:
        card = row.id_card
        return signed_url(card) if card and card.is_downloadable else None


class AdminRejectVerificationSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class AdminUserSerializer(serializers.ModelSerializer):
    """A support/admin view of an account — more than `PublicUserSerializer`
    shows anyone, but still no payment instruments or documents beyond what
    the verification queue already exposes on its own screen."""

    avatar_url = serializers.SerializerMethodField()
    university_name = serializers.CharField(source="university.name", read_only=True, default=None)
    #: Erased by its owner (GDPR): nothing can be done to it but look.
    is_erased = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "handle",
            "email",
            "full_name",
            "display_name",
            "avatar_url",
            "admin_role",
            "is_active",
            "is_erased",
            "is_staff",
            "email_verified",
            "phone_verified",
            "identity_status",
            "is_verified_student",
            "university_name",
            "created_at",
        ]
        read_only_fields = fields

    def get_avatar_url(self, user: User) -> str | None:
        return signed_url(user.avatar) if user.avatar and user.avatar.is_downloadable else None

    def get_is_erased(self, user: User) -> bool:
        return user.deleted_at is not None


class AdminSuspendUserSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class AdminAuditLogSerializer(serializers.ModelSerializer):
    """Read-only, deliberately — nothing about this log is ever editable
    through the API, matching `core.admin.AuditLogAdmin`'s own restriction."""

    actor_name = serializers.CharField(source="actor.display_name", read_only=True, default=None)
    actor_email = serializers.EmailField(source="actor.email", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "created_at",
            "actor_name",
            "actor_email",
            "action",
            "target_type",
            "target_id",
            "justification",
            "ip_address",
            "request_id",
        ]
        read_only_fields = fields
