# Generated by Django 3.2.3 on 2021-05-17 19:54

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0131_issue_560_repair_merge_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="location",
            name="created_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="location",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="created_locations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
