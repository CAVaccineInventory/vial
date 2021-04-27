from django.db import migrations

# https://github.com/CAVaccineInventory/vial/issues/293


def add_availability_tags(apps, schema_editor):
    AvailabilityTag = apps.get_model("core", "AvailabilityTag")
    AvailabilityTag.objects.update_or_create(
        slug="appointments_or_walkins",
        defaults={
            "name": "Appointments or walk-ins accepted",
            "group": "yes",
            "notes": "This location provides appointments but can also accept walk-ins",
            "previous_names": ["Yes: appointments or walk-ins accepted"],
        },
    )
    AvailabilityTag.objects.update_or_create(
        slug="appointments_available",
        defaults={
            "name": "Appointments available",
            "group": "yes",
            "notes": "This location has available appointments",
            "previous_names": ["Yes: appointments available"],
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0100_refresh_denormalizations"),
    ]

    operations = [
        migrations.RunPython(
            add_availability_tags, reverse_code=lambda apps, schema_editor: None
        ),
    ]
