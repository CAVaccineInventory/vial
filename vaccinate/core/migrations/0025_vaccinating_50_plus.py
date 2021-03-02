from django.db import migrations


def create_tag(apps, schema_editor):
    AvailabilityTag = apps.get_model("core", "AvailabilityTag")
    AvailabilityTag.objects.create(
        name="Vaccinating 50+",
        slug="vaccinating_50_plus",
        group="yes",
        notes="This location is only vaccinating people who are 50 or older. Locations should only be tagged with a single Yes: vaccinating x+ label.",
        disabled=False,
        previous_names=["Yes: vaccinating 50+"],
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0024_more_rename_call_reports_to_reports"),
    ]

    operations = [
        migrations.RunPython(create_tag),
    ]
