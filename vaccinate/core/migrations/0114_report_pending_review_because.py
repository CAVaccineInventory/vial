# Generated by Django 3.2 on 2021-04-30 06:48

import core.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0113_populate_last_imported_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="report",
            name="pending_review_because",
            field=core.fields.CharTextField(
                blank=True,
                help_text="Reason this was originally flagged for review",
                max_length=65000,
                null=True,
            ),
        ),
    ]