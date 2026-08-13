"""
Interim operations console.

Django admin carries operational load until the custom dashboard replaces it.
That makes it a real security surface now, not a developer convenience, so the
audit log is registered strictly read-only and destructive bulk actions are not
offered.
"""

from django.contrib import admin

from .models import AuditLog, Notification, NotificationPreference, PushDevice, StoredFile


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "action", "actor", "target_type", "target_id", "ip_address"]
    list_filter = ["action", "created_at"]
    search_fields = ["actor__email", "target_id", "request_id"]
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        # The log is not deletable through the application, including by a
        # Super Admin (Section 5.2).
        return False


@admin.register(StoredFile)
class StoredFileAdmin(admin.ModelAdmin):
    list_display = [
        "original_name",
        "owner",
        "purpose",
        "content_type",
        "size_bytes",
        "scan_status",
        "created_at",
    ]
    list_filter = ["purpose", "scan_status", "created_at"]
    search_fields = ["original_name", "owner__email", "checksum"]
    # The bytes are never exposed through admin; only metadata is.
    readonly_fields = ["key", "checksum", "content_type", "size_bytes", "original_name"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "category", "read_at", "created_at"]
    list_filter = ["category", "created_at"]
    search_fields = ["title", "user__email"]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ["user", "digest_frequency", "quiet_hours_start", "quiet_hours_end"]
    search_fields = ["user__email"]


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    """The token is readable here and nowhere else in the product — an
    operator diagnosing "why did this phone stop getting notifications"
    needs to see which token is attached and whether it was pruned."""

    list_display = ["user", "platform", "label", "is_active", "last_seen_at"]
    list_filter = ["platform", "is_active"]
    search_fields = ["user__email", "label"]
    readonly_fields = ["token", "last_seen_at", "created_at", "updated_at"]
