# Generated by Django 3.2.4 on 2021-07-08 18:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0155_alter_county_vts_priorty"),
    ]

    operations = [
        migrations.AddField(
            model_name="location",
            name="hours_json",
            field=models.JSONField(
                blank=True,
                help_text="Structured hours information from one of our scrapers",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="location",
            name="hours_json_last_updated_at",
            field=models.DateTimeField(
                blank=True, help_text="When hours_json was last updated", null=True
            ),
        ),
        migrations.AddField(
            model_name="location",
            name="hours_json_provenance_source_location",
            field=models.ForeignKey(
                blank=True,
                help_text="The source location that last populated hours_json",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="core.sourcelocation",
            ),
        ),
    ]
