from django.db import migrations


def add_availability_tag(apps, schema_editor):
    AvailabilityTag = apps.get_model("core", "AvailabilityTag")
    AvailabilityTag.objects.create(
        name="Vaccinating emergency services workers",
        slug="emergency_service_workers",
        group="yes",
        notes="This location vaccinates emergency service workers",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0040_increase_size_location_import_ref"),
    ]

    operations = [
        migrations.RunPython(
            add_availability_tag, reverse_code=lambda apps, schema_editor: None
        ),
    ]
