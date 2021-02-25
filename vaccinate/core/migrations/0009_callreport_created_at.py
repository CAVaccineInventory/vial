# Generated by Django 3.1.7 on 2021-02-25 01:29

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_populate_appointment_tags"),
    ]

    operations = [
        migrations.AlterField(
            model_name="callreport",
            name="created_at",
            field=models.DateTimeField(
                default=datetime.datetime.utcnow,
                help_text="the time when the report was submitted. We will interpret this as a validity time",
            ),
        ),
    ]
