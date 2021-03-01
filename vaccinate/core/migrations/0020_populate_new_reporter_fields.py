from django.db import migrations
from django.db.models import F, Value, CharField
from django.db.models.functions import Concat


def populate_new_reporter_fields(apps, schema_editor):
    Reporter = apps.get_model("core", "Reporter")
    Reporter.objects.exclude(airtable_name__isnull=True).update(
        external_id=Concat(
            Value("airtable:"), F("airtable_name"), output_field=CharField()
        )
    )
    Reporter.objects.exclude(auth0_name__isnull=True).update(
        external_id=Concat(Value("auth0:"), F("auth0_name"), output_field=CharField())
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0019_redesign_reporter"),
    ]

    operations = [
        migrations.RunPython(populate_new_reporter_fields),
    ]
