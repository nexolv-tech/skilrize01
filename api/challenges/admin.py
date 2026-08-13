"""Interim operations console for challenges — creating briefs and reviewing
submissions is staff work with no dedicated product UI yet, same status as
the rest of the admin app until Section 9's console replaces it."""

from django.contrib import admin

from .models import Badge, Challenge, Participation


class ParticipationInline(admin.TabularInline):
    model = Participation
    extra = 0
    fields = ["user", "status", "submitted_at", "automated_score", "human_score", "final_score"]
    readonly_fields = fields
    can_delete = False
    show_change_link = True


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ["title", "skill", "status", "automated_weight", "opens_at", "closes_at", "participant_count"]
    list_filter = ["status"]
    search_fields = ["title", "brief"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [ParticipationInline]

    @admin.display(description="Participants")
    def participant_count(self, obj: Challenge) -> int:
        return obj.participant_count


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = [
        "challenge",
        "user",
        "status",
        "automated_status",
        "automated_score",
        "human_score",
        "final_score",
        "deadline",
    ]
    list_filter = ["status", "automated_status", "challenge"]
    search_fields = ["user__handle", "user__email", "challenge__title"]
    readonly_fields = [
        "started_at",
        "submitted_at",
        "automated_status",
        "automated_score",
        "automated_report",
        "automated_graded_at",
        "final_score",
    ]

    fieldsets = (
        (None, {"fields": ("challenge", "user", "status", "started_at", "deadline")}),
        ("Submission", {"fields": ("submission_url", "repo_url", "notes", "submitted_at")}),
        (
            "Automated grading",
            {
                "fields": (
                    "automated_status",
                    "automated_score",
                    "automated_report",
                    "automated_graded_at",
                )
            },
        ),
        (
            "Human review",
            {"fields": ("human_score", "human_notes", "reviewed_by", "reviewed_at")},
        ),
        ("Result", {"fields": ("final_score",)}),
    )


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ["user", "challenge", "final_score", "top_percent", "awarded_at"]
    list_filter = ["challenge"]
    search_fields = ["user__handle", "user__email", "challenge__title"]
    readonly_fields = ["user", "challenge", "participation", "final_score", "top_percent", "awarded_at"]
