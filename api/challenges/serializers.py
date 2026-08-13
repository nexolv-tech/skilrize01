"""Shapes for the proof-of-work challenges API."""

from __future__ import annotations

from rest_framework import serializers

from core.files import signed_url

from .models import Badge, Challenge, Participation


class ChallengeSerializer(serializers.ModelSerializer):
    """Read shape. Writes go through `ChallengeCreateSerializer` — staff only."""

    skill_name = serializers.CharField(source="skill.name", read_only=True, default=None)
    reference_file_url = serializers.SerializerMethodField()
    participant_count = serializers.IntegerField(read_only=True)
    graded_count = serializers.IntegerField(read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    human_weight = serializers.IntegerField(read_only=True)
    #: The caller's own attempt, if any — lets the client show "Continue" vs
    #: "Join" without a second request per challenge.
    my_participation_id = serializers.SerializerMethodField()

    class Meta:
        model = Challenge
        fields = [
            "id",
            "slug",
            "title",
            "brief",
            "skill",
            "skill_name",
            "reference_file_url",
            "duration_hours",
            "automated_weight",
            "human_weight",
            "status",
            "opens_at",
            "closes_at",
            "participant_count",
            "graded_count",
            "is_open",
            "my_participation_id",
            "created_at",
        ]
        read_only_fields = fields

    def get_reference_file_url(self, obj: Challenge) -> str | None:
        f = obj.reference_file
        return signed_url(f) if f and f.is_downloadable else None

    def get_my_participation_id(self, obj: Challenge) -> int | None:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        # Prefetched by the view as `my_participations` to avoid an N+1 across
        # a list of challenges; falls back to a direct query for detail views.
        prefetched = getattr(obj, "my_participations", None)
        if prefetched is not None:
            return prefetched[0].id if prefetched else None
        participation = obj.participations.filter(user=request.user).first()
        return participation.id if participation else None


class ChallengeCreateSerializer(serializers.ModelSerializer):
    """Staff-only. `created_by` is set by the view, never from the request body."""

    class Meta:
        model = Challenge
        fields = [
            "id",
            "slug",
            "title",
            "brief",
            "skill",
            "reference_file",
            "duration_hours",
            "automated_weight",
            "status",
            "opens_at",
            "closes_at",
        ]
        read_only_fields = ["id", "slug"]

    def validate_reference_file(self, value):
        request = self.context.get("request")
        if value and request and value.owner_id != request.user.id:
            raise serializers.ValidationError("You can only attach a file you uploaded.")
        return value


class ParticipationSerializer(serializers.ModelSerializer):
    """Read-only. Submitting and reviewing happen through dedicated actions,
    not by writing fields on this serializer directly."""

    challenge_title = serializers.CharField(source="challenge.title", read_only=True)
    challenge_slug = serializers.CharField(source="challenge.slug", read_only=True)
    user_handle = serializers.CharField(source="user.handle", read_only=True)
    user_display_name = serializers.CharField(source="user.display_name", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Participation
        fields = [
            "id",
            "challenge",
            "challenge_title",
            "challenge_slug",
            "user",
            "user_handle",
            "user_display_name",
            "started_at",
            "deadline",
            "status",
            "is_overdue",
            "submission_url",
            "repo_url",
            "notes",
            "submitted_at",
            "automated_status",
            "automated_score",
            "automated_report",
            "automated_graded_at",
            "human_score",
            "human_notes",
            "reviewed_at",
            "final_score",
        ]
        read_only_fields = fields


class SubmissionInputSerializer(serializers.Serializer):
    submission_url = serializers.URLField(max_length=500)
    repo_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class HumanReviewInputSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=0, max_value=100)
    notes = serializers.CharField(required=False, allow_blank=True)


class BadgeSerializer(serializers.ModelSerializer):
    """Embedded on public profiles — the 'VERIFIED SKILL' display."""

    challenge_title = serializers.CharField(source="challenge.title", read_only=True)
    challenge_slug = serializers.CharField(source="challenge.slug", read_only=True)
    skill_name = serializers.CharField(source="challenge.skill.name", read_only=True, default=None)
    label = serializers.CharField(read_only=True)

    class Meta:
        model = Badge
        fields = [
            "id",
            "challenge",
            "challenge_title",
            "challenge_slug",
            "skill_name",
            "final_score",
            "top_percent",
            "label",
            "awarded_at",
        ]
        read_only_fields = fields
