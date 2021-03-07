from django.db import migrations


def add_location_type(apps, schema_editor):
    LocationType = apps.get_model("core", "LocationType")
    LocationType.objects.get_or_create(name="Unknown")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0032_skip_call_request_reason"),
    ]

    operations = [
        migrations.RunPython(
            add_location_type, reverse_code=lambda apps, schema_editor: None
        ),
    ]
