from django.db import migrations

location_types = (
    "Hospital / Clinic",
    "Pharmacy",
    "Super Site",
    "Private Practice",
    "School",
)

provider_types = (
    "Pharmacy",
    "Hospital",
    "Health Plan",
    "Other",
)

availability_tags = (
    (
        "No: only vaccinating staff",
        "This location is currently only vaccinating their own staff",
    ),
    ("No: not open to the public", "This location is currently not open to the public"),
    (
        "No: only vaccinating health care workers",
        "This location is currently only vaccinating healthcare workers",
    ),
    ("No: no vaccine inventory", "This location is out of vaccines"),
    (
        "No: incorrect contact information",
        "We do not have the correct contact information for this location",
    ),
    ("No: location permanently closed", "This location is permanently closed"),
    (
        "No: will never be a vaccination site",
        "We  do not think this location will ever provide vaccinations. This label  will not be used for healthcare venues that currently have no plans for  the vaccine, rather it will be used for places that we do not think  would ever be vaccinating people, like an Arby's.",
    ),
    (
        "Yes: walk-ins accepted",
        "This location allows walk-ins, subject to other caveats",
    ),
    (
        "Yes: appointment required",
        "This location requires appointments. If this is mixed with Yes: walk-ins accepted, it means that the location prefers appointments, but sometimes allows walk-ins as well. Typically Latest report notes will have more information in this case.",
    ),
    (
        "Yes: vaccinating 65+",
        "This location is only vaccinating people who are 65 or older. Locations should only be tagged with a single Yes: vaccinating x+ label.",
    ),
    (
        "Yes: vaccinating 70+",
        "This location is only vaccinating people who are 70 or older. Locations should only be tagged with a single Yes: vaccinating x+ label.",
    ),
    (
        "Yes: vaccinating 75+",
        "This location is only vaccinating people who are 75 or older. Locations should only be tagged with a single Yes: vaccinating x+ label.",
    ),
    (
        "Yes: vaccinating 80+",
        "This location is only vaccinating people who are 80 or older. Locations should only be tagged with a single Yes: vaccinating x+ label.",
    ),
    (
        "Yes: vaccinating 85+",
        "This location is only vaccinating people who are 85 or older. Locations should only be tagged with a single Yes: vaccinating x+ label.",
    ),
    (
        "Yes: restricted to county residents",
        "This location is only vaccinating residents of the county it is located in",
    ),
    (
        "Yes: must be a current patient",
        "This  location is only vaccinating people who are already patients of the  location. In some cases it may be possible to sign up as a patient.",
    ),
    (
        "Yes: must be a veteran",
        "This location is currently only vaccinating military veterans.",
    ),
    (
        "Yes: appointment calendar currently full",
        "When we last checked, this location was out of appointments. There may be more information in Latest report notes that explain when we think more appointments will be released.",
    ),
    (
        "Yes: coming soon",
        "This location is currently closed but is slated to open soon. Typically Latest report notes will have more information in this case.",
    ),
    (
        "Skip: call back later",
        "Such entries should not be surfaced to the API. Please report a bug at api@vaccinateca.com  We use this internally for marking cases where the location is  temporarily unavailable (typically due to a weekend, holiday, or lunch  break)",
    ),
)


def populate_location_types(apps, schema_editor):
    LocationType = apps.get_model("core", "LocationType")
    for name in location_types:
        LocationType.objects.create(name=name)


def populate_provider_types(apps, schema_editor):
    ProviderType = apps.get_model("core", "ProviderType")
    for name in provider_types:
        ProviderType.objects.create(name=name)


def populate_availability_tags(apps, schema_editor):
    AvailabilityTag = apps.get_model("core", "AvailabilityTag")
    for name, notes in availability_tags:
        AvailabilityTag.objects.create(name=name, notes=notes)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_populate_ca_counties"),
    ]

    operations = [
        migrations.RunPython(populate_location_types),
        migrations.RunPython(populate_provider_types),
        migrations.RunPython(populate_availability_tags),
    ]
