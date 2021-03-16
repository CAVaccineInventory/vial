from django.db import migrations


def add_availability_tag(apps, schema_editor):
    AvailabilityTag = apps.get_model("core", "AvailabilityTag")
    AvailabilityTag.objects.create(
        name="Vaccinating education and childcare workers",
        slug="education_childcare_workers",
        group="yes",
        notes="This location vaccinates education and childcare workers",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0041_availability_tag_emergency_services"),
    ]

    operations = [
        migrations.RunPython(
            add_availability_tag, reverse_code=lambda apps, schema_editor: None
        ),
    ]
