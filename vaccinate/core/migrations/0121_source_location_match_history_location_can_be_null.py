# Generated by Django 3.2.1 on 2021-05-07 01:25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0120_geography_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sourcelocationmatchhistory",
            name="new_match_location",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="source_location_match_history",
                to="core.location",
            ),
        ),
    ]