# Generated by Django 3.1.7 on 2021-03-29 20:30

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0053_rename_auth0_role_name"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="location",
            options={"permissions": [("merge_locations", "Can merge two locations")]},
        ),
    ]
