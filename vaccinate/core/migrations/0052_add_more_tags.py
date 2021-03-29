# Generated by Django 3.1.7 on 2021-03-11 20:47

from django.db import migrations

# See CAVaccineInventory/help.vaccinate@5ffde0431bed035b061cc30d27a9450821ce609e


def add_availability_tags(apps, schema_editor):
    more_ages = [18, 16]

    AvailabilityTag = apps.get_model("core", "AvailabilityTag")
    for age in more_ages:
        AvailabilityTag.objects.create(
            name=f"Vaccinating {age}+",
            slug=f"vaccinating_{age}_plus",
            group="yes",
            notes=f"This location is only vaccinating people who are {age} or older. "
            "Locations should only be tagged with a single Yes: vaccinating x+ label.",
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0051_locations_hours_textarea"),
    ]

    operations = [
        migrations.RunPython(
            add_availability_tags, reverse_code=lambda apps, schema_editor: None
        ),
    ]