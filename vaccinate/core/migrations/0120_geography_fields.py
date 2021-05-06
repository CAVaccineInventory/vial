# Generated by Django 3.2.1 on 2021-05-06 22:30

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0119_populate_source_location_point"),
    ]

    operations = [
        migrations.AlterField(
            model_name="location",
            name="point",
            field=django.contrib.gis.db.models.fields.PointField(
                blank=True, geography=True, null=True, srid=4326
            ),
        ),
        migrations.AlterField(
            model_name="sourcelocation",
            name="point",
            field=django.contrib.gis.db.models.fields.GeometryField(
                blank=True, geography=True, null=True, srid=4326
            ),
        ),
    ]