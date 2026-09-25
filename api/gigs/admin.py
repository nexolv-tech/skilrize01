from django.contrib import admin

from .models import BuyerRequest, CustomOffer, Gig, GigExtra, Order, Package


class PackageInline(admin.TabularInline):
    model = Package
    extra = 0


class GigExtraInline(admin.TabularInline):
    model = GigExtra
    extra = 0


@admin.register(Gig)
class GigAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "seller",
        "status",
        "visibility",
        "starting_price",
        "orders_count",
        "rating_average",
        "published_at",
    ]
    list_filter = ["status", "visibility", "category"]
    search_fields = ["title", "description", "seller__email"]
    inlines = [PackageInline, GigExtraInline]
    filter_horizontal = ["skills", "gallery"]
    readonly_fields = [
        "slug",
        "impressions",
        "clicks",
        "orders_count",
        "rating_average",
        "rating_count",
        "published_at",
    ]
    actions = ["deny_gigs"]

    def get_queryset(self, request):
        return Gig.objects.unscoped().select_related("seller", "category")

    @admin.action(description="Deny selected gigs (removes from catalogue)")
    def deny_gigs(self, request, queryset):
        self.message_user(request, f"{queryset.update(status=Gig.Status.DENIED)} gig(s) denied.")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "gig", "buyer", "seller", "price", "status", "due_at", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["gig__title", "buyer__email", "seller__email"]
    # Snapshots are the record of what was bought and must not be edited.
    readonly_fields = [
        "package_snapshot",
        "price",
        "delivery_days",
        "revisions_allowed",
        "started_at",
        "due_at",
        "delivered_at",
        "accept_by",
        "completed_at",
    ]
    actions = ["void_unpaid"]

    @admin.action(description="Cancel — buyer's payment never received (no refund)")
    def void_unpaid(self, request, queryset):
        from payments.settlement import void_unpaid_order

        voided = sum(
            void_unpaid_order(order, actor=request.user, note=f"By {request.user.email}.")
            for order in queryset
        )
        skipped = queryset.count() - voided
        self.message_user(
            request,
            f"{voided} order(s) cancelled."
            + (f" {skipped} skipped: already delivered, finished or cancelled." if skipped else ""),
        )


@admin.register(BuyerRequest)
class BuyerRequestAdmin(admin.ModelAdmin):
    list_display = ["__str__", "buyer", "budget", "status", "expires_at"]
    list_filter = ["status"]
    search_fields = ["description", "buyer__email"]

    def get_queryset(self, request):
        return BuyerRequest.objects.unscoped().select_related("buyer")


@admin.register(CustomOffer)
class CustomOfferAdmin(admin.ModelAdmin):
    list_display = ["id", "seller", "buyer", "price", "delivery_days", "status", "expires_at"]
    list_filter = ["status"]
    search_fields = ["seller__email", "buyer__email", "description"]
