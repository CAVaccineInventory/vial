from django.db import migrations

# https://github.com/CAVaccineInventory/vial/issues/370

concordances = (
    # Location column, ConcordanceIdentifier source
    ("google_places_id", "google_places"),
    ("vaccinespotter_location_id", "vaccinespotter"),
    ("vaccinefinder_location_id", "vaccinefinder"),
)


def populate_concordances(apps, schema_editor):
    # Migration disabled because it takes too long to run in prod
    # https://github.com/CAVaccineInventory/vial/issues/370#issuecomment-823669731
    return
    # Location = apps.get_model("core", "Location")
    # ConcordanceIdentifier = apps.get_model("core", "ConcordanceIdentifier")

    # for column, source in concordances:
    #     locations = Location.objects.exclude(**{f"{column}__isnull": True})
    #     for location in locations.only(*[p[0] for p in concordances]):
    #         identifier = getattr(location, column)
    #         concordance_identifier = ConcordanceIdentifier.objects.get_or_create(
    #             source=source,
    #             identifier=identifier,
    #         )[0]
    #         location.concordances.add(concordance_identifier)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0093_sourcelocation_matched_location"),
    ]

    operations = [
        migrations.RunPython(
            populate_concordances, reverse_code=lambda apps, schema_editor: None
        ),
    ]
