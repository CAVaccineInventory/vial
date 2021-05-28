# Generated by Django 3.2.3 on 2021-05-28 18:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0139_alter_report_internal_notes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="location",
            name="preferred_contact_method",
            field=models.CharField(
                blank=True,
                choices=[
                    ("research_online", "research_online"),
                    ("outbound_call", "outbound_call"),
                    ("online_only", "online_only"),
                    ("online_preferred", "online_preferred"),
                    ("call_preferred", "call_preferred"),
                    ("call_only", "call_only"),
                ],
                help_text="Preferred method of collecting status about this location",
                max_length=32,
                null=True,
            ),
        ),
    ]
