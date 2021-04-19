from django.db import migrations


def update_location_types(apps, schema_editor):
    LocationType = apps.get_model("core", "LocationType")
    # Add an unknown one
    LocationType.objects.get_or_create(name="Unknown")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0092_sourcelocation_matched_location"),
    ]

    operations = [
        migrations.RunPython(
            update_location_types, reverse_code=lambda apps, schema_editor: None
        ),
    ]
