from django.db import migrations


def insert_dc(apps, schema_editor):
    State = apps.get_model("core", "State")
    State.objects.update_or_create(
        abbreviation="DC", defaults={"name": "District of Columbia", "fips_code": "11"}
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0036__missing_territories_and_state_fips_codes"),
    ]

    operations = [
        migrations.RunPython(insert_dc, reverse_code=lambda apps, schema_editor: None)
    ]
