from django.db import migrations

reasons = ("Previously skipped",)


def populate_call_request_reasons(apps, schema_editor):
    CallRequestReason = apps.get_model("core", "CallRequestReason")
    for short_reason in reasons:
        CallRequestReason.objects.create(short_reason=short_reason)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_auto_20210303_2019"),
    ]

    operations = [
        migrations.RunPython(populate_call_request_reasons),
    ]
