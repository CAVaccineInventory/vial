from django.db import migrations


reasons = ("Stale report", "New location", "Eva tip", "Data corrections tip")


def populate_call_request_reasons(apps, schema_editor):
    CallRequestReason = apps.get_model("core", "CallRequestReason")
    for short_reason in reasons:
        CallRequestReason.objects.create(short_reason=short_reason)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_populate_county_airtable_ids"),
    ]

    operations = [
        migrations.RunPython(populate_call_request_reasons),
    ]
