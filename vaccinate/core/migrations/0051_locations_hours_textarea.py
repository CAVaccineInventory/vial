# Generated by Django 3.1.7 on 2021-03-26 00:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0050_run_createinitialrevisions_for_locations"),
    ]

    operations = [
        migrations.AlterField(
            model_name="location",
            name="hours",
            field=models.TextField(blank=True, null=True),
        ),
    ]
