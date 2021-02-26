from django.db import migrations


availability_tags = (
    (
        "No: may be a vaccination site in the future",
        "This location is not yet operating as a vaccination site but may become one soon",
    ),
    (
        "Yes: Vaccinating essential workers",
        "This location is vaccinating essential workers",
    ),
    (
        "Yes: restricted to city residents",
        "This location is only vaccinating residents of the city it is located in",
    ),
    (
        "Yes: Scheduling second dose only",
        "This location is only scheduling the second dose",
    ),
)


def populate_availability_tags(apps, schema_editor):
    AvailabilityTag = apps.get_model("core", "AvailabilityTag")
    for name, notes in availability_tags:
        AvailabilityTag.objects.create(name=name, notes=notes)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_callreport_airtable_json"),
    ]

    operations = [
        migrations.RunPython(populate_availability_tags),
    ]
