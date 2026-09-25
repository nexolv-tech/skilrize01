"""
Schedules `auto_release_deliveries` hourly.

Both review windows — three days on a gig order, seven on a contract
milestone — were defined and promised to users in notifications since
Phases 1 and 2, but nothing ever enforced them: a buyer who never answered a
delivery held the seller's money indefinitely. Hourly is fine-grained enough
that nobody waits a meaningful extra amount past a multi-day window.
"""

from __future__ import annotations

from django.db import migrations

NAME = "auto-release-deliveries"
TASK = "core.tasks.auto_release_deliveries"


def seed(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute="7",
        hour="*",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )
    PeriodicTask.objects.get_or_create(
        name=NAME, defaults={"task": TASK, "crontab": crontab, "enabled": True}
    )


def unseed(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_pushdevice"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
