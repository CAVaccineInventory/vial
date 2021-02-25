from django.db import migrations

appointment_tags = (
    ("County website", False),
    ("myturn.ca.gov", False),
    ("web", True),
    ("phone", True),
    ("other", True),
)


def populate_appointment_tags(apps, schema_editor):
    AppointmentTag = apps.get_model("core", "AppointmentTag")
    for name, has_details in appointment_tags:
        AppointmentTag.objects.create(name=name, has_details=has_details)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_populate_call_request_reasons"),
    ]

    operations = [
        migrations.RunPython(populate_appointment_tags),
    ]
