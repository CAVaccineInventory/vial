# Generated by Django 3.1.7 on 2021-03-01 19:24

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_location_county_can_be_null"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="CallReport",
            new_name="Report",
        ),
    ]
