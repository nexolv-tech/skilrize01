from django.contrib import admin

from .models import (
    Category,
    Invitation,
    Project,
    Proposal,
    ScreeningAnswer,
    ScreeningQuestion,
    Skill,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["__str__", "slug", "order", "is_active"]
    list_filter = ["is_active", "parent"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "is_approved", "usage_count"]
    # Unapproved skills are free-text additions from users, surfaced here for
    # taxonomy expansion rather than left to fragment the index silently.
    list_filter = ["is_approved", "category"]
    search_fields = ["name"]
    actions = ["approve_skills"]

    @admin.action(description="Approve selected skills")
    def approve_skills(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_approved=True)} skill(s) approved.")


class ScreeningQuestionInline(admin.TabularInline):
    model = ScreeningQuestion
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "client",
        "project_type",
        "status",
        "visibility",
        "proposal_count",
        "published_at",
    ]
    list_filter = ["status", "project_type", "visibility", "experience_level"]
    search_fields = ["title", "description", "client__email"]
    inlines = [ScreeningQuestionInline]
    filter_horizontal = ["skills", "attachments"]
    readonly_fields = ["proposal_count", "published_at", "closed_at"]

    def get_queryset(self, request):
        # Administrative work reaches across every surface deliberately.
        return Project.objects.unscoped().select_related("client", "category")


class ScreeningAnswerInline(admin.TabularInline):
    model = ScreeningAnswer
    extra = 0
    readonly_fields = ["question", "answer"]


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "project",
        "freelancer",
        "status",
        "bid_amount",
        "hourly_rate",
        "created_at",
    ]
    list_filter = ["status", "is_boosted"]
    search_fields = ["project__title", "freelancer__email"]
    inlines = [ScreeningAnswerInline]


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ["project", "freelancer", "status", "expires_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["project__title", "freelancer__email"]
