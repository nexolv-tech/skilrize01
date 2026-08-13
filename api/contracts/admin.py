"""
Interim contract operations.

Funding is a manual admin action until Phase 3 connects a gateway, so this
console is where money currently moves. Every transition is audited, and the
released state is deliberately not editable in bulk.
"""

from django.contrib import admin

from core.models import AuditLog

from .models import Contract, ContractEvent, Milestone, Review, TimeEntry, Trial


class MilestoneInline(admin.TabularInline):
    model = Milestone
    extra = 0
    readonly_fields = ["funded_at", "delivered_at", "released_at"]


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "client",
        "freelancer",
        "contract_type",
        "status",
        "total_amount",
        "hourly_rate",
        "created_at",
    ]
    list_filter = ["status", "contract_type", "visibility"]
    search_fields = ["title", "client__email", "freelancer__email"]
    inlines = [MilestoneInline]
    readonly_fields = [
        "terms",
        "accepted_at",
        "started_at",
        "delivered_at",
        "review_deadline",
        "ended_at",
    ]

    def get_queryset(self, request):
        return Contract.objects.unscoped().select_related("client", "freelancer")


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ["title", "contract", "amount", "status", "funded_at", "released_at"]
    list_filter = ["status"]
    search_fields = ["title", "contract__title"]
    actions = ["mark_funded"]

    @admin.action(description="Mark selected milestones as funded")
    def mark_funded(self, request, queryset):
        """Stand-in for a gateway capture webhook until Phase 3."""
        funded = 0
        for milestone in queryset.filter(status=Milestone.Status.PENDING):
            milestone.fund()
            AuditLog.record(
                actor=request.user,
                action=AuditLog.Action.UPDATE,
                target=milestone,
                request=request,
                justification="Milestone funded manually from admin (pre-gateway).",
            )
            funded += 1
        self.message_user(request, f"{funded} milestone(s) marked funded.")


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = [
        "contract",
        "freelancer",
        "worked_on",
        "hours",
        "source",
        "activity_level",
        "is_disputed",
    ]
    list_filter = ["source", "is_disputed", "worked_on"]
    search_fields = ["contract__title", "freelancer__email", "memo"]


@admin.register(ContractEvent)
class ContractEventAdmin(admin.ModelAdmin):
    list_display = ["contract", "kind", "actor", "created_at"]
    list_filter = ["kind", "created_at"]
    search_fields = ["contract__title", "body"]
    readonly_fields = ["contract", "kind", "actor", "body", "payload", "created_at"]


@admin.register(Trial)
class TrialAdmin(admin.ModelAdmin):
    list_display = ["proposal", "amount", "duration_days", "status", "contract", "converted_contract"]
    list_filter = ["status"]
    search_fields = ["proposal__project__title", "proposal__freelancer__email"]
    readonly_fields = ["contract", "converted_contract", "responded_at"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["contract", "author", "subject", "role", "overall", "published_at"]
    list_filter = ["role", "overall", "published_at"]
    search_fields = ["contract__title", "author__email", "subject__email"]
    # Private feedback is never published; it feeds moderation only.
    readonly_fields = ["contract", "author", "subject", "role", "published_at"]
