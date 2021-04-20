from django.db import migrations

# https://github.com/CAVaccineInventory/vial/issues/359


def add_availability_tag(apps, schema_editor):
    AvailabilityTag = apps.get_model("core", "AvailabilityTag")
    AvailabilityTag.objects.update_or_create(
        slug="jj_pause",
        defaults=dict(
            name="Vaccinations may be on hold due to CDC/FDA guidance regarding the Johnson & Johnson vaccine",
            group="other",
            notes="",
            previous_names=[],
        ),
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0095_rename_concordance_identifier_table"),
    ]

    operations = [
        migrations.RunPython(
            add_availability_tag, reverse_code=lambda apps, schema_editor: None
        ),
    ]
