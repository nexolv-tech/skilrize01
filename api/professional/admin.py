"""Operations console for the professional layer."""

from django.contrib import admin

from .models import (
    Agency,
    AgencyMember,
    Plan,
    RetainerPlan,
    RetainerSubscription,
    Subscription,
    Workspace,
)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    """Pricing and limits live here so they can move without a deploy."""

    list_display = ["name", "tier", "monthly_price", "proposal_quota", "team_seats", "is_public"]
    list_editable = ["monthly_price", "proposal_quota", "team_seats", "is_public"]
    ordering = ["order"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "plan",
        "status",
        "interval",
        "current_period_end",
        "cancel_at_period_end",
    ]
    list_filter = ["status", "interval", "plan"]
    search_fields = ["user__email"]
    readonly_fields = ["started_at"]


class AgencyMemberInline(admin.TabularInline):
    model = AgencyMember
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "seats_used", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug", "owner__email"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [AgencyMemberInline]


@admin.register(RetainerPlan)
class RetainerPlanAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "seller",
        "monthly_price",
        "active_subscriber_count",
        "visibility",
        "is_active",
    ]
    list_filter = ["is_active", "visibility"]
    search_fields = ["title", "seller__email"]

    def get_queryset(self, request):
        # Scopeable: the scoped manager would refuse to run outside a request.
        return self.model.all_objects.all()


@admin.register(RetainerSubscription)
class RetainerSubscriptionAdmin(admin.ModelAdmin):
    list_display = ["plan", "buyer", "status", "months_billed", "current_period_end"]
    list_filter = ["status"]


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ["name", "agency", "created_by", "is_archived", "created_at"]
    list_filter = ["is_archived"]
    search_fields = ["name"]


# `Contact`, `Deal`, `Interaction`, and `Task` are deliberately not imported or
# registered. A CRM pipeline names who somebody is talking to and for how much —
# commercially sensitive in a way a public listing is not — and the surest way
# to keep it out of the console is to give the console no page for it. Lawful
# disclosure goes through an explicit, audited export.
