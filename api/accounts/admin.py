"""
Interim operations console for identity.

Access to identity documents is logged per view (Section 7.3), so the admin
never renders the image itself — it links out through the same short-lived
signed URL every other consumer uses, and records who looked.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from core.files import signed_url
from core.models import AuditLog

from .models import (
    ApprovedEmailDomain,
    BuyerProfile,
    RefreshSession,
    SellerProfile,
    TwoFactorDevice,
    University,
    User,
)


class ApprovedEmailDomainInline(admin.TabularInline):
    model = ApprovedEmailDomain
    extra = 1


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ["name", "short_code", "city", "require_id_card", "is_active", "student_count"]
    list_filter = ["is_active", "require_id_card"]
    search_fields = ["name", "short_code"]
    inlines = [ApprovedEmailDomainInline]

    @admin.display(description="Students")
    def student_count(self, obj: University) -> int:
        return obj.students.count()


class SellerProfileInline(admin.StackedInline):
    model = SellerProfile
    can_delete = False
    readonly_fields = [
        "job_success_score",
        "contracts_completed",
        "on_time_delivery_rate",
        "response_time_minutes",
        "repeat_client_rate",
    ]


class BuyerProfileInline(admin.StackedInline):
    model = BuyerProfile
    can_delete = False
    readonly_fields = ["contracts_posted", "hire_rate", "average_rating_given"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-created_at"]
    list_display = [
        "email",
        "full_name",
        "profile_state",
        "identity_status",
        "student_verification_status",
        "university",
        "admin_role",
        "is_active",
    ]
    list_filter = ["is_active", "identity_status", "student_verification_status", "admin_role"]
    search_fields = ["email", "handle", "full_name", "phone_number"]
    readonly_fields = ["last_login", "created_at", "updated_at", "identity_document_link"]
    inlines = [SellerProfileInline, BuyerProfileInline]
    filter_horizontal = ["groups", "user_permissions"]

    fieldsets = (
        (None, {"fields": ("email", "password", "handle")}),
        (
            "Profile",
            {
                "fields": (
                    "full_name",
                    "headline",
                    "bio",
                    "avatar",
                    "country",
                    "city",
                    "timezone_name",
                    "languages",
                    "profile_visibility",
                )
            },
        ),
        (
            "Verification",
            {
                "fields": (
                    "email_verified",
                    "phone_number",
                    "phone_verified",
                    "identity_status",
                    "identity_document_link",
                )
            },
        ),
        (
            "University",
            {"fields": ("university", "student_verification_status", "student_verified_at")},
        ),
        (
            "Access",
            {
                "fields": (
                    "admin_role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Timestamps", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "full_name")}),
    )

    @admin.display(description="Profile", boolean=True)
    def profile_state(self, obj: User) -> bool:
        return obj.profile_complete

    @admin.display(description="Identity document")
    def identity_document_link(self, obj: User):
        if not obj.identity_document:
            return "—"
        return format_html(
            '<a href="{}" rel="noopener">Open (expires in minutes, access is logged)</a>',
            signed_url(obj.identity_document),
        )

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field)
        # Opening a user record in admin is a read of personal data.
        if obj is not None and obj.identity_document_id:
            AuditLog.record(
                actor=request.user,
                action=AuditLog.Action.READ_SENSITIVE,
                target=obj,
                request=request,
                justification="Identity record opened in admin.",
            )
        return obj


@admin.register(RefreshSession)
class RefreshSessionAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "device_label",
        "ip_address",
        "last_seen_at",
        "expires_at",
        "rotated_at",
        "revoked_at",
    ]
    list_filter = ["created_at"]
    search_fields = ["user__email", "ip_address"]
    readonly_fields = ["token_hash", "family"]


@admin.register(TwoFactorDevice)
class TwoFactorDeviceAdmin(admin.ModelAdmin):
    list_display = ["user", "confirmed_at", "last_used_at"]
    search_fields = ["user__email"]
    # The shared secret is never rendered, even to a Super Admin.
    exclude = ["secret", "recovery_code_hashes"]
    readonly_fields = ["confirmed_at", "last_used_at"]
