# Generated by Django 3.2.2 on 2021-05-10 01:41

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0124_unique_call_requests"),
    ]

    operations = [
        migrations.AlterField(
            model_name="callrequest",
            name="created_at",
            field=models.DateTimeField(
                blank=True,
                default=django.utils.timezone.now,
                help_text="the time the call request entered the queue.",
                null=True,
            ),
        ),
    ]
