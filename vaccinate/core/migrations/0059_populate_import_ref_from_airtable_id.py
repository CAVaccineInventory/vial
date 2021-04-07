from django.db import migrations
from django.db.models import F, Value
from django.db.models.functions import Concat


def populate_import_ref(apps, schema_editor):
    Location = apps.get_model("core", "Location")
    Location.objects.filter(import_ref__isnull=True,).exclude(
        airtable_id__isnull=True
    ).update(import_ref=Concat(Value("vca-airtable:"), F("airtable_id")))


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0058_county_age_floor_without_restrictions_internal_notes"),
    ]

    operations = [
        migrations.RunPython(
            populate_import_ref, reverse_code=lambda apps, schema_editor: None
        ),
    ]
