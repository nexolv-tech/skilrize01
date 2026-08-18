from django.contrib import admin

from .models import EscrowFunding, Payout, PayoutProfile


@admin.register(EscrowFunding)
class EscrowFundingAdmin(admin.ModelAdmin):
    list_display = ["milestone", "amount", "currency", "funded_by", "created_at"]
    search_fields = ["milestone__title", "funded_by__handle", "funded_by__email"]


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    """Where the manual side of this happens: an admin sends the real bank
    transfer for `net_amount`, then marks the row paid here."""

    list_display = [
        "milestone",
        "freelancer",
        "gross_amount",
        "commission_amount",
        "net_amount",
        "status",
        "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["freelancer__handle", "freelancer__email", "milestone__title"]
    readonly_fields = ["gross_amount", "commission_percent", "commission_amount", "net_amount"]
    actions = ["mark_paid"]

    @admin.action(description="Mark selected payouts as paid")
    def mark_paid(self, request, queryset):
        from django.utils import timezone

        updated = queryset.filter(status=Payout.Status.PENDING).update(
            status=Payout.Status.PAID, paid_by=request.user, paid_at=timezone.now()
        )
        self.message_user(request, f"{updated} payout(s) marked paid.")


@admin.register(PayoutProfile)
class PayoutProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "bank_name", "account_title", "created_at"]
    search_fields = ["user__handle", "user__email", "account_title"]
    # account_number / cnic are EncryptedTextField — never surfaced in the
    # list view or as editable admin fields; readonly here is a UI
    # courtesy, not the security boundary (the boundary is that the
    # column is opaque at rest regardless of who queries it).
    readonly_fields = ["account_number", "cnic"]
