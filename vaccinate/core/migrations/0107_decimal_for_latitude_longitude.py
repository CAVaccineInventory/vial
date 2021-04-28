# Generated by Django 3.1.8 on 2021-04-28 00:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0106_improved_priority_help_text"),
    ]

    operations = [
        migrations.AlterField(
            model_name="location",
            name="latitude",
            field=models.DecimalField(decimal_places=5, max_digits=9),
        ),
        migrations.AlterField(
            model_name="location",
            name="longitude",
            field=models.DecimalField(decimal_places=5, max_digits=9),
        ),
        migrations.AlterField(
            model_name="sourcelocation",
            name="latitude",
            field=models.DecimalField(
                blank=True, decimal_places=5, max_digits=9, null=True
            ),
        ),
        migrations.AlterField(
            model_name="sourcelocation",
            name="longitude",
            field=models.DecimalField(
                blank=True, decimal_places=5, max_digits=9, null=True
            ),
        ),
    ]
