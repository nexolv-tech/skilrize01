"""
Wires Celery Beat's `DatabaseScheduler` (already configured,
`CELERY_BEAT_SCHEDULER` in settings) to the six periodic tasks that have
existed as complete, correct `@shared_task`s with nobody ever calling them —
`sweep_promotions`, `sweep_challenge_deadlines`, and `sweep_activity_sources`
said so directly in their own docstrings; `reindex_search`,
`refresh_reputation`, and `assess_review_integrity` carried the identical gap
without saying so. First time this codebase actually creates
`PeriodicTask`/`CrontabSchedule` rows — Phase 11 (D37).

Cadence is chosen per task's own cost and how stale its effect is allowed to
get, not a single blanket interval:

* `sweep_promotions` — 5 min. Starting/stopping a paid placement on time is
  the entire point of buying one.
* `assess_review_integrity` — 10 min. Runs behind publication already
  (`contracts/integrity.py`); a review sitting unassessed for ten minutes is
  fine, a day is not.
* `sweep_challenge_deadlines` — 15 min. Challenges run in hours, not minutes.
* `refresh_reputation` — 15 min. Same shape as review integrity — background
  housekeeping, bounded by `limit=500` per run either way.
* `sweep_activity_sources` — 30 min. Provider APIs (GitHub, Figma, Notion)
  have their own rate limits; this is a courtesy interval, not a technical
  one, chosen for when providers are enabled.
* `reindex_search` — nightly at 03:00. Its own docstring already says
  "cheap enough to run nightly."
"""

from __future__ import annotations

from django.db import migrations

SCHEDULE = [
    ("sweep-promotions", "core.tasks.sweep_promotions", {"minute": "*/5"}),
    ("assess-review-integrity", "core.tasks.assess_review_integrity", {"minute": "*/10"}),
    ("sweep-challenge-deadlines", "core.tasks.sweep_challenge_deadlines", {"minute": "*/15"}),
    ("refresh-reputation", "core.tasks.refresh_reputation", {"minute": "*/15"}),
    ("sweep-activity-sources", "integrations.tasks.sweep_activity_sources", {"minute": "*/30"}),
    ("reindex-search", "core.tasks.reindex_search", {"minute": "0", "hour": "3"}),
]


def seed(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    for name, task, cron_fields in SCHEDULE:
        crontab, _ = CrontabSchedule.objects.get_or_create(
            minute=cron_fields.get("minute", "*"),
            hour=cron_fields.get("hour", "*"),
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="UTC",
        )
        PeriodicTask.objects.get_or_create(
            name=name, defaults={"task": task, "crontab": crontab, "enabled": True}
        )


def unseed(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name__in=[row[0] for row in SCHEDULE]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_alter_notification_category"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
