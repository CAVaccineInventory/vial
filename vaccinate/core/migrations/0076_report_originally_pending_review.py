# Generated by Django 3.1.8 on 2021-04-12 08:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0075_various_model_field_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="report",
            name="originally_pending_review",
            field=models.BooleanField(
                help_text="Reports that were originally flagged as pending review",
                null=True,
            ),
        ),
    ]