from django.contrib import admin

from .models import EscrowCharge, Payout, PayoutProfile


@admin.register(EscrowCharge)
class EscrowChargeAdmin(admin.ModelAdmin):
    list_display = [
        "customer_transaction_id",
        "milestone",
        "amount",
        "currency",
        "status",
        "created_at",
    ]
    list_filter = ["status", "currency"]
    search_fields = ["customer_transaction_id", "swich_order_id", "milestone__title"]
    readonly_fields = ["callback_payload"]


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = [
        "customer_transaction_id",
        "freelancer",
        "milestone",
        "amount",
        "status",
        "created_at",
    ]
    list_filter = ["status", "currency"]
    search_fields = ["customer_transaction_id", "freelancer__handle", "freelancer__email"]
    readonly_fields = ["swich_response"]


@admin.register(PayoutProfile)
class PayoutProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "bank_name", "verified_account_title", "created_at"]
    search_fields = ["user__handle", "user__email", "verified_account_title"]
    # account_number / cnic are EncryptedTextField — never surfaced in the
    # list view or as editable admin fields; readonly here is a UI courtesy,
    # not the security boundary (the boundary is that the column is opaque
    # at rest regardless of who queries it).
    readonly_fields = ["account_number", "cnic"]
