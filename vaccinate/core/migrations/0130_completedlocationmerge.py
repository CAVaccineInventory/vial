# Generated by Django 3.2.1 on 2021-05-11 19:04

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0129_populate_task_types"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompletedLocationMerge",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "details",
                    models.JSONField(
                        blank=True,
                        help_text="Detailed information about the merge",
                        null=True,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="completed_location_merges",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "loser_location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="core.location",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="completed_location_merges",
                        to="core.task",
                    ),
                ),
                (
                    "winner_location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="core.location",
                    ),
                ),
            ],
            options={
                "db_table": "completed_location_merge",
            },
        ),
    ]