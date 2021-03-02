from django.db import migrations
from django.db.models import F


def backfill_public_ids(apps, schema_editor):
    Location = apps.get_model("core", "Location")
    Report = apps.get_model("core", "Report")
    Location.objects.filter(public_id__isnull=True, airtable_id__isnull=False).update(
        public_id=F("airtable_id")
    )
    Report.objects.filter(public_id__isnull=True, airtable_id__isnull=False).update(
        public_id=F("airtable_id")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0026_public_id"),
    ]

    operations = [
        migrations.RunPython(backfill_public_ids),
    ]
