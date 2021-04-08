from django.db import migrations

# https://github.com/CAVaccineInventory/vial/issues/168


def add_availability_tags(apps, schema_editor):
    more_ages = [18, 16, 45, 40, 55, 60, 30, 35]

    AvailabilityTag = apps.get_model("core", "AvailabilityTag")
    for age in more_ages:
        AvailabilityTag.objects.update_or_create(
            slug=f"vaccinating_{age}_plus",
            defaults=dict(
                name=f"Vaccinating {age}+",
                group="yes",
                notes=f"This location is only vaccinating people who are {age} or older. "
                "Locations should only be tagged with a single Yes: vaccinating x+ label.",
                previous_names=[f"Yes: vaccinating {age}+"],
            ),
        )

    for slug, name in (
        ("eligibility_state_website", "Eligibility determined by state website"),
        ("eligibility_county_website", "Eligibility determined by county website"),
        ("eligibility_provider_website", "Eligibility determined by provider website"),
    ):
        AvailabilityTag.objects.update_or_create(
            slug=slug,
            defaults=dict(
                name=name,
                group="other",
            ),
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0064_availability_tag_group_other"),
    ]

    operations = [
        migrations.RunPython(
            add_availability_tags, reverse_code=lambda apps, schema_editor: None
        ),
    ]
