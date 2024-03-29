# Generated by Django 3.1.8 on 2021-04-10 20:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0073_callrequest_priority_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="location",
            name="preferred_contact_method",
            field=models.CharField(
                choices=[
                    ("research_online", "research_online"),
                    ("outbound_call", "outbound_call"),
                ],
                max_length=32,
                null=True,
            ),
        ),
    ]
