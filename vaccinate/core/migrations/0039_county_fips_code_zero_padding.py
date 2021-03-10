from django.db import migrations


def zero_pad_county_fips_codes(apps, schema_editor):
    County = apps.get_model("core", "County")
    for county in County.objects.all():
        if len(county.fips_code) == 4:
            county.fips_code = "0" + county.fips_code
            county.save()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0038_county_fips_code_string_not_integer"),
    ]

    operations = [
        migrations.RunPython(
            zero_pad_county_fips_codes, reverse_code=lambda apps, schema_editor: None
        )
    ]
