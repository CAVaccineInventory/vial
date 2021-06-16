from django.db import migrations


def rename_ambigous_counties(apps, schema_editor):
    County = apps.get_model("core", "County")
    for fips_code, name in {
        "24510": "Baltimore City",
        "29510": "St Louis City",
        "51600": "Fairfax City",
        "51620": "Franklin City",
        "51760": "Richmond City",
        "51770": "Roanoke City",
    }.items():
        County.objects.filter(fips_code=fips_code).update(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0147_location_provenance_columns"),
    ]

    operations = [
        migrations.RunPython(
            rename_ambigous_counties, reverse_code=lambda apps, schema_editor: None
        ),
    ]
