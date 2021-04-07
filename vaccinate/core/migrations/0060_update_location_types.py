from django.db import migrations
from django.db.models import F, Value
from django.db.models.functions import Concat


def update_location_types(apps, schema_editor):
    LocationType = apps.get_model("core", "LocationType")
    # Add two missing ones
    LocationType.objects.get_or_create(name="Test Location")
    correctional = LocationType.objects.get_or_create(name="Correctional Facility")[0]
    # Update Santa Barbara County Juvenile Hall, then delete it
    try:
        juvenile_hall = LocationType.objects.get(
            name="Santa Barbara County Juvenile Hall"
        )
        juvenile_hall.locations.update(location_type=correctional)
        juvenile_hall.delete()
    except LocationType.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0059_populate_import_ref_from_airtable_id"),
    ]

    operations = [
        migrations.RunPython(
            update_location_types, reverse_code=lambda apps, schema_editor: None
        ),
    ]
